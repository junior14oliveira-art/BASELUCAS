from fastapi import APIRouter, Query
from typing import Any, Dict, Optional
from sqlalchemy import select
from src.infrastructure.database import async_session, RealOrderDB
from src.config import settings
import json

router = APIRouter(prefix="/shipments", tags=["Envios & Etiquetas de Correio/Transportadoras"])

COURIERS = [
    {"code": "mercado_envios", "name": "Mercado Envios (ME)", "active": True},
    {"code": "correios", "name": "Correios (via ME)", "active": False, "note": "Via ML"},
]


@router.get("")
async def list_shipments(limit: int = Query(100, ge=1, le=500)):
    """Envios derivados dos pedidos reais (SQLite). Sem mocks SHP-8801."""
    async with async_session() as session:
        rows = (
            await session.execute(
                select(RealOrderDB)
                .where(RealOrderDB.shipping_id != "")
                .order_by(RealOrderDB.created_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        # Também inclui pedidos com shipping_status mesmo sem shipping_id
        if len(rows) < limit:
            extra = (
                await session.execute(
                    select(RealOrderDB)
                    .where(RealOrderDB.shipping_status != "")
                    .order_by(RealOrderDB.created_at.desc())
                    .limit(limit)
                )
            ).scalars().all()
            seen = {r.id for r in rows}
            for e in extra:
                if e.id not in seen:
                    rows.append(e)
                    seen.add(e.id)
                if len(rows) >= limit:
                    break

        shipments = []
        for o in rows:
            addr = {}
            try:
                addr = json.loads(o.shipping_address_json or "{}")
            except (TypeError, ValueError, json.JSONDecodeError):
                addr = {}
            shipments.append(
                {
                    "id": o.shipping_id or f"local-{o.id}",
                    "order_id": o.id,
                    "external_order_id": o.external_id,
                    "courier": "Mercado Envios",
                    "tracking_code": o.tracking_number or "",
                    "status": o.shipping_status or o.status_name or "",
                    "customer": o.customer_name,
                    "address": addr if isinstance(addr, dict) else {},
                    "created_at": o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else "",
                }
            )
        return {
            "shipments": shipments,
            "total": len(shipments),
            "couriers": COURIERS,
            "source": "sqlite_real_orders",
            "ml_write": False,
        }


@router.post("")
async def create_shipment(payload: Dict[str, Any]):
    """Bloqueado — criação de envio no ML/BL não liberada."""
    return {
        "status": "BLOCKED",
        "message": "Somente leitura — criação de envio/etiqueta no ML ainda não liberada (Fase 4).",
        "ml_write": False,
        "payload_echo": {
            "order_id": payload.get("order_id"),
            "courier": payload.get("courier"),
        },
    }


@router.get("/{shipment_id}/label")
async def generate_shipping_label(shipment_id: str):
    """Resolve pedido pelo shipping_id → gate ML + links de preview (sem PDF falso)."""
    from src.infrastructure import ml_shipping_labels as ml_labels

    async with async_session() as session:
        row = (
            await session.execute(
                select(RealOrderDB).where(RealOrderDB.shipping_id == shipment_id)
            )
        ).scalars().first()
    if not row:
        return {
            "status": "STUB",
            "shipment_id": shipment_id,
            "message": (
                "Shipment não ligado a pedido no SQLite. "
                "Use GET /api/v1/orders/{{id}}/label ou /label/preview."
            ),
            "label_url": None,
            "ml_write": False,
            "ml_read_only": bool(settings.ML_READ_ONLY),
            "docs": "docs/LABELS_ML.md",
        }
    account = await ml_labels.get_active_ml_account()
    gate = ml_labels.evaluate_production_gate(
        has_oauth=account is not None,
        has_token=bool(account and (account.access_token or "").strip()),
        shipment_id=shipment_id,
        shipping_status=row.shipping_status or "",
    )
    return {
        **gate.as_detail(),
        "shipment_id": shipment_id,
        "order_id": row.id,
        "preview_url": f"/api/v1/orders/{row.id}/label/preview",
        "label_url": f"/api/v1/orders/{row.id}/label?format=pdf",
    }
