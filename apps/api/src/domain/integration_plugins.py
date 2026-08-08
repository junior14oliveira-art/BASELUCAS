"""Catálogo de plugins de integração (hub estilo BaseLinker).

Hoje só Feed ML 4MC + cache SQLite estão ao vivo. Demais entradas são
placeholders do molde — adapters futuros (Bling, NF-e/SEFAZ, Envios, printer).
Adicionar plugin = um item em INTEGRATION_PLUGINS.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal

PluginStatus = Literal["connected", "not_configured", "coming_soon"]

STATUS_LABELS = {
    "connected": "Conectado",
    "not_configured": "Não configurado",
    "coming_soon": "Em breve",
}


def build_integration_plugins(
    *,
    ml_feed_url: str,
    db_engine_label: str,
    ml_oauth_configured: bool,
) -> List[Dict[str, Any]]:
    """Lista de tiles para a UI /app → Integrações."""
    feed_detail = ml_feed_url or "FEED ML 4MC"
    oauth_status: PluginStatus = "connected" if ml_oauth_configured else "not_configured"

    plugins: List[Dict[str, Any]] = [
        {
            "id": "ml_feed_4mc",
            "name": "Feed ML 4MC",
            "category": "Marketplace",
            "icon": "rss_feed",
            "status": "connected",
            "detail": feed_detail,
            "live": True,
            "description": "Único plugin de dados ao vivo — pedidos/produtos via bridge 4MC (read-only).",
        },
        {
            "id": "sqlite_cache",
            "name": "SQLite cache",
            "category": "Infra",
            "icon": "storage",
            "status": "connected",
            "detail": db_engine_label,
            "live": True,
            "description": "Cache local lido pela UI; sync explícito grava aqui.",
        },
        {
            "id": "ml_oauth_direct",
            "name": "Mercado Livre direto OAuth",
            "category": "Marketplace",
            "icon": "login",
            "status": oauth_status,
            "detail": "Credenciais ML_APP_ID / ML_SECRET_KEY" if ml_oauth_configured else "Sem ML_APP_ID / ML_SECRET_KEY",
            "live": False,
            "description": "OAuth direto ML (não é o feed 4MC). Ainda sem wiring completo na UI.",
        },
        {
            "id": "bling_4mc",
            "name": "Bling 4M&C",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": "coming_soon",
            "detail": "Conta ERP",
            "live": False,
            "description": "Adapter Bling planejado — sem API ao vivo.",
        },
        {
            "id": "bling_portal",
            "name": "Bling Portal",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": "not_configured",
            "detail": "Conta ERP",
            "live": False,
            "description": "Adapter Bling planejado — sem API ao vivo.",
        },
        {
            "id": "bling_max",
            "name": "Bling Max",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": "not_configured",
            "detail": "Conta ERP",
            "live": False,
            "description": "Adapter Bling planejado — sem API ao vivo.",
        },
        {
            "id": "bling_star_lude",
            "name": "Bling Star Lude",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": "coming_soon",
            "detail": "Conta ERP",
            "live": False,
            "description": "Adapter Bling planejado — sem API ao vivo.",
        },
        {
            "id": "bling_brasil",
            "name": "Bling Brasil",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": "coming_soon",
            "detail": "Conta ERP",
            "live": False,
            "description": "Adapter Bling planejado — sem API ao vivo.",
        },
        {
            "id": "mercado_envios",
            "name": "Mercado Envios",
            "category": "Logística",
            "icon": "local_shipping",
            "status": "coming_soon",
            "detail": "Contas de envio",
            "live": False,
            "description": "Contas Mercado Envios — adapter futuro.",
        },
        {
            "id": "nfe_sefaz",
            "name": "NF-e / SEFAZ",
            "category": "Fiscal",
            "icon": "receipt_long",
            "status": "coming_soon",
            "detail": "Emissão fiscal",
            "live": False,
            "description": "Emissão NF-e / SEFAZ — adapter futuro (FiscalAgent).",
        },
        {
            "id": "base_printer",
            "name": "Base.printer",
            "category": "Impressão",
            "icon": "print",
            "status": "coming_soon",
            "detail": "Impressão remota",
            "live": False,
            "description": "Daemon de impressão remota / ZPL — roadmap Sprint 4.",
        },
    ]
    return plugins


# Alias estável para docs / imports futuros
INTEGRATION_PLUGINS = build_integration_plugins


def plugin_status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)
