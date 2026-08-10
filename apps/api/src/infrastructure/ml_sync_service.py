"""Sincronização entre o Mercado Livre e a base local.

Responsável por trazer anúncios, pedidos e perguntas para o banco, e por
espelhar os pedidos do ML na tabela unificada de pedidos (RealOrderDB), que é
a fonte usada pelo dashboard e pelos agentes.
"""

import json
import time
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from src.infrastructure.database import (
    async_session,
    init_db,
    MLAccountDB,
    MLListingDB,
    MLOrderDB,
    MLQuestionDB,
    RealOrderDB,
)
from src.config import settings
from src.infrastructure.mercadolivre_client import (
    MercadoLivreClient,
    MercadoLivreError,
    MercadoLivreReadOnlyError,
)


async def build_client(account: MLAccountDB) -> MercadoLivreClient:
    """Cria um cliente já ligado à persistência de tokens da conta."""

    async def persist_tokens(tokens: Dict[str, Any]) -> None:
        async with async_session() as session:
            row = await session.get(MLAccountDB, account.id)
            if row:
                row.access_token = tokens["access_token"]
                row.refresh_token = tokens["refresh_token"]
                row.expires_at = tokens["expires_at"]
                await session.commit()

    return MercadoLivreClient(
        access_token=account.access_token,
        refresh_token=account.refresh_token,
        user_id=account.ml_user_id,
        expires_at=account.expires_at,
        on_token_refresh=persist_tokens,
    )


async def get_account(ml_user_id: Optional[int] = None) -> Optional[MLAccountDB]:
    """Retorna a conta pedida ou, sem argumento, a primeira conta ativa."""
    async with async_session() as session:
        query = select(MLAccountDB).where(MLAccountDB.is_active == True)  # noqa: E712
        if ml_user_id:
            query = query.where(MLAccountDB.ml_user_id == ml_user_id)
        result = await session.execute(query)
        return result.scalars().first()


