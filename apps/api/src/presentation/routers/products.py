from fastapi import APIRouter, Query
from typing import Optional
from sqlalchemy import select, func
from src.infrastructure.database import async_session, RealProductDB
from src.config import settings

router = APIRouter(prefix="/products", tags=["Produtos & Catálogo Reais"])


@router.get("")
async def list_products(
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None),
):
    """Lista produtos do cache SQLite (feed ML). Sem canais fictícios."""
    async with async_session() as session:
        total = (await session.execute(select(func.count()).select_from(RealProductDB))).scalar_one()
        query = select(RealProductDB).offset(offset).limit(limit)
        result = await session.execute(query)
        prods = result.scalars().all()
        output = []
        for p in prods:
            row = {
                "id": p.id,
                "mlb_id": p.id,
                "sku": p.sku or "",
                "name": p.name or "",
                "price": float(p.price or 0),
                "stock": int(p.stock or 0),
                "status": getattr(p, "status", "") or "",
                "permalink": getattr(p, "permalink", "") or "",
                "ean": getattr(p, "ean", "") or "",
                "sold_quantity": int(getattr(p, "sold_quantity", 0) or 0),
                "currency_id": getattr(p, "currency_id", None) or "BRL",
                "channels": ["Mercado Livre"],
            }
            output.append(row)
        if search:
            q = search.lower().strip()
            output = [
                p
                for p in output
                if q in (p.get("sku") or "").lower()
                or q in (p.get("name") or "").lower()
                or q in (p.get("id") or "").lower()
                or q in (p.get("ean") or "").lower()
            ]
        return {
            "total": int(total or 0),
            "returned": len(output),
            "offset": offset,
            "limit": limit,
            "products": output,
            "ml_read_only": bool(settings.ML_READ_ONLY),
        }


@router.post("/sync-stock")
async def sync_stock(sku: str, quantity: int):
    """Bloqueado enquanto ML_READ_ONLY — não altera estoque no ML."""
    if settings.ML_READ_ONLY:
        return {
            "status": "BLOCKED",
            "message": "Somente leitura — em construção. Escrita de estoque no ML desativada.",
            "ml_write": False,
            "sku": sku,
            "quantity": quantity,
        }
    from src.agents.agents_orchestrator import orchestrator

    result = await orchestrator.run_stock_agent(sku, quantity, action="update")
    return result
