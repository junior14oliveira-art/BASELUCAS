"""Macro Fiscal — orquestra ML (SQLite) → Pedido de Venda Bling → (opcional) NF-e.

Fluxo:
  1. Lê RealOrderDB (cache ML)
  2. Monta payload POST /pedidos/vendas
  3. Se BLING_READ_ONLY → não chama API; devolve preview + status skipped_read_only
  4. Se ok → grava bling_pedido_id
  5. Se NFE_EMIT_ENABLED + allow_nfe → POST /nfe; senão nfe_skipped

Testar sem emitir NF real:
  - Defaults: BLING_READ_ONLY=true, NFE_EMIT_ENABLED=false
  - POST /api/v1/bling/orders/{id}/push?dry_run=true → só preview do payload
  - Homologar pedido (sem NF): BLING_READ_ONLY=false, NFE_EMIT_ENABLED=false
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select

from src.config import settings
from src.infrastructure.bling_client import (
    BlingClient,
    BlingError,
    BlingNfeDisabledError,
    BlingReadOnlyError,
    bling_read_only,
    is_app_configured,
    nfe_emit_enabled,
)
from src.infrastructure.database import BlingConfigDB, RealOrderDB, async_session, init_db

# Status ML / filas locais que consideramos "pagamento confirmado"
_PAID_HINTS = (
    "paid",
    "pago",
    "pagos",
    "confirmado",
    "payment_required",  # bridge às vezes rotula assim pós-pago no mapa
)


def _digits(doc: str) -> str:
    return re.sub(r"\D+", "", doc or "")


def order_looks_paid(order: RealOrderDB) -> bool:
    """Heurística: status local / enrichment / valor > 0."""
    name = (order.status_name or "").lower()
    if any(h in name for h in ("pago", "pagos", "paid", "confirmado", "novos pedidos")):
        # "Novos pedidos" no pipeline = entrada pós-venda paga (ver skill)
        if "aguardando pagamento" in name or "unpaid" in name:
            return False
        if "novos pedidos" in name or "pago" in name or "pagos" in name or "paid" in name:
            return True
    try:
        enrich = json.loads(order.enrichment_json or "{}")
    except Exception:
        enrich = {}
    ml_status = str(enrich.get("ml_status") or enrich.get("status") or "").lower()
    if ml_status in ("paid", "confirmed"):
        return True
    # Fallback: pedido ML com valor e sem flag unpaid
    if float(order.total_amount or 0) > 0 and "unpaid" not in name and "aguardando pagamento" not in name:
        return True
    return False


async def get_bling_config(account_key: Optional[str] = None) -> Optional[BlingConfigDB]:
    await init_db()
    key = (account_key or settings.BLING_ACCOUNT_KEY or "4mc").strip() or "4mc"
    async with async_session() as session:
        result = await session.execute(
            select(BlingConfigDB).where(BlingConfigDB.account_key == key)
        )
        row = result.scalar_one_or_none()
        if row:
            return row
        # Fallback: qualquer conta ativa com token
        result = await session.execute(
            select(BlingConfigDB).where(BlingConfigDB.is_active == True)  # noqa: E712
        )
        return result.scalars().first()


async def save_bling_tokens(
    token_data: Dict[str, Any],
    *,
    account_key: Optional[str] = None,
    account_label: Optional[str] = None,
) -> BlingConfigDB:
    await init_db()
    key = (account_key or settings.BLING_ACCOUNT_KEY or "4mc").strip() or "4mc"
    expires_at = float(token_data.get("expires_at") or 0.0)
    if not expires_at and token_data.get("expires_in"):
        expires_at = time.time() + float(token_data["expires_in"])

    async with async_session() as session:
        result = await session.execute(
            select(BlingConfigDB).where(BlingConfigDB.account_key == key)
        )
        row = result.scalar_one_or_none()
        now = datetime.now()
        if not row:
            row = BlingConfigDB(
                account_key=key,
                account_label=account_label or f"Bling {key}",
                connected_at=now,
            )
            session.add(row)
        row.access_token = str(token_data.get("access_token") or "")
        row.refresh_token = str(token_data.get("refresh_token") or row.refresh_token or "")
        row.expires_at = expires_at
        row.scopes = str(token_data.get("scope") or token_data.get("scopes") or row.scopes or "")
        row.token_type = str(token_data.get("token_type") or "Bearer")
        row.is_active = True
        row.updated_at = now
        row.last_error = ""
        if not row.connected_at:
            row.connected_at = now
        if account_label:
            row.account_label = account_label
        await session.commit()
        await session.refresh(row)
        return row


async def build_client(account_key: Optional[str] = None) -> Tuple[Optional[BlingClient], Optional[BlingConfigDB]]:
    cfg = await get_bling_config(account_key)
    if not cfg or not (cfg.access_token or "").strip():
        return None, cfg

    key = cfg.account_key

    async def _persist(data: Dict[str, Any]) -> None:
        await save_bling_tokens(data, account_key=key)

    client = BlingClient(
        access_token=cfg.access_token,
        refresh_token=cfg.refresh_token,
        expires_at=cfg.expires_at,
        on_token_refresh=_persist,
    )
    return client, cfg


def build_pedido_venda_payload(order: RealOrderDB) -> Dict[str, Any]:
    """Monta JSON compatível com POST /pedidos/vendas (API v3)."""
    try:
        items_raw = json.loads(order.items_json or "[]")
    except Exception:
        items_raw = []
    if not isinstance(items_raw, list):
        items_raw = []

    try:
        addr = json.loads(order.shipping_address_json or "{}")
    except Exception:
        addr = {}
    if not isinstance(addr, dict):
        addr = {}

    doc = _digits(order.buyer_doc or "")
    tipo_pessoa = "J" if len(doc) > 11 else "F"
    data_pedido = (order.created_at or datetime.now()).strftime("%Y-%m-%d")

    itens: List[Dict[str, Any]] = []
    for it in items_raw:
        if not isinstance(it, dict):
            continue
        qty = float(it.get("quantity") or it.get("qty") or 1)
        price = float(it.get("price") or it.get("unit_price") or it.get("valor") or 0)
        sku = str(it.get("sku") or it.get("seller_sku") or it.get("codigo") or "")
        desc = str(it.get("name") or it.get("title") or it.get("descricao") or "Item ML")
        itens.append(
            {
                "codigo": sku or str(it.get("item_id") or it.get("id") or "ML-ITEM"),
                "descricao": desc[:120],
                "unidade": "UN",
                "quantidade": qty,
                "valor": price,
            }
        )
    if not itens:
        itens.append(
            {
                "codigo": order.external_id or order.id,
                "descricao": f"Pedido ML {order.external_id or order.id}",
                "unidade": "UN",
                "quantidade": 1,
                "valor": float(order.total_amount or 0),
            }
        )

    contato: Dict[str, Any] = {
        "nome": (order.customer_name or "Cliente Mercado Livre")[:60],
        "tipoPessoa": tipo_pessoa,
        "email": order.customer_email or "",
    }
    if doc:
        contato["numeroDocumento"] = doc
    if order.customer_phone:
        contato["telefone"] = order.customer_phone

    # Endereço (quando bridge 4MC enriquecido)
    end: Dict[str, Any] = {}
    if addr.get("address_line") or addr.get("street_name"):
        end["endereco"] = str(addr.get("address_line") or addr.get("street_name") or "")[:100]
    if addr.get("street_number"):
        end["numero"] = str(addr.get("street_number"))[:10]
    if addr.get("comment") or addr.get("address_line_2"):
        end["complemento"] = str(addr.get("comment") or addr.get("address_line_2") or "")[:50]
    if addr.get("neighborhood") or addr.get("city_neighborhood"):
        end["bairro"] = str(addr.get("neighborhood") or addr.get("city_neighborhood") or "")[:50]
    if addr.get("city") or addr.get("city_name"):
        end["municipio"] = str(addr.get("city") or addr.get("city_name") or "")[:50]
    if addr.get("state") or addr.get("state_id"):
        end["uf"] = str(addr.get("state") or addr.get("state_id") or "")[:2]
    if addr.get("zip_code") or addr.get("zipcode"):
        end["cep"] = _digits(str(addr.get("zip_code") or addr.get("zipcode") or ""))
    if end:
        contato["endereco"] = end

    payload: Dict[str, Any] = {
        "data": data_pedido,
        "dataSaida": data_pedido,
        "numeroPedidoCompra": str(order.external_id or order.id)[:30],
        "observacoes": f"Pedido Mercado Livre {order.id} | canal={order.channel_name}",
        "contato": contato,
        "itens": itens,
        "transporte": {
            "fretePorConta": 2,  # 2 = destinatário / conta terceira (ME típico)
            "transportePorConta": 1,
        },
    }
    return payload


def build_nfe_payload(order: RealOrderDB, bling_pedido_id: str) -> Dict[str, Any]:
    """Payload mínimo POST /nfe a partir do pedido de venda Bling."""
    natureza_id = int(getattr(settings, "BLING_NATUREZA_OPERACAO_ID", 0) or 0)
    body: Dict[str, Any] = {
        "tipo": 1,  # 1 = saída
        "finalidade": 1,
        "pedidoVenda": {"id": int(bling_pedido_id) if str(bling_pedido_id).isdigit() else bling_pedido_id},
        "observacoes": f"NF-e automática Base Antigravity — ML {order.external_id or order.id}",
    }
    if natureza_id > 0:
        body["naturezaOperacao"] = {"id": natureza_id}
    return body


def integration_ui_status() -> Dict[str, Any]:
    """Status honesto para tiles / GET /bling/status."""
    app_ok = is_app_configured()
    return {
        "app_configured": app_ok,
        "bling_read_only": bling_read_only(),
        "nfe_emit_enabled": nfe_emit_enabled(),
        "auto_push_on_paid": bool(getattr(settings, "BLING_AUTO_PUSH_ON_PAID", True)),
        "account_key": settings.BLING_ACCOUNT_KEY,
        "redirect_uri": settings.BLING_REDIRECT_URI,
        # Preenchido pelo router com token do DB
        "ui_status": "awaiting_credentials" if not app_ok else "configured",
        "ui_label": "Aguardando credenciais" if not app_ok else "Configurado",
    }


async def push_order_to_bling(
    order_id: str,
    *,
    dry_run: bool = False,
    force: bool = False,
    emit_nfe: bool = True,
    account_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Cria Pedido de Venda no Bling a partir do pedido ML local. Opcionalmente comanda NF-e."""
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            return {"ok": False, "error": "Pedido não encontrado no SQLite local.", "order_id": order_id}

        if order.bling_pedido_id and not force and not dry_run:
            return {
                "ok": True,
                "skipped": True,
                "reason": "already_pushed",
                "order_id": order_id,
                "bling_pedido_id": order.bling_pedido_id,
                "bling_status": order.bling_status,
                "nfe_emit_enabled": nfe_emit_enabled(),
            }

        payload = build_pedido_venda_payload(order)
        paid = order_looks_paid(order)

        base_out: Dict[str, Any] = {
            "ok": True,
            "order_id": order_id,
            "external_id": order.external_id,
            "paid_detected": paid,
            "dry_run": dry_run,
            "bling_read_only": bling_read_only(),
            "nfe_emit_enabled": nfe_emit_enabled(),
            "pedido_payload": payload,
        }

        if dry_run:
            nfe_preview = None
            if emit_nfe:
                nfe_preview = build_nfe_payload(order, bling_pedido_id="DRY_RUN")
            order.bling_status = "dry_run"
            order.bling_last_error = ""
            await session.commit()
            return {
                **base_out,
                "message": "Dry-run: payload montado, nenhuma chamada à API Bling.",
                "nfe_payload_preview": nfe_preview,
                "bling_status": "dry_run",
            }

        if not is_app_configured():
            order.bling_status = "awaiting_credentials"
            order.bling_last_error = "BLING_CLIENT_ID/SECRET ausentes"
            await session.commit()
            return {
                **base_out,
                "ok": False,
                "error": "App Bling não configurado (.env).",
                "ui_status": "awaiting_credentials",
                "bling_status": "awaiting_credentials",
            }

        client, cfg = await build_client(account_key)
        if not client:
            order.bling_status = "awaiting_oauth"
            order.bling_last_error = "Sem token OAuth — GET /api/v1/bling/auth"
            await session.commit()
            return {
                **base_out,
                "ok": False,
                "error": "Credenciais de app ok, mas falta OAuth. Chame GET /api/v1/bling/auth.",
                "ui_status": "configured",
                "bling_status": "awaiting_oauth",
            }

        # READ_ONLY: não finge sucesso remoto — grava skipped + preview
        if bling_read_only():
            order.bling_status = "skipped_read_only"
            order.bling_last_error = ""
            order.bling_pushed_at = datetime.now()
            await session.commit()
            return {
                **base_out,
                "ok": True,
                "skipped": True,
                "reason": "bling_read_only",
                "message": (
                    "BLING_READ_ONLY=true — Pedido de Venda NÃO enviado. "
                    "Payload em pedido_payload. Para criar no Bling: BLING_READ_ONLY=false "
                    "(mantenha NFE_EMIT_ENABLED=false)."
                ),
                "bling_status": "skipped_read_only",
                "account_key": cfg.account_key if cfg else None,
            }

        try:
            resp = await client.create_pedido_venda(payload, allow_write=True)
        except BlingReadOnlyError as exc:
            order.bling_status = "skipped_read_only"
            order.bling_last_error = str(exc.message)
            await session.commit()
            return {**base_out, "ok": False, "error": exc.message, "bling_status": "skipped_read_only"}
        except BlingError as exc:
            order.bling_status = "error"
            order.bling_last_error = exc.message
            await session.commit()
            return {
                **base_out,
                "ok": False,
                "error": exc.message,
                "bling_payload": exc.payload,
                "bling_status": "error",
            }

        data = resp.get("data") if isinstance(resp.get("data"), dict) else resp
        pedido_id = ""
        if isinstance(data, dict):
            pedido_id = str(data.get("id") or (data.get("pedido") or {}).get("id") or "")
        if not pedido_id and isinstance(resp, dict):
            pedido_id = str(resp.get("id") or "")

        order.bling_pedido_id = pedido_id
        order.bling_status = "pedido_criado"
        order.bling_last_error = ""
        order.bling_pushed_at = datetime.now()
        await session.commit()

        out: Dict[str, Any] = {
            **base_out,
            "bling_pedido_id": pedido_id,
            "bling_response": resp,
            "bling_status": "pedido_criado",
            "message": f"Pedido de Venda criado no Bling (id={pedido_id or '?'}).",
        }

        if not emit_nfe:
            out["nfe"] = {"skipped": True, "reason": "emit_nfe=false"}
            return out

        if not nfe_emit_enabled():
            order.bling_status = "nfe_skipped_disabled"
            await session.commit()
            out["bling_status"] = "nfe_skipped_disabled"
            out["nfe"] = {
                "skipped": True,
                "reason": "nfe_emit_enabled=false",
                "message": "Pedido criado; NF-e NÃO comandada (NFE_EMIT_ENABLED=false).",
                "nfe_payload_preview": build_nfe_payload(order, pedido_id or "0"),
            }
            return out

        if not pedido_id:
            out["nfe"] = {"skipped": True, "reason": "missing_pedido_id"}
            return out

        nfe_body = build_nfe_payload(order, pedido_id)
        try:
            nfe_resp = await client.create_nfe(nfe_body, allow_write=True, allow_nfe=True)
        except BlingNfeDisabledError as exc:
            order.bling_status = "nfe_skipped_disabled"
            await session.commit()
            out["nfe"] = {"skipped": True, "error": exc.message}
            out["bling_status"] = "nfe_skipped_disabled"
            return out
        except BlingError as exc:
            order.bling_status = "nfe_error"
            order.bling_last_error = exc.message
            await session.commit()
            out["ok"] = True  # pedido ok; NF falhou
            out["nfe"] = {"ok": False, "error": exc.message, "payload": exc.payload}
            out["bling_status"] = "nfe_error"
            return out

        nfe_data = nfe_resp.get("data") if isinstance(nfe_resp.get("data"), dict) else nfe_resp
        nfe_id = ""
        if isinstance(nfe_data, dict):
            nfe_id = str(nfe_data.get("id") or "")
        order.bling_nfe_id = nfe_id
        order.bling_status = "nfe_solicitada"
        await session.commit()
        out["bling_status"] = "nfe_solicitada"
        out["nfe"] = {"ok": True, "bling_nfe_id": nfe_id, "response": nfe_resp}
        out["message"] = f"Pedido {pedido_id} + NF-e solicitada ({nfe_id or 'id pendente'})."
        return out


