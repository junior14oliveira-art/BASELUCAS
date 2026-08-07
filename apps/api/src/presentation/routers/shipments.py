from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/shipments", tags=["Envios & Etiquetas de Correio/Transportadoras"])

SHIPMENTS = [
    {
        "id": "SHP-8801",
        "order_id": "ORD-1001",
        "courier": "Correios Sedex",
        "tracking_code": "BR123456789BR",
        "status": "DISPATCHED",
        "created_at": "2026-08-07 08:00"
    },
    {
        "id": "SHP-8802",
        "order_id": "ORD-1002",
        "courier": "Jadlog Package",
        "tracking_code": "JAD987654321",
        "status": "DELIVERED",
        "created_at": "2026-08-06 14:20"
    }
]

COURIERS = [
    {"code": "correios", "name": "Correios (Sedex / Pac)", "active": True},
    {"code": "jadlog", "name": "Jadlog Express", "active": True},
    {"code": "loggi", "name": "Loggi Direct", "active": True},
    {"code": "melhorenvio", "name": "Melhor Envio Multi", "active": True}
]

@router.get("")
async def list_shipments():
    return {"shipments": SHIPMENTS, "couriers": COURIERS}

@router.post("")
async def create_shipment(payload: Dict[str, Any]):
    new_shp = {
        "id": f"SHP-{8801 + len(SHIPMENTS)}",
        "order_id": payload.get("order_id", "ORD-1000"),
        "courier": payload.get("courier", "Correios Sedex"),
        "tracking_code": payload.get("tracking_code", f"BR{100000000 + len(SHIPMENTS)}BR"),
        "status": "PENDING_DISPATCH",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    SHIPMENTS.insert(0, new_shp)
    return {"status": "SUCCESS", "shipment": new_shp}

@router.get("/{shipment_id}/label")
async def generate_shipping_label(shipment_id: str):
    return {
        "status": "SUCCESS",
        "shipment_id": shipment_id,
        "label_url": f"/labels/zpl_{shipment_id}.pdf",
        "zpl_code": f"^XA^FO50,50^ADN,36,20^FDENVIO OMNICHANNEL #{shipment_id}^FS^XZ"
    }
