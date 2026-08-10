"""Etapa 3 — Gatilho da Logística: webhook Bling NF-e → billing_info ML → ZPL engatilhado.

Fluxo:
  1. ACK do webhook (router) + log em BlingNfeWebhookEventDB
  2. Resolver chave de acesso (payload ou GET /nfe/{id} via Etapa 2)
  3. Localizar RealOrderDB (bling_nfe_id / bling_pedido_id / order_id explícito)
  4. Injetar chave no ML billing_info — **gated** se ML_READ_ONLY=true
  5. Baixar ZPL (GET /shipment_labels?response_type=zpl2) em background
  6. Engatilhar: zpl_armed + zpl_content (+ arquivo em ZPL_LABELS_DIR)
  7. Status local: "Aguardando Nota" → "Pronto para Bipagem"

Não imprime (CUPS/USB = Etapa 4 / expedition).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import or_, select

from src.config import API_ROOT, settings
from src.infrastructure.bling_client import BlingError
from src.infrastructure.bling_service import build_client as build_bling_client
from src.infrastructure.database import (
    BlingNfeWebhookEventDB,
    RealOrderDB,
    async_session,
    init_db,
)
from src.infrastructure.mercadolivre_client import (
    MercadoLivreError,
    MercadoLivreReadOnlyError,
)
from src.infrastructure.ml_shipping_labels import evaluate_production_gate, get_active_ml_account
from src.infrastructure.ml_sync_service import build_client as build_ml_client

STATUS_AGUARDANDO_NOTA = "Aguardando Nota"
STATUS_PRONTO_BIPAGEM = "Pronto para Bipagem"

_AUTHORIZED_HINTS = (
    "autorizada",
    "autorizado",
    "approved",
    "authorized",
    "5",  # situação Bling frequente = Autorizada
    "6",
)


def zpl_labels_dir() -> Path:
    raw = (settings.ZPL_LABELS_DIR or "data/zpl_labels").strip()
    path = Path(raw)
    if not path.is_absolute():
        path = API_ROOT / path
    path.mkdir(parents=True, exist_ok=True)
    return path


def _digits(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def extract_nfe_fields(payload: Dict[str, Any]) -> Dict[str, str]:
    """Extrai id NF-e, chave, pedido e evento de formatos comuns do Bling v3."""
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    if not isinstance(data, dict):
        data = {}

    event = str(
        payload.get("event")
        or payload.get("eventName")
        or payload.get("tipo")
        or data.get("event")
        or "nfe.status.changed"
    )

    nfe_id = str(
        data.get("id")
        or data.get("nfeId")
        or data.get("notaFiscalId")
        or payload.get("nfe_id")
        or payload.get("id")
        or ""
    ).strip()

    chave = str(
        data.get("chaveAcesso")
        or data.get("chave_acesso")
        or data.get("access_key")
        or data.get("nfe_access_key")
        or payload.get("chaveAcesso")
        or payload.get("nfe_access_key")
        or ""
    ).strip()
    chave = _digits(chave) or chave

    order_hint = str(
        data.get("order_id")
        or data.get("ml_order_id")
        or payload.get("order_id")
        or ""
    ).strip()

    pedido = data.get("pedido") if isinstance(data.get("pedido"), dict) else {}
    bling_pedido = str(
        pedido.get("id")
        or data.get("pedidoId")
        or data.get("idPedidoVenda")
        or payload.get("bling_pedido_id")
        or ""
    ).strip()

    situacao = str(
        data.get("situacao")
        or data.get("status")
        or data.get("situacaoNome")
        or payload.get("situacao")
        or ""
    ).strip()

    return {
        "event": event,
        "bling_nfe_id": nfe_id,
        "nfe_access_key": chave,
        "order_id_hint": order_hint,
        "bling_pedido_id": bling_pedido,
        "situacao": situacao,
    }


def situacao_autorizada(situacao: str, payload: Dict[str, Any]) -> bool:
    s = (situacao or "").lower()
    if any(h in s for h in _AUTHORIZED_HINTS if len(h) > 1) or s in _AUTHORIZED_HINTS:
        return True
    # Se o payload já traz chave de 44 dígitos, assume SEFAZ ok
    fields = extract_nfe_fields(payload)
    key = fields.get("nfe_access_key") or ""
    return len(_digits(key)) >= 44


async def resolve_nfe_access_key(
    *,
    bling_nfe_id: str,
    chave_payload: str,
) -> Tuple[str, Dict[str, Any]]:
    """Usa chave do webhook ou GET /nfe/{id} (OAuth Etapa 2)."""
    if len(_digits(chave_payload)) >= 44:
        return _digits(chave_payload), {"source": "webhook_payload"}

    if not bling_nfe_id:
        return "", {"source": "missing", "error": "Sem bling_nfe_id nem chave no payload"}

    client, _cfg = await build_bling_client()
    if not client:
        return "", {
            "source": "bling_get_skipped",
            "error": "Sem token Bling (conclua OAuth Etapa 2) — informe chaveAcesso no webhook para testar.",
        }
    try:
        raw = await client.get_nfe(bling_nfe_id)
    except BlingError as exc:
        return "", {"source": "bling_get_error", "error": exc.message, "status_code": exc.status_code}

    data = raw.get("data") if isinstance(raw.get("data"), dict) else raw
    if not isinstance(data, dict):
        data = {}
    chave = str(
        data.get("chaveAcesso")
        or data.get("chave_acesso")
        or ((data.get("notaFiscal") or {}) if isinstance(data.get("notaFiscal"), dict) else {}).get(
            "chaveAcesso"
        )
        or ""
    ).strip()
    chave = _digits(chave) or chave
    return chave, {"source": "bling_get_nfe", "nfe_preview_keys": list(data.keys())[:20]}


async def find_order_for_nfe(
    *,
    bling_nfe_id: str = "",
    bling_pedido_id: str = "",
    order_id_hint: str = "",
    nfe_access_key: str = "",
) -> Optional[RealOrderDB]:
    await init_db()
    async with async_session() as session:
        if order_id_hint:
            row = await session.get(RealOrderDB, order_id_hint)
            if row:
                return row
            result = await session.execute(
                select(RealOrderDB).where(
                    or_(
                        RealOrderDB.external_id == order_id_hint,
                        RealOrderDB.id == order_id_hint,
                    )
                )
            )
            row = result.scalars().first()
            if row:
                return row

        clauses = []
        if bling_nfe_id:
            clauses.append(RealOrderDB.bling_nfe_id == str(bling_nfe_id))
        if bling_pedido_id:
            clauses.append(RealOrderDB.bling_pedido_id == str(bling_pedido_id))
        if nfe_access_key:
            clauses.append(RealOrderDB.nfe_access_key == nfe_access_key)
        if clauses:
            result = await session.execute(select(RealOrderDB).where(or_(*clauses)))
            row = result.scalars().first()
            if row:
                return row
    return None


async def inject_billing_info_gated(order: RealOrderDB, access_key: str) -> Dict[str, Any]:
    """POST billing_info no ML — respeita ML_READ_ONLY (stub/gated documentado)."""
    if settings.ML_READ_ONLY:
        return {
            "status": "gated_read_only",
            "ml_read_only": True,
            "message": (
                "ML_READ_ONLY=true — injeção em billing_info NÃO enviada ao ML. "
                "Chave gravada só no SQLite. Homologar: ML_READ_ONLY=false."
            ),
            "order_id": order.id,
            "endpoint": f"POST /orders/{order.id}/billing_info",
        }

    account = await get_active_ml_account()
    if not account or not (account.access_token or "").strip():
        return {
            "status": "error",
            "ml_read_only": False,
            "message": "Sem conta ML OAuth ativa para injetar billing_info.",
        }

    client = await build_ml_client(account)
    try:
        resp = await client.inject_nfe_billing_info(order.id, access_key, allow_write=True)
        return {"status": "ok", "ml_read_only": False, "response": resp}
    except MercadoLivreReadOnlyError as exc:
        return {"status": "gated_read_only", "ml_read_only": True, "message": exc.message}
    except MercadoLivreError as exc:
        return {
            "status": "error",
            "ml_read_only": False,
            "message": exc.message,
            "status_code": exc.status_code,
            "payload": exc.payload,
        }


async def download_and_arm_zpl(order: RealOrderDB) -> Dict[str, Any]:
    """Baixa ZPL do Mercado Envios e engatilha (disco + zpl_armed/zpl_content)."""
    shipment_id = (order.shipping_id or "").strip()
    account = await get_active_ml_account()
    gate = evaluate_production_gate(
        has_oauth=account is not None,
        has_token=bool(account and (account.access_token or "").strip()),
        shipment_id=shipment_id,
        shipping_status=order.shipping_status or "",
    )
    if not gate.allowed:
        return {
            "status": "gated",
            "zpl_status": "gated",
            "armed": False,
            **gate.as_detail(),
        }

    assert account is not None
    client = await build_ml_client(account)
    try:
        content = await client.get_shipment_labels([shipment_id], response_type="zpl2")
    except MercadoLivreError as exc:
        return {
            "status": "error",
            "zpl_status": "error",
            "armed": False,
            "message": exc.message,
            "status_code": exc.status_code,
        }

    if isinstance(content, bytes):
        text = content.decode("utf-8", errors="replace")
    else:
        text = str(content or "")

    if not text.strip():
        return {"status": "error", "zpl_status": "error", "armed": False, "message": "ZPL vazio"}

    fname = f"{order.id}_{shipment_id}.zpl"
    path = zpl_labels_dir() / fname
    path.write_text(text, encoding="utf-8")

    return {
        "status": "ready",
        "zpl_status": "ready",
        "armed": True,
        "zpl_path": str(path),
        "zpl_content": text,
        "bytes": len(content) if isinstance(content, (bytes, bytearray)) else len(text.encode()),
    }


def _should_flip_status(current: str, unlock: bool) -> bool:
    if not unlock:
        return False
    name = (current or "").strip()
    if not name or name == STATUS_AGUARDANDO_NOTA:
        return True
    # Também libera se ainda estiver em filas fiscais típicas
    low = name.lower()
    return "aguardando nota" in low or "aguardando nf" in low or "sem nota" in low


async def apply_order_unlock(
    order_id: str,
    *,
    access_key: str,
    bling_nfe_id: str = "",
    billing_result: Dict[str, Any],
    zpl_result: Dict[str, Any],
) -> Dict[str, Any]:
    await init_db()
    async with async_session() as session:
        order = await session.get(RealOrderDB, order_id)
        if not order:
            return {"ok": False, "error": "order_not_found"}

        order.nfe_access_key = access_key
        if bling_nfe_id:
            order.bling_nfe_id = str(bling_nfe_id)
        order.bling_status = "nfe_autorizada"

        inj = str(billing_result.get("status") or "")
        order.ml_billing_inject_status = inj or "pending"

        zst = str(zpl_result.get("zpl_status") or zpl_result.get("status") or "")
        order.zpl_status = zst

        armed = bool(zpl_result.get("armed"))
        zpl_text = (zpl_result.get("zpl_content") or "").strip()
        zpl_path = (zpl_result.get("zpl_path") or "").strip()

        if armed and zpl_text:
            order.zpl_armed = True
            order.zpl_content = zpl_text
            order.zpl_path = zpl_path
            order.zpl_ready_at = datetime.now()
        elif settings.LOGISTICS_UNLOCK_ON_NFE_KEY and access_key:
            # Chave SEFAZ ok mas ZPL ainda gated (ex.: billing_info não injetado).
            # Não inventa ZPL falso — Etapa 4 checa zpl_armed.
            if not order.zpl_armed:
                order.zpl_status = order.zpl_status or "pending_ml_label"

        prev_status = order.status_name
        unlocked = False
        if armed or (
            settings.LOGISTICS_UNLOCK_ON_NFE_KEY
            and access_key
            and inj in ("ok", "gated_read_only")
        ):
            if _should_flip_status(order.status_name or "", True):
                order.status_name = STATUS_PRONTO_BIPAGEM
                unlocked = True
            elif armed and (order.status_name or "") != STATUS_PRONTO_BIPAGEM:
                # Já saiu de Aguardando Nota mas ZPL acabou de chegar
                if "bipagem" not in (order.status_name or "").lower():
                    order.status_name = STATUS_PRONTO_BIPAGEM
                    unlocked = True

        # Espelha no enrichment para UI / expedition fallback
        try:
            enrich = json.loads(order.enrichment_json or "{}")
            if not isinstance(enrich, dict):
                enrich = {}
        except Exception:
            enrich = {}
        enrich["nfe_access_key"] = access_key
        enrich["zpl_armed"] = bool(order.zpl_armed)
        if order.zpl_content:
            enrich["zpl_content"] = order.zpl_content
        enrich["zpl_path"] = order.zpl_path or ""
        enrich["ml_billing_inject_status"] = order.ml_billing_inject_status
        enrich["logistics_unlock_at"] = datetime.now().isoformat()
        order.enrichment_json = json.dumps(enrich, ensure_ascii=False)

        await session.commit()

        return {
            "ok": True,
            "order_id": order.id,
            "previous_status": prev_status,
            "status_name": order.status_name,
            "status_unlocked": unlocked,
            "zpl_armed": bool(order.zpl_armed),
            "zpl_path": order.zpl_path or "",
            "zpl_status": order.zpl_status,
            "ml_billing_inject_status": order.ml_billing_inject_status,
            "nfe_access_key_suffix": access_key[-8:] if len(access_key) >= 8 else access_key,
        }


async def process_bling_nfe_webhook(
    payload: Dict[str, Any],
    *,
    event_row_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Pipeline completo pós-ACK do webhook."""
    await init_db()
    fields = extract_nfe_fields(payload)
    bling_nfe_id = fields["bling_nfe_id"]
    situacao = fields["situacao"]

    if situacao and not situacao_autorizada(situacao, payload):
        result = {
            "ok": True,
            "skipped": True,
            "reason": "situacao_nao_autorizada",
            "situacao": situacao,
            "bling_nfe_id": bling_nfe_id,
        }
        await _finish_event(event_row_id, result, error="")
        return result

    chave, chave_meta = await resolve_nfe_access_key(
        bling_nfe_id=bling_nfe_id,
        chave_payload=fields["nfe_access_key"],
    )
    if not chave:
        result = {
            "ok": False,
            "error": "chave_acesso_indisponivel",
            "meta": chave_meta,
            "hint": "Inclua chaveAcesso no POST de teste ou conclua OAuth Bling (Etapa 2).",
        }
        await _finish_event(event_row_id, result, error=result["error"])
        return result

    order = await find_order_for_nfe(
        bling_nfe_id=bling_nfe_id,
        bling_pedido_id=fields["bling_pedido_id"],
        order_id_hint=fields["order_id_hint"],
        nfe_access_key=chave,
    )
    if not order:
        result = {
            "ok": False,
            "error": "order_not_found",
            "bling_nfe_id": bling_nfe_id,
            "bling_pedido_id": fields["bling_pedido_id"],
            "order_id_hint": fields["order_id_hint"],
            "hint": (
                "Vincule o pedido via Etapa 2 (bling_nfe_id / bling_pedido_id) "
                "ou envie order_id no JSON do webhook."
            ),
        }
        await _finish_event(event_row_id, result, error=result["error"])
        return result

    billing = await inject_billing_info_gated(order, chave)
    zpl = await download_and_arm_zpl(order)
    applied = await apply_order_unlock(
        order.id,
        access_key=chave,
        bling_nfe_id=bling_nfe_id,
        billing_result=billing,
        zpl_result=zpl,
    )

    result = {
        "ok": bool(applied.get("ok")),
        "event": fields["event"],
        "chave_meta": chave_meta,
        "billing_info": billing,
        "zpl": {k: v for k, v in zpl.items() if k != "zpl_content"},
        "order": applied,
        "storage": {
            "sqlite_columns": [
                "nfe_access_key",
                "ml_billing_inject_status",
                "zpl_armed",
                "zpl_content",
                "zpl_path",
                "zpl_status",
                "status_name",
            ],
            "zpl_dir": str(zpl_labels_dir()),
            "note": "Etapa 4 lê zpl_armed/zpl_content via /api/v1/expedition/scan — sem bipagem aqui.",
        },
    }
    await _finish_event(
        event_row_id,
        result,
        error="" if result.get("ok") else str(applied.get("error") or "process_failed"),
        order_id=order.id,
        access_key=chave,
    )
    return result


async def register_webhook_event(payload: Dict[str, Any]) -> int:
    await init_db()
    fields = extract_nfe_fields(payload)
    async with async_session() as session:
        row = BlingNfeWebhookEventDB(
            event_name=fields["event"][:100],
            bling_nfe_id=fields["bling_nfe_id"][:50],
            order_id=fields["order_id_hint"][:100],
            nfe_access_key=fields["nfe_access_key"][:60],
            payload_json=json.dumps(payload, ensure_ascii=False)[:50000],
            received_at=datetime.now(),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return int(row.id)


async def _finish_event(
    event_row_id: Optional[int],
    result: Dict[str, Any],
    *,
    error: str,
    order_id: str = "",
    access_key: str = "",
) -> None:
    if not event_row_id:
        return
    async with async_session() as session:
        row = await session.get(BlingNfeWebhookEventDB, event_row_id)
        if not row:
            return
        row.processed = True
        row.processed_at = datetime.now()
        row.error = (error or "")[:2000]
        row.result_json = json.dumps(result, ensure_ascii=False, default=str)[:50000]
        if order_id:
            row.order_id = order_id
        if access_key:
            row.nfe_access_key = access_key[:60]
        await session.commit()