class MercadoLivreSyncService:

    # ------------------------------------------------------------------
    # Anúncios
    # ------------------------------------------------------------------

    async def sync_listings(self, account: MLAccountDB, status: Optional[str] = None,
                            max_items: int = 5000) -> Dict[str, Any]:
        """Baixa todos os anúncios do vendedor usando o modo scan.

        O scan é obrigatório acima de 1000 anúncios; abaixo disso ele também
        funciona, então usamos um caminho único.
        """
        await init_db()
        client = await build_client(account)

        item_ids: List[str] = []
        scroll_id: Optional[str] = None

        while len(item_ids) < max_items:
            # Respeita Rate Limit do ML (evita 429 Too Many Requests)
            await asyncio.sleep(0.35)
            
            page = await client.scan_user_items(status=status, scroll_id=scroll_id, limit=100)
            results = page.get("results", [])
            if not results:
                break
            item_ids.extend(results)
            scroll_id = page.get("scroll_id")
            if not scroll_id:
                break

        # O multiget devolve o anúncio completo; a busca devolve só os IDs.
        details = await client.get_items_batch(item_ids)

        synced = 0
        async with async_session() as session:
            for entry in details:
                body = entry.get("body") if isinstance(entry, dict) and "body" in entry else entry
                if not body or not body.get("id"):
                    continue

                sku = ""
                for attr in body.get("attributes", []) or []:
                    if attr.get("id") in ("SELLER_SKU", "GTIN"):
                        sku = attr.get("value_name") or ""
                        if attr.get("id") == "SELLER_SKU":
                            break
                if not sku:
                    sku = body.get("seller_custom_field") or ""

                shipping = body.get("shipping", {}) or {}
                listing = MLListingDB(
                    id=body["id"],
                    ml_user_id=account.ml_user_id,
                    title=body.get("title", ""),
                    sku=sku,
                    category_id=body.get("category_id", ""),
                    listing_type_id=body.get("listing_type_id", ""),
                    price=float(body.get("price") or 0.0),
                    available_quantity=int(body.get("available_quantity") or 0),
                    sold_quantity=int(body.get("sold_quantity") or 0),
                    status=body.get("status", "active"),
                    permalink=body.get("permalink", ""),
                    thumbnail=body.get("thumbnail", ""),
                    logistic_type=shipping.get("logistic_type", "") or "",
                    free_shipping=bool(shipping.get("free_shipping", False)),
                    catalog_listing=bool(body.get("catalog_listing", False)),
                    health=float(body.get("health") or 0.0),
                    raw_json=json.dumps(body)[:100000],
                    synced_at=datetime.now(),
                )
                await session.merge(listing)
                synced += 1

            row = await session.get(MLAccountDB, account.id)
            if row:
                row.last_sync_at = datetime.now()
            await session.commit()

        return {"listings_found": len(item_ids), "listings_synced": synced}

    # ------------------------------------------------------------------
    # Pedidos
    # ------------------------------------------------------------------

    async def sync_orders(self, account: MLAccountDB, status: Optional[str] = None,
                          date_from: Optional[str] = None, max_orders: int = 1000) -> Dict[str, Any]:
        """Baixa pedidos e os espelha na tabela unificada RealOrderDB."""
        await init_db()
        client = await build_client(account)

        orders: List[Dict[str, Any]] = []
        offset = 0
        while len(orders) < max_orders:
            # Respeita Rate Limit do ML (evita 429 Too Many Requests)
            await asyncio.sleep(0.35)
            
            page = await client.search_orders(
                status=status, date_from=date_from, limit=50, offset=offset
            )
            results = page.get("results", [])
            if not results:
                break
            orders.extend(results)
            offset += 50
            if offset >= int(page.get("paging", {}).get("total", 0)):
                break

        synced = 0
        async with async_session() as session:
            for o in orders:
                order_id = str(o.get("id"))
                buyer = o.get("buyer", {}) or {}
                shipping = o.get("shipping", {}) or {}
                payments = o.get("payments", []) or []
                paid = sum(float(p.get("total_paid_amount") or 0.0) for p in payments)

                items = [
                    {
                        "sku": (it.get("item", {}) or {}).get("seller_sku")
                               or (it.get("item", {}) or {}).get("seller_custom_field") or "",
                        "item_id": (it.get("item", {}) or {}).get("id", ""),
                        "name": (it.get("item", {}) or {}).get("title", ""),
                        "quantity": it.get("quantity", 0),
                        "price": it.get("unit_price", 0.0),
                    }
                    for it in (o.get("order_items", []) or [])
                ]

                date_created = self._parse_ml_date(o.get("date_created"))

                await session.merge(MLOrderDB(
                    id=order_id,
                    ml_user_id=account.ml_user_id,
                    status=o.get("status", ""),
                    status_detail=str(o.get("status_detail") or ""),
                    buyer_id=str(buyer.get("id", "")),
                    buyer_nickname=buyer.get("nickname", ""),
                    total_amount=float(o.get("total_amount") or 0.0),
                    paid_amount=paid,
                    currency_id=o.get("currency_id", "BRL"),
                    shipping_id=str(shipping.get("id", "") or ""),
                    shipping_status=shipping.get("status", "") or "",
                    tracking_number=shipping.get("tracking_number", "") or "",
                    pack_id=str(o.get("pack_id") or ""),
                    items_json=json.dumps(items),
                    date_created=date_created,
                    synced_at=datetime.now(),
                ))

                # Espelho na tabela unificada consumida pelo dashboard e agentes.
                from src.infrastructure.order_customer import buyer_name_for_sync

                await session.merge(RealOrderDB(
                    id=f"ML-{order_id}",
                    external_id=order_id,
                    customer_name=buyer_name_for_sync(o) or "—",
                    customer_email=buyer.get("email", "") or "",
                    customer_phone="",
                    status_id=0,
                    status_name=self._map_status(o.get("status", "")),
                    total_amount=float(o.get("total_amount") or 0.0),
                    channel_name="Mercado Livre",
                    items_json=json.dumps(items),
                    created_at=date_created,
                ))
                synced += 1

            await session.commit()

        return {"orders_synced": synced}

    @staticmethod
    def _parse_ml_date(value: Optional[str]) -> datetime:
        """Converte a data ISO-8601 do ML (com offset) para datetime naive local."""
        if not value:
            return datetime.now()
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None)
        except (ValueError, AttributeError):
            return datetime.now()

    @staticmethod
    def _map_status(ml_status: str) -> str:
        """Traduz o status do ML para o workflow interno de separação."""
        return {
            "confirmed": "Novos pedidos",
            "payment_required": "Aguardando Pagamento",
            "payment_in_process": "Aguardando Pagamento",
            "partially_paid": "Aguardando Pagamento",
            "paid": "Pago",
            "shipped": "Enviado",
            "delivered": "Enviado",
            "cancelled": "Cancelado",
            "invalid": "Cancelado",
        }.get(ml_status, "Novos pedidos")

    # ------------------------------------------------------------------
    # Perguntas
    # ------------------------------------------------------------------

    async def sync_questions(self, account: MLAccountDB, status: str = "UNANSWERED") -> Dict[str, Any]:
        """Baixa as perguntas dos anúncios do vendedor."""
        await init_db()
        client = await build_client(account)

        page = await client.search_questions(status=status, limit=50)
        questions = page.get("questions", []) or []

        synced = 0
        async with async_session() as session:
            for q in questions:
                answer = q.get("answer") or {}
                await session.merge(MLQuestionDB(
                    id=str(q.get("id")),
                    ml_user_id=account.ml_user_id,
                    item_id=q.get("item_id", ""),
                    item_title="",
                    text=q.get("text", ""),
                    status=q.get("status", status),
                    answer_text=answer.get("text", "") or "",
                    from_user_id=str((q.get("from", {}) or {}).get("id", "")),
                    date_created=self._parse_ml_date(q.get("date_created")),
                ))
                synced += 1
            await session.commit()

        return {"questions_synced": synced}

    # ------------------------------------------------------------------
    # Sincronismo reverso (base local → Mercado Livre)
    # ------------------------------------------------------------------

    async def push_stock(self, account: MLAccountDB, sku: str, quantity: int) -> Dict[str, Any]:
        """Propaga estoque — bloqueado enquanto ML_READ_ONLY=True."""
        if settings.ML_READ_ONLY:
            raise MercadoLivreReadOnlyError("PUT", f"/items?sku={sku}&available_quantity")
        client = await build_client(account)

        async with async_session() as session:
            result = await session.execute(
                select(MLListingDB).where(
                    MLListingDB.sku == sku,
                    MLListingDB.ml_user_id == account.ml_user_id,
                )
            )
            listings = result.scalars().all()

        if not listings:
            return {"updated": 0, "detail": f"Nenhum anúncio vinculado ao SKU {sku}"}

        updated, errors = 0, []
        for listing in listings:
            try:
                await client.update_item_stock(listing.id, quantity, allow_write=True)
                updated += 1
            except MercadoLivreError as exc:
                errors.append({"item_id": listing.id, "error": exc.message})

        # Reflete o novo estoque localmente para não esperar o próximo sync.
        if updated:
            async with async_session() as session:
                for listing in listings:
                    row = await session.get(MLListingDB, listing.id)
                    if row:
                        row.available_quantity = quantity
                await session.commit()

        return {"updated": updated, "errors": errors}

    async def push_price(self, account: MLAccountDB, item_id: str, price: float) -> Dict[str, Any]:
        """Atualiza preço — bloqueado enquanto ML_READ_ONLY=True."""
        if settings.ML_READ_ONLY:
            raise MercadoLivreReadOnlyError("PUT", f"/items/{item_id}")
        client = await build_client(account)
        response = await client.update_item_price(item_id, price, allow_write=True)

        async with async_session() as session:
            row = await session.get(MLListingDB, item_id)
            if row:
                row.price = price
            await session.commit()

        return {"item_id": item_id, "price": price, "ml_response_status": response.get("status")}

    # ------------------------------------------------------------------
    # Sincronismo completo
    # ------------------------------------------------------------------

    async def sync_all(self, account: MLAccountDB) -> Dict[str, Any]:
        """Executa a carga completa: anúncios, pedidos e perguntas."""
        started = time.monotonic()
        stats: Dict[str, Any] = {}
        steps = (
            ("listings", self.sync_listings),
            ("orders", self.sync_orders),
            ("questions", self.sync_questions),
        )
        for name, step in steps:
            try:
                stats.update(await step(account))
            except MercadoLivreError as exc:
                stats[f"{name}_error"] = exc.message
        stats["elapsed_seconds"] = round(time.monotonic() - started, 2)
        return stats


ml_sync_service = MercadoLivreSyncService()
