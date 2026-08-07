from fastapi import APIRouter
from typing import List, Dict, Any
from sqlalchemy import select
from src.infrastructure.database import async_session, RealProductDB
from src.agents.agents_orchestrator import orchestrator

router = APIRouter(prefix="/products", tags=["Produtos & Catálogo Reais"])

@router.get("")
async def list_products(limit: int = 50):
    async with async_session() as session:
        result = await session.execute(select(RealProductDB).limit(limit))
        prods = result.scalars().all()
        output = [
            {
                "id": p.id,
                "sku": p.sku,
                "name": p.name,
                "cost": 0.00,
                "price": p.price,
                "stock": p.stock,
                "channels": ["Mercado Livre", "Shopee"]
            }
            for p in prods
        ]
        return {"total": len(output), "products": output}

@router.post("/sync-stock")
async def sync_stock(sku: str, quantity: int):
    result = await orchestrator.run_stock_agent(sku, quantity, action="update")
    return result
