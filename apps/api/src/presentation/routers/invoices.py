from fastapi import APIRouter
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/invoices", tags=["Módulo Fiscal: NF-e, Faturas & Recibos SEFAZ"])

INVOICES = [
    {
        "id": "INV-2026-101",
        "order_id": "ORD-1001",
        "nfe_number": "000.012.890",
        "nfe_series": "1",
        "nfe_key": "35260800000000000000550010000128901000000000",
        "customer": "Carlos Eduardo Silva",
        "amount": 499.90,
        "status": "ISSUED",
        "issued_at": "2026-08-07 10:30"
    },
    {
        "id": "INV-2026-102",
        "order_id": "ORD-1002",
        "nfe_number": "000.012.891",
        "nfe_series": "1",
        "nfe_key": "35260800000000000000550010000128911000000000",
        "customer": "Mariana Oliveira",
        "amount": 299.00,
        "status": "PENDING",
        "issued_at": "2026-08-07 11:00"
    }
]

@router.get("")
async def list_invoices():
    return {"invoices": INVOICES, "pending_count": len([i for i in INVOICES if i["status"] == "PENDING"])}

@router.post("")
async def issue_invoice(payload: Dict[str, Any]):
    new_inv = {
        "id": f"INV-2026-{101 + len(INVOICES)}",
        "order_id": payload.get("order_id", "ORD-1000"),
        "nfe_number": f"000.012.{890 + len(INVOICES)}",
        "nfe_series": "1",
        "nfe_key": f"35260800000000000000550010000128{90 + len(INVOICES)}1000000000",
        "customer": payload.get("customer", "Cliente"),
        "amount": float(payload.get("amount", 199.90)),
        "status": "ISSUED",
        "issued_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    INVOICES.insert(0, new_inv)
    return {"status": "SUCCESS", "invoice": new_inv}

@router.get("/{invoice_id}/pdf")
async def download_nfe_pdf(invoice_id: str):
    return {
        "status": "SUCCESS",
        "invoice_id": invoice_id,
        "pdf_url": f"/invoices/danfe_{invoice_id}.pdf"
    }
