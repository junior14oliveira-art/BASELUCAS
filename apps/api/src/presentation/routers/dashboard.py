from fastapi import APIRouter
from typing import Any, Dict
from sqlalchemy import select, func
from datetime import datetime, timedelta
from src.infrastructure.database import async_session, RealOrderDB, RealProductDB
from src.infrastructure.sync_service import sync_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/kpis")
async def get_dashboard_kpis() -> Dict[str, Any]:
    """KPIs a partir do SQLite local — sem números fictícios."""
    async with async_session() as session:
        orders_count = (
            await session.execute(select(func.count()).select_from(RealOrderDB))
        ).scalar_one()
        products_count = (
            await session.execute(select(func.count()).select_from(RealProductDB))
        ).scalar_one()
        revenue = (
            await session.execute(select(func.coalesce(func.sum(RealOrderDB.total_amount), 0.0)))
        ).scalar_one()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        orders_today = (
            await session.execute(
                select(func.count())
                .select_from(RealOrderDB)
                .where(RealOrderDB.created_at >= today)
            )
        ).scalar_one()
        rev_today = (
            await session.execute(
                select(func.coalesce(func.sum(RealOrderDB.total_amount), 0.0)).where(
                    RealOrderDB.created_at >= today
                )
            )
        ).scalar_one()
        low_stock = (
            await session.execute(
                select(func.count())
                .select_from(RealProductDB)
                .where(RealProductDB.stock <= 5)
            )
        ).scalar_one()

    meta = await sync_service.get_last_sync_meta()
    synced_at = meta.get("synced_at")
    account = (meta.get("account") or {}).get("nickname") or "ML"

    return {
        "faturamento_total": float(revenue or 0),
        "faturamento_hoje": float(rev_today or 0),
        "faturamento_hoje_fmt": f"R$ {float(rev_today or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "pedidos_total": int(orders_count or 0),
        "pedidos_hoje": int(orders_today or 0),
        "produtos_total": int(products_count or 0),
        "estoque_baixo": int(low_stock or 0),
        "account": account,
        "last_sync": synced_at,
        "source": "sqlite",
        "growth_percent": None,
        "nfe_emitidas": None,
        "active_integrations": 1,
        "queue_status": {
            "note": "Infra RabbitMQ/Redis planejada — fluxo atual = FastAPI + SQLite",
            "last_sync": synced_at,
        },
    }


@router.get("/recent-orders")
async def get_recent_orders(limit: int = 20):
    """Pedidos recentes do cache SQLite."""
    import json

    async with async_session() as session:
        rows = (
            await session.execute(
                select(RealOrderDB).order_by(RealOrderDB.created_at.desc()).limit(limit)
            )
        ).scalars().all()
        out = []
        for o in rows:
            items = []
            try:
                items = json.loads(o.items_json) if o.items_json else []
            except (TypeError, ValueError, json.JSONDecodeError):
                items = []
            item_desc = ""
            if items:
                item_desc = f"{items[0].get('name', '')} x{items[0].get('quantity', 1)}"
            out.append(
                {
                    "id": o.id,
                    "marketplace": o.channel_name or "Mercado Livre",
                    "customer": o.customer_name,
                    "item": item_desc or "—",
                    "price": float(o.total_amount or 0),
                    "status": o.status_name,
                    "shipping": o.shipping_status or "",
                    "date": o.created_at.strftime("%d/%m/%Y %H:%M") if o.created_at else "",
                }
            )
        return out