async def auto_push_paid_orders(*, limit: int = 25) -> Dict[str, Any]:
    """Após sync ML: empurra pedidos pagos ainda sem bling_pedido_id."""
    if not bool(getattr(settings, "BLING_AUTO_PUSH_ON_PAID", True)):
        return {"ok": True, "skipped": True, "reason": "auto_push_disabled"}

    await init_db()
    results: List[Dict[str, Any]] = []
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).limit(500))
        orders = list(result.scalars().all())

    retryable = {"", "error", "nfe_error", "awaiting_oauth", "awaiting_credentials"}
    if not bling_read_only():
        # Quando liberar escrita, reprocessa os que só tinham sido marcados em dry/read-only
        retryable |= {"skipped_read_only", "dry_run", "nfe_skipped_disabled"}

    candidates = [
        o
        for o in orders
        if order_looks_paid(o)
        and not (o.bling_pedido_id or "").strip()
        and (o.bling_status or "") in retryable
    ][:limit]

    for o in candidates:
        res = await push_order_to_bling(o.id, dry_run=False, emit_nfe=True)
        results.append(
            {
                "order_id": o.id,
                "ok": res.get("ok"),
                "bling_status": res.get("bling_status"),
                "skipped": res.get("skipped"),
                "reason": res.get("reason") or res.get("error"),
            }
        )

    return {
        "ok": True,
        "candidates": len(candidates),
        "processed": len(results),
        "bling_read_only": bling_read_only(),
        "nfe_emit_enabled": nfe_emit_enabled(),
        "results": results,
    }
