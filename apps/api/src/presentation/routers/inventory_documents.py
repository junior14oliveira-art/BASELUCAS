from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/inventory", tags=["Inventário & Documentos WMS"])

# Mock/DB In-memory store for documents, POs and transfers
INVENTORY_DOCUMENTS = [
    {
        "id": "DOC-2026-001",
        "type": "GRN",
        "series": "ENT",
        "warehouse_id": "1",
        "warehouse_name": "Armazém Principal (SP)",
        "status": "CONFIRMED",
        "items_count": 45,
        "total_value": 12490.00,
        "created_at": "2026-08-07 09:30"
    },
    {
        "id": "DOC-2026-002",
        "type": "PO",
        "series": "COMPRA",
        "warehouse_id": "1",
        "warehouse_name": "Armazém Principal (SP)",
        "status": "DRAFT",
        "items_count": 120,
        "total_value": 35000.00,
        "created_at": "2026-08-07 11:15"
    }
]

PURCHASE_ORDERS = [
    {
        "id": "PO-9901",
        "supplier": "Tech Componentes Ltda",
        "status": "SENT",
        "total_items": 200,
        "total_amount": 45000.00,
        "created_at": "2026-08-06 14:00"
    }
]

TRANSFERS = [
    {
        "id": "TRF-501",
        "source_warehouse": "Armazém Principal (SP)",
        "target_warehouse": "Filial Sul (Curitiba)",
        "status": "IN_PROGRESS",
        "items_count": 15,
        "created_at": "2026-08-07 10:00"
    }
]

@router.get("/documents")
async def list_documents(doc_type: Optional[str] = Query(None)):
    if doc_type:
        filtered = [d for d in INVENTORY_DOCUMENTS if d["type"] == doc_type]
        return {"documents": filtered}
    return {"documents": INVENTORY_DOCUMENTS}

@router.post("/documents")
async def create_document(payload: Dict[str, Any]):
    new_doc = {
        "id": f"DOC-2026-00{len(INVENTORY_DOCUMENTS)+1}",
        "type": payload.get("type", "GRN"),
        "series": payload.get("series", "GERAL"),
        "warehouse_id": str(payload.get("warehouse_id", 1)),
        "warehouse_name": "Armazém Central",
        "status": "DRAFT",
        "items_count": len(payload.get("items", [])),
        "total_value": float(payload.get("total_value", 0.0)),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    INVENTORY_DOCUMENTS.insert(0, new_doc)
    return {"status": "SUCCESS", "document": new_doc}

@router.post("/documents/{doc_id}/confirm")
async def confirm_document(doc_id: str):
    doc = next((d for d in INVENTORY_DOCUMENTS if d["id"] == doc_id), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Documento não encontrado")
    doc["status"] = "CONFIRMED"
    return {"status": "SUCCESS", "message": f"Documento #{doc_id} confirmado e estoque atualizado!"}

@router.get("/purchase-orders")
async def list_purchase_orders():
    return {"purchase_orders": PURCHASE_ORDERS}

@router.post("/purchase-orders")
async def create_purchase_order(payload: Dict[str, Any]):
    new_po = {
        "id": f"PO-{9901 + len(PURCHASE_ORDERS)}",
        "supplier": payload.get("supplier", "Fornecedor Padrão"),
        "status": "DRAFT",
        "total_items": payload.get("total_items", 10),
        "total_amount": float(payload.get("total_amount", 1000.0)),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    PURCHASE_ORDERS.insert(0, new_po)
    return {"status": "SUCCESS", "po": new_po}

@router.get("/transfers")
async def list_transfers():
    return {"transfers": TRANSFERS}

@router.post("/transfers")
async def create_transfer(payload: Dict[str, Any]):
    new_trf = {
        "id": f"TRF-{501 + len(TRANSFERS)}",
        "source_warehouse": payload.get("source_warehouse", "Armazém SP"),
        "target_warehouse": payload.get("target_warehouse", "Filial RJ"),
        "status": "DRAFT",
        "items_count": payload.get("items_count", 5),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    TRANSFERS.insert(0, new_trf)
    return {"status": "SUCCESS", "transfer": new_trf}
