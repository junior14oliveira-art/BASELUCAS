"""Sincronismo read-only a partir do feed Mercado Livre (bridge).

Substitui o BaseLinker como fonte dos dados exibidos no /app:
- puxa feed/orders/items
- grava em RealOrderStatusDB / RealOrderDB / RealProductDB
- não envia escrita de volta ao ML nem ao BaseLinker
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select

from src.infrastructure.database import (
    MLClaimDB,
    MLQuestionDB,
    RealOrderDB,
    RealOrderStatusDB,
    RealProductDB,
    SyncMetaDB,
    async_session,
    init_db,
)
from src.infrastructure.ml_feed_client import (
    ORDERS_MAX_LIMIT,
    MLFeedClientError,
    ml_feed_client,
)

# Paginação completa (~8k pedidos): 50/página. Enrich detalhe/shipment só no lote recente.
ENRICH_ORDERS_LIMIT = 40
ENRICH_ITEMS_LIMIT = 200
ENRICH_DELAY_SEC = 0.35
ORDERS_MAX_OFFSET = 20_000

# Status canônicos ML → rótulos em PT-BR usados na sidebar.
STATUS_CATALOG: List[Tuple[int, str, str]] = [
    (1, "Pagos", "#0D8000"),
    (2, "Confirmados", "#0066FF"),
    (3, "Prontos para enviar", "#B80AF7"),
    (4, "Enviados", "#0D8000"),
    (5, "Entregues", "#10B981"),
    (6, "Cancelados", "#CC0000"),
    (7, "Outros", "#64748B"),
]

STATUS_MAP = {
    "paid": "Pagos",
    "payment_required": "Pagos",
    "confirmed": "Confirmados",
    "payment_in_process": "Confirmados",
    "ready_to_ship": "Prontos para enviar",
    "shipped": "Enviados",
    "delivered": "Entregues",
    "cancelled": "Cancelados",
    "canceled": "Cancelados",
}


def _parse_date(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value is None or value == "":
        return datetime.now()
    if isinstance(value, (int, float)):
        # epoch segundos ou ms
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts)
        except (OverflowError, OSError, ValueError):
            return datetime.now()
    text = str(value).strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(text.replace("+00:00", "Z"), fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.now()


def _map_status(raw: Any) -> str:
    key = str(raw or "").strip().lower()
    if not key:
        return "Outros"
    if key in STATUS_MAP:
        return STATUS_MAP[key]
    # Já pode vir em português do bridge
    for _, name, _ in STATUS_CATALOG:
        if name.lower() == key:
            return name
    return raw if isinstance(raw, str) and raw.strip() else "Outros"


def _status_id(name: str) -> int:
    for sid, label, _ in STATUS_CATALOG:
        if label == name:
            return sid
    return 7


def _extract_items(order: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_items = (
        order.get("order_items")
        or order.get("items")
        or order.get("products")
        or []
    )
    out: List[Dict[str, Any]] = []
    for it in raw_items:
        if not isinstance(it, dict):
            continue
        item = it.get("item") if isinstance(it.get("item"), dict) else {}
        name = (
            it.get("name")
            or it.get("title")
            or item.get("title")
            or item.get("name")
            or "Item"
        )
        sku = (
            it.get("sku")
            or item.get("seller_sku")
            or item.get("seller_custom_field")
            or item.get("id")
            or ""
        )
        out.append(
            {
                "name": name,
                "sku": str(sku),
                "quantity": it.get("quantity", 1) or 1,
                "price": float(it.get("unit_price") or it.get("price") or 0.0),
                "item_id": str(item.get("id") or it.get("item_id") or ""),
            }
        )
    return out


def _buyer_name(order: Dict[str, Any]) -> str:
    buyer = order.get("buyer") if isinstance(order.get("buyer"), dict) else {}
    return (
        order.get("customer_name")
        or order.get("buyer_nickname")
        or buyer.get("nickname")
        or buyer.get("first_name")
        or "Comprador Mercado Livre"
    )


def _order_amount(order: Dict[str, Any]) -> float:
    if order.get("total_amount") is not None:
        return float(order.get("total_amount") or 0.0)
    if order.get("paid_amount") is not None:
        return float(order.get("paid_amount") or 0.0)
    payments = order.get("payments") or []
    if isinstance(payments, list) and payments:
        return sum(float(p.get("total_paid_amount") or 0.0) for p in payments if isinstance(p, dict))
    return 0.0


# Chaves em que o bridge 4MC / ML pode expor listas de pedidos (não só "paid").
_ORDER_LIST_KEYS = (
    "orders",
    "results",
    "data",
    "recent",
    "unpaid",
    "paid",
    "orders_paid",
    "orders_unpaid",
    "orders_recent",
)


def _iter_order_dicts(payload: Any) -> List[Dict[str, Any]]:
    """Extrai dicts de pedido de qualquer chave útil do feed/orders (todos os status)."""
    out: List[Dict[str, Any]] = []
    if payload is None:
        return out
    if isinstance(payload, list):
        for entry in payload:
            if isinstance(entry, dict):
                # Pedido direto ou envelope {order: {...}}
                if entry.get("id") or entry.get("order_id") or entry.get("external_id"):
                    out.append(entry)
                elif isinstance(entry.get("order"), dict):
                    out.append(entry["order"])
                else:
                    # Pode ser página aninhada
                    out.extend(_iter_order_dicts(entry))
        return out
    if not isinstance(payload, dict):
        return out
    # Pedido único
    if payload.get("id") or payload.get("order_id") or payload.get("external_id"):
        # Evita tratar o documento raiz (feed) como pedido: feed tem "orders" lista
        if not any(isinstance(payload.get(k), (list, dict)) and k in _ORDER_LIST_KEYS for k in _ORDER_LIST_KEYS):
            if "summary" not in payload and "paging" not in payload:
                out.append(payload)
    for key in _ORDER_LIST_KEYS:
        if key in payload:
            out.extend(_iter_order_dicts(payload.get(key)))
    # Nested comum: { data: { orders: [...] } }
    nested = payload.get("body") or payload.get("response")
    if isinstance(nested, (dict, list)):
        out.extend(_iter_order_dicts(nested))
    return out


def _normalize_order(order: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    order_id = order.get("id") or order.get("order_id") or order.get("external_id")
    if order_id is None:
        return None
    order_id = str(order_id)
    # Qualquer status útil — não filtrar só "paid" (summary.total_orders_paid é só métrica).
    status_name = _map_status(
        order.get("status")
        or order.get("status_name")
        or order.get("order_status")
        or order.get("shipping_status")
    )
    items = _extract_items(order)
    
    is_notebook = any("notebook" in str(it.get("name", "")).lower() for it in items)
    if is_notebook:
        status_name = "Notebook - Geral"

    buyer = order.get("buyer") if isinstance(order.get("buyer"), dict) else {}
    shipping = order.get("shipping") if isinstance(order.get("shipping"), dict) else {}
    shipment = order.get("_shipment") if isinstance(order.get("_shipment"), dict) else {}
    addr = _compact_receiver_address(shipment) if shipment else {}
    phone = str(
        order.get("customer_phone")
        or buyer.get("phone")
        or addr.get("receiver_phone")
        or ""
    )
    created = _parse_date(
        order.get("date_created")
        or order.get("date_closed")
        or order.get("created_at")
        or order.get("date_add")
    )
    enrich = {
        "shipping_status": shipment.get("status") or order.get("shipping_status") or "",
        "shipping_substatus": shipment.get("substatus") or "",
        "tracking_method": shipment.get("tracking_method") or "",
        "logistic_type": shipment.get("logistic_type") or "",
        "enriched": bool(order.get("_enriched")),
    }
    return {
        "id": f"ML-{order_id}",
        "external_id": order_id,
        "customer_name": _buyer_name(order),
        "customer_email": str(order.get("customer_email") or buyer.get("email") or ""),
        "customer_phone": phone,
        "status_id": _status_id(status_name) if not is_notebook else 3,
        "status_name": status_name,
        "total_amount": _order_amount(order),
        "channel_name": "Mercado Livre",
        "items_json": json.dumps(items, ensure_ascii=False),
        "created_at": created,
        "shipping_id": str(shipping.get("id") or shipment.get("id") or order.get("shipping_id") or ""),
        "shipping_status": str(shipment.get("status") or shipping.get("status") or ""),
        "tracking_number": str(shipment.get("tracking_number") or order.get("tracking_number") or ""),
        "shipping_address_json": json.dumps(addr, ensure_ascii=False),
        "marketplace_fee": _extract_marketplace_fee(order),
        "buyer_doc": _extract_buyer_doc(order),
        "pack_id": str(order.get("pack_id") or ""),
        "enrichment_json": json.dumps(enrich, ensure_ascii=False),
    }


def _unwrap_item_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    """Aceita item ML cru ou envelope {code, body} do multi-get."""
    body = item.get("body")
    if isinstance(body, dict) and (body.get("id") or body.get("title")):
        return body
    return item


def _attr_map(item: Dict[str, Any]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for attr in item.get("attributes", []) or []:
        if not isinstance(attr, dict):
            continue
        aid = str(attr.get("id") or "")
        val = attr.get("value_name") or attr.get("value_id") or ""
        if aid and val:
            out[aid] = str(val)
    return out


def _extract_sku(item: Dict[str, Any]) -> str:
    attrs = _attr_map(item)
    for key in ("SELLER_SKU", "SELLER_CUSTOM_FIELD", "GTIN", "EAN"):
        if attrs.get(key):
            return attrs[key]
    return str(
        item.get("seller_sku")
        or item.get("seller_custom_field")
        or item.get("sku")
        or item.get("user_product_id")
        or ""
    )


def _extract_ean(item: Dict[str, Any]) -> str:
    attrs = _attr_map(item)
    return str(attrs.get("GTIN") or attrs.get("EAN") or attrs.get("PRODUCT_IDENTIFIER") or "")


def _extract_buyer_doc(order: Dict[str, Any]) -> str:
    buyer = order.get("buyer") if isinstance(order.get("buyer"), dict) else {}
    bi = buyer.get("billing_info") if isinstance(buyer.get("billing_info"), dict) else {}
    if not bi:
        bi = order.get("billing_info") if isinstance(order.get("billing_info"), dict) else {}
    ident = bi.get("identification") if isinstance(bi.get("identification"), dict) else {}
    return str(
        bi.get("doc_number")
        or ident.get("number")
        or bi.get("document_number")
        or ""
    )


def _extract_marketplace_fee(order: Dict[str, Any]) -> float:
    payments = order.get("payments") or []
    if not isinstance(payments, list):
        return 0.0
    total = 0.0
    for p in payments:
        if not isinstance(p, dict):
            continue
        fee = p.get("marketplace_fee")
        if fee is None:
            fee = p.get("sale_fee")
        try:
            total += float(fee or 0.0)
        except (TypeError, ValueError):
            continue
    return total


def _compact_receiver_address(shipment: Dict[str, Any]) -> Dict[str, Any]:
    ra = shipment.get("receiver_address") if isinstance(shipment.get("receiver_address"), dict) else {}
    city = ra.get("city")
    state = ra.get("state")
    return {
        "receiver_name": ra.get("receiver_name") or "",
        "receiver_phone": ra.get("receiver_phone") or "",
        "address_line": ra.get("address_line") or "",
        "street_name": ra.get("street_name") or "",
        "street_number": ra.get("street_number") or "",
        "comment": ra.get("comment") or "",
        "zip_code": ra.get("zip_code") or "",
        "neighborhood": ra.get("neighborhood") or "",
        "city": city.get("name") if isinstance(city, dict) else (city or ""),
        "state": state.get("name") if isinstance(state, dict) else (state or ""),
        "country": (
            (ra.get("country") or {}).get("id")
            if isinstance(ra.get("country"), dict)
            else (ra.get("country") or "")
        ),
    }


def _safe_float(*values: Any) -> float:
    for value in values:
        if value is None or value == "":
            continue
        if isinstance(value, dict):
            nested = value.get("amount") or value.get("price") or value.get("value")
            if nested is not None:
                try:
                    return float(nested)
                except (TypeError, ValueError):
                    continue
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _safe_int(*values: Any) -> int:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(float(value))
        except (TypeError, ValueError):
            continue
    return 0


def _normalize_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    item = _unwrap_item_payload(item)
    item_id = item.get("id") or item.get("item_id") or item.get("mlb_id")
    if item_id is None:
        return None
    item_id = str(item_id)
    sku = _extract_sku(item) or item_id
    title = str(item.get("title") or item.get("name") or "")
    # Stub só com ID (sem título útil): ainda persiste, mas sem inventar preço.
    if not title or title == item_id:
        title = title or item_id
    price = _safe_float(
        item.get("price"),
        item.get("base_price"),
        item.get("sale_price"),
        item.get("unit_price"),
        item.get("prices"),
    )
    stock = _safe_int(
        item.get("available_quantity"),
        item.get("stock"),
        item.get("available_stock"),
        item.get("quantity"),
        item.get("initial_quantity"),
    )
    thumbnail = str(
        item.get("thumbnail")
        or item.get("secure_thumbnail")
        or ""
    )
    if not thumbnail:
        pics = item.get("pictures") or []
        if isinstance(pics, list) and pics and isinstance(pics[0], dict):
            thumbnail = str(pics[0].get("secure_url") or pics[0].get("url") or "")
    shipping = item.get("shipping") if isinstance(item.get("shipping"), dict) else {}
    variations = item.get("variations") if isinstance(item.get("variations"), list) else []
    return {
        "id": item_id,
        "inventory_id": "ML",
        "sku": str(sku),
        "name": title,
        "price": price,
        "stock": stock,
        "status": str(item.get("status") or item.get("sub_status") or ""),
        "permalink": str(item.get("permalink") or item.get("url") or ""),
        "thumbnail": thumbnail,
        "sold_quantity": _safe_int(item.get("sold_quantity"), item.get("sold")),
        "currency_id": str(item.get("currency_id") or "BRL"),
        "ean": _extract_ean(item),
        "logistic_type": str(shipping.get("logistic_type") or item.get("logistic_type") or ""),
        "ml_inventory_id": str(item.get("inventory_id") or ""),
        "variations_json": json.dumps(variations, ensure_ascii=False),
    }


def _products_from_orders(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Catálogo derivado das linhas de pedido quando /items vier incompleto."""
    by_id: Dict[str, Dict[str, Any]] = {}
    for order in orders:
        for line in _extract_items(order):
            item_id = str(line.get("item_id") or line.get("sku") or "")
            if not item_id:
                continue
            prev = by_id.get(item_id)
            price = float(line.get("price") or 0.0)
            row = {
                "id": item_id,
                "inventory_id": "ML",
                "sku": str(line.get("sku") or item_id),
                "name": str(line.get("name") or item_id),
                "price": price,
                "stock": 0,
                "status": "from_order",
                "permalink": "",
                "thumbnail": "",
                "sold_quantity": int(line.get("quantity") or 0),
                "currency_id": "BRL",
                "ean": "",
                "logistic_type": "",
                "ml_inventory_id": "",
                "variations_json": "[]",
            }
            if prev:
                # Mantém o maior preço visto e soma vendidos
                row["price"] = max(float(prev.get("price") or 0.0), price)
                row["sold_quantity"] = int(prev.get("sold_quantity") or 0) + int(
                    line.get("quantity") or 0
                )
                if prev.get("name") and prev["name"] != item_id:
                    row["name"] = prev["name"]
                if prev.get("sku"):
                    row["sku"] = prev["sku"]
            by_id[item_id] = row
    return list(by_id.values())


