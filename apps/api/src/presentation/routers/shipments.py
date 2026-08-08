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
    """Stub de etiqueta — ZPL real = Fase 4."""
    return {
        "status": "STUB",
        "shipment_id": shipment_id,
        "message": "Impressão ZPL Direct ainda não liberada (Fase 4). Use Pick & Pack para validar bipagem.",
        "label_url": None,
        "zpl_code": f"^XA^FO50,50^ADN,36,20^FDSTUB {shipment_id}^FS^XZ",
        "ml_write": False,
        "ml_read_only": bool(settings.ML_READ_ONLY),
    }
