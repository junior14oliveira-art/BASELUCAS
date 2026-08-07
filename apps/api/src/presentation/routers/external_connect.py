from fastapi import APIRouter
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/connect", tags=["Base Connect B2B, Fulfillment & Lojas Externas"])

B2B_PARTNERS = [
    {
        "id": "B2B-01",
        "name": "Bling ERP Integration",
        "type": "ERP",
        "status": "CONNECTED",
        "credit_limit": 50000.00,
        "credit_used": 12500.00,
        "last_sync": "2026-08-07 12:00"
    },
    {
        "id": "B2B-02",
        "name": "Tiny ERP Integration",
        "type": "ERP",
        "status": "CONNECTED",
        "credit_limit": 30000.00,
        "credit_used": 4200.00,
        "last_sync": "2026-08-07 11:45"
    }
]

FULFILLMENT_DELIVERIES = [
    {
        "id": "FUL-901",
        "center_name": "Full Mercado Livre (Louveira-SP)",
        "status": "IN_TRANSIT",
        "items_count": 500,
        "created_at": "2026-08-05"
    }
]

@router.get("/partners")
async def list_b2b_partners():
    return {"partners": B2B_PARTNERS}

@router.get("/fulfillment")
async def list_fulfillment_deliveries():
    return {"deliveries": FULFILLMENT_DELIVERIES}