def _is_product_stub(row: Dict[str, Any]) -> bool:
    """Stub = só ID, sem título/preço/estoque úteis."""
    pid = str(row.get("id") or "")
    name = str(row.get("name") or "")
    return (not name or name == pid) and float(row.get("price") or 0.0) == 0.0


def _merge_products(
    primary: List[Dict[str, Any]], fallback: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Une catálogo /items com derivados de pedidos; anúncio completo ganha em conflito."""
    merged: Dict[str, Dict[str, Any]] = {
        str(row["id"]): dict(row) for row in fallback if row.get("id") is not None
    }
    for row in primary:
        pid = str(row.get("id") or "")
        if not pid:
            continue
        prev = merged.get(pid)
        if not prev:
            merged[pid] = dict(row)
            continue
        if _is_product_stub(row) and not _is_product_stub(prev):
            # Mantém dados do pedido; só anexa status do stub se faltar
            if not prev.get("status") and row.get("status"):
                prev["status"] = row["status"]
            continue
        out = dict(row)
        # Completa lacunas com fallback (pedido)
        if (not out.get("name") or out.get("name") == pid) and prev.get("name"):
            out["name"] = prev["name"]
        if (not out.get("sku") or out.get("sku") == pid) and prev.get("sku"):
            out["sku"] = prev["sku"]
        if not float(out.get("price") or 0.0) and prev.get("price"):
            out["price"] = float(prev["price"])
        if not out.get("permalink") and prev.get("permalink"):
            out["permalink"] = prev["permalink"]
        if not out.get("thumbnail") and prev.get("thumbnail"):
            out["thumbnail"] = prev["thumbnail"]
        if not out.get("ean") and prev.get("ean"):
            out["ean"] = prev["ean"]
        if not out.get("logistic_type") and prev.get("logistic_type"):
            out["logistic_type"] = prev["logistic_type"]
        if not out.get("ml_inventory_id") and prev.get("ml_inventory_id"):
            out["ml_inventory_id"] = prev["ml_inventory_id"]
        if (not out.get("variations_json") or out.get("variations_json") == "[]") and prev.get(
            "variations_json"
        ):
            out["variations_json"] = prev["variations_json"]
        out["sold_quantity"] = max(
            int(out.get("sold_quantity") or 0), int(prev.get("sold_quantity") or 0)
        )
        if not out.get("status") and prev.get("status"):
            out["status"] = prev["status"]
        merged[pid] = out
    return list(merged.values())


class MLFeedSyncService:
    """Pull do feed ML → banco local (fonte do dashboard /app)."""

    def _add_orders(self, raw: Any, seen: set, collected: List[Dict[str, Any]]) -> int:
        added = 0
        for o in _iter_order_dicts(raw):
            oid = str(o.get("id") or o.get("order_id") or o.get("external_id") or "")
            if not oid or oid in seen:
                continue
            seen.add(oid)
            collected.append(o)
            added += 1
        return added

    async def _page_orders_endpoint(self, seen: set, collected: List[Dict[str, Any]]) -> None:
        """Pagina /ml/orders (todas as chaves/status) e deduplica em collected."""
        offset = 0
        limit = ORDERS_MAX_LIMIT  # bridge 4MC: limit=100 → 400 (máx. 51)
        while True:
            page = await ml_feed_client.get_orders(offset=offset, limit=limit)
            batch = _iter_order_dicts(page)
            if not batch:
                break
            self._add_orders(batch, seen, collected)
            paging = page.get("paging") or {}
            total = int(paging.get("total") or 0)
            offset += limit
            if total and offset >= total:
                break
            if len(batch) < limit:
                break
            if offset > ORDERS_MAX_OFFSET:
                break
            # Respiro leve entre páginas (evita 429 no Render cold/hot)
            await asyncio.sleep(0.15)

    async def _enrich_orders_batch(
        self, orders: List[Dict[str, Any]], limit: int = ENRICH_ORDERS_LIMIT
    ) -> Dict[str, int]:
        """Enriquece os N pedidos mais recentes com /order + /shipment (rate-limit friendly)."""
        stats = {"orders_detail": 0, "shipments": 0, "errors": 0}
        if not orders or limit <= 0:
            return stats
        # Pedidos listados vêm do mais recente → primeiro; pega fatia inicial
        targets = orders[:limit]
        for raw in targets:
            oid = raw.get("id") or raw.get("order_id")
            if oid is None:
                continue
            try:
                await asyncio.sleep(ENRICH_DELAY_SEC)
                detail_payload = await ml_feed_client.get_order(oid)
                detail = detail_payload.get("order") if isinstance(detail_payload, dict) else None
                if isinstance(detail, dict):
                    # merge campos do detalhe sem perder o que a lista já tinha
                    for k, v in detail.items():
                        if v is not None and v != "" and v != {}:
                            raw[k] = v
                    raw["_enriched"] = True
                    stats["orders_detail"] += 1
                shipping = raw.get("shipping") if isinstance(raw.get("shipping"), dict) else {}
                ship_id = shipping.get("id") or raw.get("shipping_id")
                if ship_id:
                    await asyncio.sleep(ENRICH_DELAY_SEC)
                    ship_payload = await ml_feed_client.get_shipment(ship_id)
                    shipment = (
                        ship_payload.get("shipment")
                        if isinstance(ship_payload, dict)
                        else None
                    )
                    if isinstance(shipment, dict):
                        raw["_shipment"] = shipment
                        stats["shipments"] += 1
            except MLFeedClientError:
                stats["errors"] += 1
                continue
        return stats

    async def _enrich_items_batch(
        self, items: List[Dict[str, Any]], limit: int = ENRICH_ITEMS_LIMIT
    ) -> Dict[str, int]:
        """Puxa /item/:id para EAN/variações/estoque em amostra (não martela o catálogo inteiro)."""
        stats = {"items_detail": 0, "with_ean": 0, "errors": 0}
        if not items or limit <= 0:
            return stats
        # Preferir anúncios com id MLB real
        candidates: List[Dict[str, Any]] = []
        seen: set = set()
        for it in items:
            body = _unwrap_item_payload(it) if isinstance(it, dict) else {}
            iid = str(body.get("id") or it.get("id") or "")
            if not iid.startswith("MLB") or iid in seen:
                continue
            seen.add(iid)
            candidates.append(it)
            if len(candidates) >= limit:
                break
        for it in candidates:
            body = _unwrap_item_payload(it)
            iid = str(body.get("id") or "")
            try:
                await asyncio.sleep(ENRICH_DELAY_SEC)
                payload = await ml_feed_client.get_item(iid)
                detail = payload.get("item") if isinstance(payload, dict) else None
                if not isinstance(detail, dict):
                    continue
                # substitui stub/lista pelo detalhe completo
                if isinstance(it, dict) and "body" in it:
                    it["body"] = detail
                else:
                    it.clear()
                    it.update(detail)
                stats["items_detail"] += 1
                if _extract_ean(detail):
                    stats["with_ean"] += 1
            except MLFeedClientError:
                stats["errors"] += 1
                continue
        return stats

    async def _sync_questions_and_claims(self, ml_user_id: int = 0) -> Dict[str, int]:
        """Persiste perguntas/claims do bridge (merge; lista vazia não apaga cache)."""
        out = {"questions_synced": 0, "claims_synced": 0, "errors": 0}
        now = datetime.now()
        try:
            q_payload = await ml_feed_client.get_questions()
        except MLFeedClientError:
            q_payload = {}
            out["errors"] += 1
        try:
            c_payload = await ml_feed_client.get_claims()
        except MLFeedClientError:
            c_payload = {}
            out["errors"] += 1

        questions = []
        if isinstance(q_payload, dict):
            questions = q_payload.get("questions") or []
            if not ml_user_id:
                acc = q_payload.get("account") or {}
                try:
                    ml_user_id = int(acc.get("ml_user_id") or 0)
                except (TypeError, ValueError):
                    ml_user_id = 0
        claims = c_payload.get("claims") or [] if isinstance(c_payload, dict) else []

        async with async_session() as session:
            for q in questions:
                if not isinstance(q, dict) or q.get("id") is None:
                    continue
                answer = q.get("answer") if isinstance(q.get("answer"), dict) else {}
                from_user = q.get("from") if isinstance(q.get("from"), dict) else {}
                await session.merge(
                    MLQuestionDB(
                        id=str(q.get("id")),
                        ml_user_id=ml_user_id,
                        item_id=str(q.get("item_id") or ""),
                        item_title="",
                        text=str(q.get("text") or ""),
                        status=str(q.get("status") or "UNANSWERED"),
                        answer_text=str(answer.get("text") or ""),
                        from_user_id=str(from_user.get("id") or ""),
                        date_created=_parse_date(q.get("date_created")),
                    )
                )
                out["questions_synced"] += 1
            for c in claims:
                if not isinstance(c, dict):
                    continue
                cid = c.get("id") or c.get("claim_id")
                if cid is None:
                    continue
                await session.merge(
                    MLClaimDB(
                        id=str(cid),
                        ml_user_id=ml_user_id,
                        resource_id=str(
                            c.get("resource_id")
                            or c.get("order_id")
                            or c.get("resource")
                            or ""
                        ),
                        status=str(c.get("status") or ""),
                        type=str(c.get("type") or c.get("claim_type") or ""),
                        stage=str(c.get("stage") or ""),
                        reason_id=str(c.get("reason_id") or c.get("reason") or ""),
                        payload_json=json.dumps(c, ensure_ascii=False),
                        date_created=_parse_date(
                            c.get("date_created") or c.get("created_at")
                        ),
                        synced_at=now,
                    )
                )
                out["claims_synced"] += 1
            if out["questions_synced"] or out["claims_synced"]:
                await session.commit()
        return out

    async def _collect_orders(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Une feed + /ml/orders. summary.total_orders_paid é só métrica — NÃO filtra."""
        collected: List[Dict[str, Any]] = []
        seen: set = set()

        feed = await ml_feed_client.get_feed()
        # Sempre puxa /ml/orders (pode ter unpaid/recent/results mesmo com paid=0 no summary)
        await self._page_orders_endpoint(seen, collected)
        # Completa com qualquer pedido embutido no feed (orders / unpaid / recent / …)
        self._add_orders(feed, seen, collected)

        return collected, feed

    async def _page_items_status(
        self, status: Optional[str], seen: set, collected: List[Dict[str, Any]]
    ) -> None:
        offset = 0
        # Bridge 4MC estoura 500 com limit=50 em /items (active); 20 é estável.
        limit = 20
        # índice id -> posição em collected (permite upgrade stub → payload completo)
        index: Dict[str, int] = {
            str(it.get("id")): i
            for i, it in enumerate(collected)
            if isinstance(it, dict) and it.get("id")
        }

        while True:
            page = await ml_feed_client.get_items(offset=offset, limit=limit, status=status)
            batch = page.get("items") or page.get("results") or []
            if not batch:
                break
            for it in batch:
                if isinstance(it, str):
                    sid = str(it)
                    if sid not in seen:
                        seen.add(sid)
                        index[sid] = len(collected)
                        collected.append(
                            {
                                "id": sid,
                                "title": sid,
                                "price": 0,
                                "available_quantity": 0,
                                "status": status or "",
                            }
                        )
                    continue
                if not isinstance(it, dict):
                    continue
                body = it.get("body") if isinstance(it.get("body"), dict) else it
                iid = str(body.get("id") or it.get("id") or it.get("item_id") or "")
                if not iid:
                    continue
                # Garante status da query quando o payload não trouxer
                payload = it
                if status and not body.get("status") and not it.get("status"):
                    if body is it:
                        payload = {**it, "status": status}
                    else:
                        payload = {**it, "body": {**body, "status": status}}
                if iid in seen:
                    # Upgrade: substitui stub (só id) pelo anúncio completo
                    pos = index.get(iid)
                    if pos is not None:
                        prev = collected[pos]
                        prev_title = str(prev.get("title") or prev.get("id") or "")
                        is_stub = prev_title == str(prev.get("id") or "") and not prev.get(
                            "price"
                        )
                        if is_stub:
                            collected[pos] = payload
                    continue
                seen.add(iid)
                index[iid] = len(collected)
                collected.append(payload)
            paging = page.get("paging") or {}
            total = int(paging.get("total") or 0)
            offset += limit
            if total and offset >= total:
                break
            if len(batch) < limit:
                break
            if offset > 5000:
                break

    async def _collect_items(self) -> List[Dict[str, Any]]:
        """Puxa anúncios em status úteis. Preferir status explícitos (active/paused/…)."""
        collected: List[Dict[str, Any]] = []
        seen: set = set()
        # active primeiro (catálogo operacional); demais status completam o inventário
        for status in ("active", "paused", "under_review", "inactive", "closed"):
            try:
                await self._page_items_status(status, seen, collected)
            except MLFeedClientError:
                continue

        # Completa com sample de IDs do feed, se houver
        try:
            feed = await ml_feed_client.get_feed()
            for iid in feed.get("item_ids_sample") or []:
                sid = str(iid)
                if sid and sid not in seen:
                    seen.add(sid)
                    collected.append(
                        {"id": sid, "title": sid, "price": 0, "available_quantity": 0}
                    )
        except MLFeedClientError:
            pass

        return collected

    async def sync_all_real_data(self) -> dict:
        await init_db()
        stats: Dict[str, Any] = {
            "source": "mercadolivre_feed",
            "account": {},
            "summary": {},
            "statuses_synced": 0,
            "orders_synced": 0,
            "products_synced": 0,
            "questions_unanswered": 0,
            "questions_synced": 0,
            "claims_synced": 0,
            "enrichment": {},
        }

        try:
            orders_raw, feed = await self._collect_orders()
        except MLFeedClientError as exc:
            return {
                **stats,
                "ok": False,
                "error": str(exc),
            }

        account = feed.get("account") or {}
        summary = feed.get("summary") or {}
        stats["account"] = {
            "nickname": account.get("nickname"),
            "ml_user_id": account.get("ml_user_id"),
        }
        stats["summary"] = summary
        stats["questions_unanswered"] = int(
            summary.get("total_questions_unanswered")
            or len(feed.get("questions") or [])
            or 0
        )

        # Enrich só lote recente — NÃO detalhar os ~8k de uma vez (429 / tempo).
        enrich_orders = await self._enrich_orders_batch(orders_raw, ENRICH_ORDERS_LIMIT)

        try:
            items_raw = await self._collect_items()
        except MLFeedClientError:
            items_raw = []

        enrich_items = await self._enrich_items_batch(items_raw, ENRICH_ITEMS_LIMIT)
        stats["enrichment"] = {**enrich_orders, **enrich_items}

        try:
            ml_uid = int(account.get("ml_user_id") or 0)
        except (TypeError, ValueError):
            ml_uid = 0
        qc = await self._sync_questions_and_claims(ml_uid)
        stats["questions_synced"] = qc.get("questions_synced", 0)
        stats["claims_synced"] = qc.get("claims_synced", 0)

        normalized_orders = []
        for o in orders_raw:
            n = _normalize_order(o)
            if n:
                normalized_orders.append(n)

        normalized_items = []
        for it in items_raw:
            n = _normalize_item(it)
            if n:
                normalized_items.append(n)

        # Completa catálogo com itens presentes nos pedidos (título/SKU/preço unitário)
        from_orders = _products_from_orders(orders_raw)
        normalized_items = _merge_products(normalized_items, from_orders)

        # Não apagar o cache local se o feed voltar vazio (bridge offline / janela sem dados).
        async with async_session() as session:
            existing_orders = (
                await session.execute(select(func.count()).select_from(RealOrderDB))
            ).scalar_one()
            existing_products = (
                await session.execute(select(func.count()).select_from(RealProductDB))
            ).scalar_one()

            if not normalized_orders and not normalized_items and (existing_orders or existing_products):
                stats["orders_synced"] = 0
                stats["products_synced"] = 0
                stats["statuses_synced"] = 0
                stats["ok"] = True
                stats["cache_preserved"] = True
                stats["orders_in_db"] = int(existing_orders or 0)
                stats["products_in_db"] = int(existing_products or 0)
                stats["warning"] = (
                    "Feed ML retornou 0 pedidos/itens — cache SQLite preservado."
                )
                return stats

            # Preserva filas BaseLinker (import read-only) — nunca sobrescrever com buckets ML.
            from src.infrastructure.baselinker_status_import import (
                META_KEY as _BL_META_KEY,
            )

            bl_meta = await session.get(SyncMetaDB, _BL_META_KEY)
            existing_status_rows = (
                await session.execute(select(RealOrderStatusDB))
            ).scalars().all()
            preserved_bl = [
                {"id": s.id, "name": s.name, "color": s.color}
                for s in existing_status_rows
            ]
            use_bl_statuses = bool(bl_meta and (bl_meta.value or "").strip()) or (
                len(preserved_bl) > 7
                or ({s["id"] for s in preserved_bl} != {1, 2, 3, 4, 5, 6, 7} and len(preserved_bl) > 0)
            )
            if use_bl_statuses and not preserved_bl:
                use_bl_statuses = False

            await session.execute(delete(RealOrderStatusDB))
            await session.execute(delete(RealOrderDB))
            await session.execute(delete(RealProductDB))

            if use_bl_statuses:
                default = preserved_bl[0]
                by_name = {s["name"].lower(): s for s in preserved_bl}
                # Preferência: nome BL contendo "novo" / "pago" / match exato ML
                preferred = None
                for s in preserved_bl:
                    nl = s["name"].lower()
                    if "novo" in nl or "new" in nl:
                        preferred = s
                        break
                if not preferred:
                    for s in preserved_bl:
                        if "pago" in s["name"].lower() or "paid" in s["name"].lower():
                            preferred = s
                            break
                default = preferred or default
                for o in normalized_orders:
                    match = by_name.get((o.get("status_name") or "").lower())
                    if match:
                        o["status_id"] = match["id"]
                        o["status_name"] = match["name"]
                    else:
                        o["status_id"] = default["id"]
                        o["status_name"] = default["name"]
                for s in preserved_bl:
                    count = sum(
                        1
                        for o in normalized_orders
                        if o["status_id"] == s["id"] or o["status_name"] == s["name"]
                    )
                    session.add(
                        RealOrderStatusDB(
                            id=s["id"], name=s["name"], color=s["color"], count=count
                        )
                    )
                stats["statuses_synced"] = len(preserved_bl)
                stats["statuses_source"] = "baselinker_preserved"
            else:
                for sid, name, color in STATUS_CATALOG:
                    count = sum(1 for o in normalized_orders if o["status_name"] == name)
                    session.add(
                        RealOrderStatusDB(id=sid, name=name, color=color, count=count)
                    )
                stats["statuses_synced"] = len(STATUS_CATALOG)
                stats["statuses_source"] = "ml_catalog"

            for o in normalized_orders:
                session.add(RealOrderDB(**o))
            stats["orders_synced"] = len(normalized_orders)

            for p in normalized_items:
                session.add(RealProductDB(**p))
            stats["products_synced"] = len(normalized_items)

            now = datetime.now()
            meta_payload = {
                "source": "mercadolivre_feed",
                "account": stats["account"],
                "summary": summary,
                "orders_synced": stats["orders_synced"],
                "products_synced": stats["products_synced"],
                "statuses_synced": stats["statuses_synced"],
                "questions_synced": stats.get("questions_synced", 0),
                "claims_synced": stats.get("claims_synced", 0),
                "enrichment": stats.get("enrichment") or {},
                "feed_timestamp": feed.get("timestamp"),
                "synced_at": now.isoformat(timespec="seconds"),
            }
            await session.merge(
                SyncMetaDB(
                    key="ml_feed_last_sync",
                    value=json.dumps(meta_payload, ensure_ascii=False),
                    updated_at=now,
                )
            )

            await session.commit()

        stats["ok"] = True
        stats["feed_timestamp"] = feed.get("timestamp")
        stats["feed_origem"] = feed.get("origem")
        stats["synced_at"] = datetime.now().isoformat(timespec="seconds")
        stats["cache"] = "sqlite"
        return stats

    async def get_last_sync_meta(self) -> Dict[str, Any]:
        """Lê metadados da última sync — só SQLite, zero rede."""
        await init_db()
        async with async_session() as session:
            row = await session.get(SyncMetaDB, "ml_feed_last_sync")
            order_count = (
                await session.execute(select(func.count()).select_from(RealOrderDB))
            ).scalar() or 0
            product_count = (
                await session.execute(select(func.count()).select_from(RealProductDB))
            ).scalar() or 0
        if not row:
            return {
                "has_sync": False,
                "synced_at": None,
                "orders_in_db": int(order_count),
                "products_in_db": int(product_count),
                "source": None,
            }
        try:
            payload = json.loads(row.value or "{}")
        except json.JSONDecodeError:
            payload = {}
        return {
            "has_sync": True,
            "synced_at": payload.get("synced_at")
            or (row.updated_at.isoformat(timespec="seconds") if row.updated_at else None),
            "account": payload.get("account") or {},
            "summary": payload.get("summary") or {},
            "orders_synced": payload.get("orders_synced"),
            "products_synced": payload.get("products_synced"),
            "orders_in_db": int(order_count),
            "products_in_db": int(product_count),
            "source": payload.get("source") or "mercadolivre_feed",
            "feed_timestamp": payload.get("feed_timestamp"),
        }


# Mantém o nome sync_service usado pelos routers — agora aponta para o feed ML.
sync_service = MLFeedSyncService()