"""Webhooks externos — Etapa 3: Bling NF-e (SEFAZ autorizou).

Rotas (ambas válidas):
  POST /webhooks/bling/nfe
  POST /api/v1/webhooks/bling/nfe

Responde 200 rápido e processa em BackgroundTasks (billing_info + ZPL).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, BackgroundTasks, Query, Request
from sqlalchemy import select

from src.config import settings
from src.infrastructure.database import BlingNfeWebhookEventDB, async_session, init_db
from src.infrastructure import logistics_unlock_service as logistics

router = APIRouter(tags=["Webhooks — Bling NF-e / Logística"])


async def _handle_nfe_webhook(request: Request, background_tasks: BackgroundTasks) -> Dict[str, Any]:
    try:
        payload = await request.json()
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"raw": payload}

    event_id = await logistics.register_webhook_event(payload)
    background_tasks.add_task(logistics.process_bling_nfe_webhook, payload, event_row_id=event_id)

    fields = logistics.extract_nfe_fields(payload)
    return {
        "status": "accepted",
        "message": "Webhook NF-e recebido — processamento em background (billing_info + ZPL).",
        "event_id": event_id,
        "bling_nfe_id": fields.get("bling_nfe_id") or None,
        "docs": "docs/LABELS_ML.md",
    }


@router.post("/webhooks/bling/nfe")
async def bling_nfe_webhook_root(request: Request, background_tasks: BackgroundTasks):
    """URL sugerida no ROADMAP: POST /webhooks/bling/nfe"""
    return await _handle_nfe_webhook(request, background_tasks)


@router.post("/api/v1/webhooks/bling/nfe")
async def bling_nfe_webhook_v1(request: Request, background_tasks: BackgroundTasks):
    """Alias com prefixo API (painel Bling / docs/BLING_API_STUDY.md)."""
    return await _handle_nfe_webhook(request, background_tasks)


@router.post("/api/v1/webhooks/bling/nfe/process/{event_id}")
async def reprocess_bling_nfe_event(event_id: int):
    """Reprocessa evento já gravado (debug / retry)."""
    await init_db()
    async with async_session() as session:
        row = await session.get(BlingNfeWebhookEventDB, event_id)
        if not row:
            return {"ok": False, "error": "event_not_found", "event_id": event_id}
        try:
            import json

            payload = json.loads(row.payload_json or "{}")
        except Exception:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    result = await logistics.process_bling_nfe_webhook(payload, event_row_id=event_id)
    return {"ok": True, "event_id": event_id, "result": result}


@router.get("/api/v1/webhooks/bling/nfe/events")
async def list_bling_nfe_events(
    processed: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    await init_db()
    async with async_session() as session:
        q = select(BlingNfeWebhookEventDB).order_by(BlingNfeWebhookEventDB.id.desc()).limit(limit)
        if processed is not None:
            q = q.where(BlingNfeWebhookEventDB.processed == processed)
        rows = (await session.execute(q)).scalars().all()
        return {
            "total": len(rows),
            "events": [
                {
                    "id": r.id,
                    "event_name": r.event_name,
                    "bling_nfe_id": r.bling_nfe_id,
                    "order_id": r.order_id,
                    "nfe_access_key_suffix": (r.nfe_access_key or "")[-8:],
                    "processed": r.processed,
                    "error": r.error,
                    "received_at": r.received_at.isoformat() if r.received_at else None,
                    "processed_at": r.processed_at.isoformat() if r.processed_at else None,
                }
                for r in rows
            ],
        }


@router.get("/api/v1/orders/{order_id}/logistics")
async def get_order_logistics_state(order_id: str):
    """Onde o ZPL está engatilhado + status billing_info (entrega Etapa 3)."""
    from src.infrastructure.database import RealOrderDB

    await init_db()
    async with async_session() as session:
        order = await session.get(RealOrderDB, order_id)
        if not order:
            return {"ok": False, "error": "order_not_found"}
        key = order.nfe_access_key or ""
        return {
            "ok": True,
            "order_id": order.id,
            "status_name": order.status_name,
            "nfe_access_key_suffix": key[-8:] if len(key) >= 8 else key,
            "ml_billing_inject_status": order.ml_billing_inject_status,
            "ml_read_only": bool(settings.ML_READ_ONLY),
            "zpl": {
                "armed": bool(order.zpl_armed),
                "status": order.zpl_status,
                "path": order.zpl_path or None,
                "has_content": bool((order.zpl_content or "").strip()),
                "ready_at": order.zpl_ready_at.isoformat() if order.zpl_ready_at else None,
                "dir": str(logistics.zpl_labels_dir()),
            },
            "next_step": "Etapa 4: POST /api/v1/expedition/scan com barcode do pedido",
        }
