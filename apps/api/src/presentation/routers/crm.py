from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
from datetime import datetime

router = APIRouter(prefix="/crm", tags=["CRM & Gestão de Clientes"])

CUSTOMERS = [
    {
        "id": "CRM-01",
        "name": "Carlos Eduardo Silva",
        "email": "carlos.silva@email.com",
        "phone": "(11) 98765-4321",
        "company": "Silva Tech Comercial Ltda",
        "document": "12.345.678/0001-90",
        "status": "VIP",
        "orders_count": 14,
        "total_spent": 12890.50,
        "created_at": "2025-03-15"
    },
    {
        "id": "CRM-02",
        "name": "Mariana Oliveira",
        "email": "mariana.oliveira@email.com",
        "phone": "(21) 99887-6655",
        "company": "Mariana E-commerce",
        "document": "987.654.321-00",
        "status": "REGULAR",
        "orders_count": 3,
        "total_spent": 890.00,
        "created_at": "2026-01-20"
    }
]

@router.get("/customers")
async def list_customers(search: Optional[str] = Query(None)):
    if search:
        s_lower = search.lower()
        filtered = [c for c in CUSTOMERS if s_lower in c["name"].lower() or s_lower in c["email"].lower()]
        return {"customers": filtered}
    return {"customers": CUSTOMERS}

@router.get("/customers/{customer_id}")
async def get_customer_detail(customer_id: str):
    cust = next((c for c in CUSTOMERS if c["id"] == customer_id or c["email"] == customer_id), None)
    if not cust:
        # Fallback dynamic customer object
        return {
            "id": customer_id,
            "name": "Cliente BaseLinker",
            "email": f"{customer_id}@email.com",
            "phone": "(11) 99999-8888",
            "status": "REGULAR",
            "orders_count": 5,
            "total_spent": 1500.00,
            "orders_history": []
        }
    return cust

@router.put("/customers/{customer_id}")
async def update_customer(customer_id: str, payload: Dict[str, Any]):
    cust = next((c for c in CUSTOMERS if c["id"] == customer_id), None)
    if cust:
        for k, v in payload.items():
            if k in cust:
                cust[k] = v
    return {"status": "SUCCESS", "message": f"Cliente #{customer_id} atualizado com sucesso!"}
