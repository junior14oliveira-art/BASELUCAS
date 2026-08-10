from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.config import settings
from src.presentation.routers import (
    dashboard, orders, products, marketplaces, assistant, web_ui, automation_rules,
    inventory_documents, shipments, crm, invoices, external_connect, mercadolivre, operators
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
