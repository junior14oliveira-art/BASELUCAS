"""Catálogo de plugins de integração (hub estilo BaseLinker).

Hoje só Feed ML 4MC + cache SQLite estão ao vivo. Demais entradas são
placeholders do molde — adapters futuros (Bling, NF-e/SEFAZ, Envios, printer).
Adicionar plugin = um item em INTEGRATION_PLUGINS.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal

PluginStatus = Literal["connected", "configured", "awaiting_credentials", "not_configured", "coming_soon"]

STATUS_LABELS = {
    "connected": "Conectado",
    "configured": "Configurado",
    "awaiting_credentials": "Aguardando credenciais",
    "not_configured": "Não configurado",
    "coming_soon": "Em breve",
}


def build_integration_plugins(
    *,
    ml_feed_url: str,
    db_engine_label: str,
    ml_oauth_configured: bool,
    bling_app_configured: bool = False,
    bling_oauth_token: bool = False,
    nfe_emit_enabled: bool = False,
) -> List[Dict[str, Any]]:
    """Lista de tiles para a UI /app → Integrações."""
    feed_detail = ml_feed_url or "FEED ML 4MC"
    oauth_status: PluginStatus = "connected" if ml_oauth_configured else "not_configured"
    oauth_detail = (
        "OAuth nativo conectado (não é o feed 4MC)"
        if ml_oauth_configured
        else "Sem ML_CLIENT_ID / ML_CLIENT_SECRET — card Canais → ML direto"
    )

    if not bling_app_configured:
        bling_status: PluginStatus = "awaiting_credentials"
        bling_detail = "BLING_CLIENT_ID / BLING_CLIENT_SECRET"
    elif bling_oauth_token:
        bling_status = "configured"
        bling_detail = "OAuth ok — writes gated por BLING_READ_ONLY"
    else:
        bling_status = "configured"
        bling_detail = "App ok — GET /api/v1/bling/auth"

    nfe_status: PluginStatus = "configured" if bling_app_configured else "awaiting_credentials"
    nfe_detail = (
        "Emissão OFF (NFE_EMIT_ENABLED=false)"
        if not nfe_emit_enabled
        else "Emissão habilitada — homologação"
    )

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
            "detail": oauth_detail,
            "live": False,
            "description": "OAuth direto ML (não é o feed 4MC). Credenciais via card Canais ou .env.",
        },
        {
            "id": "bling_4mc",
            "name": "Bling 4M&C",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": bling_status,
            "detail": bling_detail,
            "live": False,
            "description": "Macro Fiscal — POST /pedidos/vendas + NF-e gated. Nunca 'Conectado' sem OAuth.",
        },
        {
            "id": "bling_portal",
            "name": "Bling Portal",
            "category": "ERP / Bling",
            "icon": "account_balance",
            "status": "coming_soon" if not bling_app_configured else bling_status,
            "detail": "Conta ERP",
            "live": False,
            "description": "Adapter multi-conta — roadmap.",
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
            "status": nfe_status,
            "detail": nfe_detail,
            "live": False,
            "description": "Emissão via Bling (POST /nfe) — NFE_EMIT_ENABLED=false até homologação.",
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
