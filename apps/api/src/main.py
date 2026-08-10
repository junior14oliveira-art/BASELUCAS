from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.config import settings
from src.presentation.routers import (
    dashboard, orders, products, marketplaces, assistant, web_ui, automation_rules,
    inventory_documents, shipments, crm, invoices, external_connect, mercadolivre, operators,
    bling, webhooks, expedition,
)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    description="API REST Clean Architecture + DDD para Plataforma SaaS Omnichannel AI (Evolução BaseLinker)"
)

# CORS Middleware — local: qualquer origem localhost/127.0.0.1
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static UX helpers (toasts etc.) — /app/static/app_ux.js
_STATIC_DIR = Path(__file__).resolve().parent / "presentation" / "static"
if _STATIC_DIR.is_dir():
    app.mount("/app/static", StaticFiles(directory=str(_STATIC_DIR)), name="app_static")

# Register Routers
app.include_router(web_ui.router)
app.include_router(dashboard.router, prefix=settings.API_V1_STR)
app.include_router(orders.router, prefix=settings.API_V1_STR)
app.include_router(products.router, prefix=settings.API_V1_STR)
app.include_router(marketplaces.router, prefix=settings.API_V1_STR)
app.include_router(assistant.router, prefix=settings.API_V1_STR)
app.include_router(automation_rules.router, prefix=settings.API_V1_STR)
app.include_router(inventory_documents.router, prefix=settings.API_V1_STR)
app.include_router(shipments.router, prefix=settings.API_V1_STR)
app.include_router(crm.router, prefix=settings.API_V1_STR)
app.include_router(invoices.router, prefix=settings.API_V1_STR)
app.include_router(external_connect.router, prefix=settings.API_V1_STR)
app.include_router(mercadolivre.router, prefix=settings.API_V1_STR)
app.include_router(operators.router, prefix=settings.API_V1_STR)
app.include_router(operators.users_alias_router, prefix=settings.API_V1_STR)
app.include_router(bling.router, prefix=settings.API_V1_STR)
app.include_router(expedition.router, prefix=settings.API_V1_STR)
# Etapa 3 — /webhooks/bling/nfe e /api/v1/webhooks/bling/nfe (paths absolutos no router)
app.include_router(webhooks.router)

import asyncio
import logging
from src.infrastructure.ml_sync_service import ml_sync_service, get_account

async def auto_sync_ml_task():
    """Background task que roda a cada 5 minutos sincronizando o ML nativo."""
    while True:
        await asyncio.sleep(300)  # Aguarda 5 minutos
        try:
            account = await get_account(None)
            if account and account.access_token:
                logging.info(f"Iniciando Auto-Sync ML em background para: {account.nickname}")
                await ml_sync_service.sync_all(account)
        except Exception as e:
            logging.error(f"Erro no Auto-Sync ML: {e}")

@app.on_event("startup")
async def on_startup():
    asyncio.create_task(auto_sync_ml_task())


@app.get("/api-status")
async def api_status():
    return {
        "message": "Plataforma SaaS Omnichannel AI - API Backend Operational",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
        "web_ui": "/app",
        "status": "HEALTHY",
        "mock_mode": settings.MOCK_INTEGRATIONS
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
