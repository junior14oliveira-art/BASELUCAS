from fastapi import APIRouter
from typing import Dict, Any
from src.agents.agents_orchestrator import orchestrator

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/kpis")
async def get_dashboard_kpis() -> Dict[str, Any]:
    return {
        "faturamento_hoje": "R$ 148.500,00",
        "growth_percent": 14.2,
        "pedidos_hoje": 342,
        "estoque_reservado": 1280,
        "nfe_emitidas": 318,
        "active_integrations": 17,
        "queue_status": {
            "rabbitmq": "OPERATIONAL",
            "redis": "OPERATIONAL",
            "last_sync_seconds_ago": 12
        }
    }

@router.get("/recent-orders")
async def get_recent_orders():
    return [
        {
            "id": "45267912",
            "marketplace": "Mercado Livre",
            "customer": "Rennan Ruback de Mello",
            "item": "1x Monitor Positivo 20' E2011px Para Pc Preto 127/220v",
            "price": 447.00,
            "status": "Pedidos Agendados",
            "shipping": "ME2 - Mercado Envios Places",
            "date": "07/08/2026 10:29"
        },
        {
            "id": "45267159",
            "marketplace": "Shopee",
            "customer": "Gentil Dallo",
            "item": "2x Notebook Hp Elitebook 15 8th 16gb Ssd 256gb W11 60hz Cor Prateado",
            "price": 1899.99,
            "status": "Separação Tamires",
            "shipping": "ME2 - Mercado Envios Places",
            "date": "07/08/2026 10:25"
        },
        {
            "id": "45263649",
            "marketplace": "Amazon",
            "customer": "Luzia Tatiana Borges Smania",
            "item": "2x Monitor 19 LG Led Widescreen Preto Base Giratória 127/220v",
            "price": 599.98,
            "status": "Aguardando Faturamento",
            "shipping": "ME2 - Mercado Envios Places",
            "date": "07/08/2026 10:01"
        }
    ]
