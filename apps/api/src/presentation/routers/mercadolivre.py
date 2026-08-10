"""Endpoints REST da integração com o Mercado Livre.

Fluxo de conexão:
 1. GET  /ml/auth/url        -> devolve a URL de autorização
 2. vendedor autoriza no ML  -> ML redireciona para o redirect_uri
 3. GET  /ml/auth/callback   -> troca o code por tokens e grava a conta
"""

import json
import secrets
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from src.config import settings
from src.infrastructure.database import (
    async_session,
    init_db,
    MLAccountDB,
    MLCategoryMapDB,
    MLListingDB,
    MLOrderDB,
    MLQuestionDB,
    MLWebhookEventDB,
)
from src.infrastructure.mercadolivre_client import (
    MercadoLivreClient,
    MercadoLivreError,
    MercadoLivreAuthError,
    generate_pkce_pair,
    is_configured,
)
from src.infrastructure.ml_sync_service import build_client, get_account, ml_sync_service

router = APIRouter(prefix="/ml", tags=["Mercado Livre"])

# Guarda state -> code_verifier entre o início do OAuth e o callback.
# Em produção com múltiplas réplicas isso deve migrar para o Redis.
_oauth_states: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PriceUpdate(BaseModel):
    price: float = Field(gt=0, description="Novo preço do anúncio")


class StockUpdate(BaseModel):
    quantity: int = Field(ge=0, description="Nova quantidade disponível")


class BulkItemUpdate(BaseModel):
    item_id: str
    price: Optional[float] = Field(default=None, gt=0)
    quantity: Optional[int] = Field(default=None, ge=0)


class BulkUpdateRequest(BaseModel):
    updates: List[BulkItemUpdate]


class AnswerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class CategoryMapRequest(BaseModel):
    internal_category: str
    ml_category_id: str


class CreateListingRequest(BaseModel):
    title: str
    category_id: str
    price: float = Field(gt=0)
    available_quantity: int = Field(ge=1)
    condition: str = "new"
    listing_type_id: str = "gold_special"
    currency_id: str = "BRL"
    description: Optional[str] = None
    pictures: List[str] = Field(default_factory=list)
    attributes: List[Dict[str, Any]] = Field(default_factory=list)
    sku: Optional[str] = None


class StockPushRequest(BaseModel):
    sku: str
    quantity: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _require_account(ml_user_id: Optional[int] = None) -> MLAccountDB:
    account = await get_account(ml_user_id)
    if not account:
        raise HTTPException(
            status_code=412,
            detail="Nenhuma conta do Mercado Livre conectada. Chame GET /api/v1/ml/auth/url para conectar.",
        )
    return account


def _handle_ml_error(exc: MercadoLivreError) -> HTTPException:
    status = 401 if isinstance(exc, MercadoLivreAuthError) else (exc.status_code or 502)
    if status < 400:
        status = 502
    return HTTPException(status_code=status, detail={"message": exc.message, "ml_payload": exc.payload})


# ---------------------------------------------------------------------------
# Status da integração
# ---------------------------------------------------------------------------

def _mask_secret(value: str, keep: int = 4) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= keep:
        return "*" * len(v)
    return ("*" * max(len(v) - keep, 4)) + v[-keep:]


class MLCredentialsBody(BaseModel):
    client_id: str = Field(..., min_length=1, description="App ID (ML_CLIENT_ID)")
    client_secret: str = Field(..., min_length=1, description="Secret Key")
    redirect_uri: Optional[str] = None


async def _hydrate_ml_app_from_db() -> None:
    """Carrega App ID/Secret salvos no .env ou SyncMeta se settings em memória estiverem vazios."""
    import os
    from src.infrastructure.database import SyncMetaDB

    # Só getenv — nunca hardcodar Client ID/Secret no código.
    if not (settings.ML_CLIENT_ID or "").strip():
        settings.ML_CLIENT_ID = os.getenv("ML_CLIENT_ID", "")
    if not (settings.ML_CLIENT_SECRET or "").strip():
        settings.ML_CLIENT_SECRET = os.getenv("ML_CLIENT_SECRET", "")

    await init_db()
    async with async_session() as session:
        mapping = {
            "ml_oauth.client_id": "ML_CLIENT_ID",
            "ml_oauth.client_secret": "ML_CLIENT_SECRET",
            "ml_oauth.redirect_uri": "ML_REDIRECT_URI",
        }
        for meta_key, attr in mapping.items():
            current = (getattr(settings, attr, None) or "").strip()
            if current:
                continue
            row = await session.get(SyncMetaDB, meta_key)
            if row and (row.value or "").strip():
                setattr(settings, attr, row.value.strip())


@router.get("/status")
async def integration_status():
    """Diz se o app já foi configurado e quais contas estão conectadas."""
    await _hydrate_ml_app_from_db()
    async with async_session() as session:
        result = await session.execute(select(MLAccountDB))
        accounts = result.scalars().all()

    active = [a for a in accounts if a.is_active and (a.access_token or "").strip()]
    app_ok = is_configured()
    if active:
        ui_status, ui_label, ui_color = "connected", "Conectado (OAuth direto)", "green"
    elif app_ok:
        ui_status, ui_label, ui_color = "awaiting", "App configurado — conclua OAuth", "amber"
    else:
        ui_status, ui_label, ui_color = "not_configured", "Não configurado — clique para conectar", "muted"

    return {
        "configured": app_ok,
        "site_id": settings.ML_SITE_ID,
        "redirect_uri": settings.ML_REDIRECT_URI,
        "client_id_masked": _mask_secret(settings.ML_CLIENT_ID or "", 6),
        "has_client_secret": bool((settings.ML_CLIENT_SECRET or "").strip()),
        "ml_read_only": bool(getattr(settings, "ML_READ_ONLY", True)),
        "connected_accounts": len(active),
        "ui_status": ui_status,
        "ui_label": ui_label,
        "ui_color": ui_color,
        "accounts": [
            {
                "id": a.id,
                "ml_user_id": a.ml_user_id,
                "nickname": a.nickname,
                "is_active": a.is_active,
                "token_expired": a.expires_at > 0 and time.time() >= a.expires_at,
                "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
            }
            for a in accounts
        ],
        "setup_hint": (
            None if app_ok
            else "Informe App ID / Secret no card Mercado Livre direto ou em apps/api/.env"
        ),
        "note": "Separado do feed 4M&C — este é OAuth nativo da API oficial.",
    }


@router.post("/credentials")
async def save_ml_credentials(body: MLCredentialsBody):
    """Salva App ID / Secret do DevCenter (runtime + SyncMeta; não commit de secrets)."""
    await init_db()
    settings.ML_CLIENT_ID = body.client_id.strip()
    settings.ML_CLIENT_SECRET = body.client_secret.strip()
    if body.redirect_uri and body.redirect_uri.strip():
        settings.ML_REDIRECT_URI = body.redirect_uri.strip()

    from src.infrastructure.database import SyncMetaDB

    async with async_session() as session:
        for key, value in (
            ("ml_oauth.client_id", settings.ML_CLIENT_ID),
            ("ml_oauth.client_secret", settings.ML_CLIENT_SECRET),
            ("ml_oauth.redirect_uri", settings.ML_REDIRECT_URI),
        ):
            row = await session.get(SyncMetaDB, key)
            if not row:
                row = SyncMetaDB(key=key, value=value)
                session.add(row)
            else:
                row.value = value
                row.updated_at = datetime.now()
        await session.commit()

    return {
        "ok": True,
        "message": "Credenciais ML direto salvas. Inicie o OAuth para conectar a conta.",
        "status": await integration_status(),
    }


# ---------------------------------------------------------------------------
# OAuth2
# ---------------------------------------------------------------------------

@router.get("/auth/url")
async def get_authorization_url(use_pkce: bool = Query(True, description="Usar PKCE (recomendado)")):
    """Gera a URL para o vendedor autorizar o app."""
    await _hydrate_ml_app_from_db()
    if not is_configured():
        raise HTTPException(
            status_code=412,
            detail="ML_CLIENT_ID/ML_CLIENT_SECRET não configurados. Preencha no card ML direto ou apps/api/.env.",
        )

    state = secrets.token_urlsafe(24)
    code_challenge = None
    entry: Dict[str, Any] = {"created_at": time.time()}

    if use_pkce:
        pkce = generate_pkce_pair()
        entry["code_verifier"] = pkce["code_verifier"]
        code_challenge = pkce["code_challenge"]

    _oauth_states[state] = entry

    # Limpa states com mais de 10 minutos.
    cutoff = time.time() - 600
    for key in [k for k, v in _oauth_states.items() if v["created_at"] < cutoff]:
        _oauth_states.pop(key, None)

    return {
        "authorization_url": MercadoLivreClient.build_authorization_url(state, code_challenge),
        "state": state,
        "expires_in_seconds": 600,
    }


@router.get("/auth/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
):
    """Recebe o redirect do Mercado Livre e grava a conta conectada."""
    if error:
        raise HTTPException(status_code=400, detail=f"Autorização negada: {error} — {error_description}")
    if not code:
        raise HTTPException(status_code=400, detail="Parâmetro 'code' ausente no callback.")

    entry = _oauth_states.pop(state, None) if state else None
    code_verifier = entry.get("code_verifier") if entry else None

    try:
        tokens = await MercadoLivreClient.exchange_code(code, code_verifier=code_verifier)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    client = MercadoLivreClient(
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        user_id=tokens.get("user_id"),
        expires_at=time.time() + int(tokens.get("expires_in", 21600)),
    )

    try:
        me = await client.get_me()
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(MLAccountDB).where(MLAccountDB.ml_user_id == int(tokens["user_id"]))
        )
        account = result.scalars().first()

        if not account:
            account = MLAccountDB(ml_user_id=int(tokens["user_id"]))
            session.add(account)

        account.nickname = me.get("nickname", "")
        account.email = me.get("email", "") or ""
        account.site_id = me.get("site_id", settings.ML_SITE_ID)
        account.access_token = tokens["access_token"]
        account.refresh_token = tokens.get("refresh_token", "")
        account.expires_at = client.expires_at
        account.scopes = tokens.get("scope", "")
        account.is_active = True
        account.connected_at = datetime.now()

        await session.commit()
        account_id = account.id

    return {
        "message": f"Conta {me.get('nickname')} conectada com sucesso!",
        "account_id": account_id,
        "ml_user_id": tokens["user_id"],
        "nickname": me.get("nickname"),
        "site_id": me.get("site_id"),
        "next_step": "POST /api/v1/ml/sync/all para importar anúncios, pedidos e perguntas.",
    }


@router.get("/accounts")
async def list_accounts():
    """Contas de vendedor conectadas (sem expor tokens)."""
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(MLAccountDB))
        accounts = result.scalars().all()

    return {
        "total": len(accounts),
        "accounts": [
            {
                "id": a.id,
                "ml_user_id": a.ml_user_id,
                "nickname": a.nickname,
                "email": a.email,
                "site_id": a.site_id,
                "is_active": a.is_active,
                "connected_at": a.connected_at.isoformat() if a.connected_at else None,
                "last_sync_at": a.last_sync_at.isoformat() if a.last_sync_at else None,
                "token_expires_in": max(0, int(a.expires_at - time.time())) if a.expires_at else 0,
            }
            for a in accounts
        ],
    }


@router.delete("/accounts/{account_id}")
async def disconnect_account(account_id: int):
    """Desconecta a conta (mantém o histórico já sincronizado)."""
    async with async_session() as session:
        account = await session.get(MLAccountDB, account_id)
        if not account:
            raise HTTPException(status_code=404, detail="Conta não encontrada.")
        account.is_active = False
        account.access_token = ""
        account.refresh_token = ""
        await session.commit()
        nickname = account.nickname

    return {"message": f"Conta {nickname} desconectada."}


# ---------------------------------------------------------------------------
# Sincronização
# ---------------------------------------------------------------------------

@router.post("/sync/all")
async def sync_all(ml_user_id: Optional[int] = Query(None)):
    """Carga completa: anúncios, pedidos e perguntas."""
    account = await _require_account(ml_user_id)
    try:
        return await ml_sync_service.sync_all(account)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.post("/sync/listings")
async def sync_listings(
    ml_user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="active, paused ou closed"),
):
    account = await _require_account(ml_user_id)
    try:
        return await ml_sync_service.sync_listings(account, status=status)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.post("/sync/orders")
async def sync_orders(
    ml_user_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None, description="paid, shipped, cancelled..."),
    date_from: Optional[str] = Query(None, description="ISO-8601, ex: 2026-08-01T00:00:00.000-03:00"),
):
    account = await _require_account(ml_user_id)
    try:
        return await ml_sync_service.sync_orders(account, status=status, date_from=date_from)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.post("/sync/questions")
async def sync_questions(ml_user_id: Optional[int] = Query(None)):
    account = await _require_account(ml_user_id)
    try:
        return await ml_sync_service.sync_questions(account)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


# ---------------------------------------------------------------------------
# Anúncios
# ---------------------------------------------------------------------------

@router.get("/listings")
async def list_listings(
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None, description="Filtra por título ou SKU"),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """Anúncios já sincronizados na base local."""
    await init_db()
    async with async_session() as session:
        query = select(MLListingDB)
        count_query = select(func.count(MLListingDB.id))

        if status:
            query = query.where(MLListingDB.status == status)
            count_query = count_query.where(MLListingDB.status == status)
        if search:
            pattern = f"%{search}%"
            condition = MLListingDB.title.ilike(pattern) | MLListingDB.sku.ilike(pattern)
            query = query.where(condition)
            count_query = count_query.where(condition)

        total = (await session.execute(count_query)).scalar() or 0
        result = await session.execute(
            query.order_by(MLListingDB.sold_quantity.desc()).limit(limit).offset(offset)
        )
        listings = result.scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "listings": [
            {
                "id": l.id,
                "title": l.title,
                "sku": l.sku,
                "price": l.price,
                "available_quantity": l.available_quantity,
                "sold_quantity": l.sold_quantity,
                "status": l.status,
                "listing_type_id": l.listing_type_id,
                "category_id": l.category_id,
                "permalink": l.permalink,
                "thumbnail": l.thumbnail,
                "free_shipping": l.free_shipping,
                "logistic_type": l.logistic_type,
                "catalog_listing": l.catalog_listing,
                "health": l.health,
            }
            for l in listings
        ],
    }


@router.get("/listings/{item_id}")
async def get_listing(item_id: str, refresh: bool = Query(False, description="Buscar direto no ML")):
    """Detalhe do anúncio. Com ``refresh=true`` busca ao vivo na API do ML."""
    if refresh:
        account = await _require_account()
        client = await build_client(account)
        try:
            return await client.get_item(item_id)
        except MercadoLivreError as exc:
            raise _handle_ml_error(exc)

    async with async_session() as session:
        listing = await session.get(MLListingDB, item_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Anúncio não encontrado na base local.")
    return json.loads(listing.raw_json)


@router.put("/listings/{item_id}/price")
async def update_price(item_id: str, payload: PriceUpdate, ml_user_id: Optional[int] = Query(None)):
    """Altera o preço do anúncio no Mercado Livre."""
    account = await _require_account(ml_user_id)
    try:
        return await ml_sync_service.push_price(account, item_id, payload.price)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.put("/listings/{item_id}/stock")
async def update_stock(item_id: str, payload: StockUpdate, ml_user_id: Optional[int] = Query(None)):
    """Altera a quantidade disponível do anúncio."""
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        response = await client.update_item_stock(item_id, payload.quantity)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    async with async_session() as session:
        row = await session.get(MLListingDB, item_id)
        if row:
            row.available_quantity = payload.quantity
        await session.commit()

    return {"item_id": item_id, "available_quantity": payload.quantity,
            "ml_status": response.get("status")}


@router.post("/listings/{item_id}/pause")
async def pause_listing(item_id: str, ml_user_id: Optional[int] = Query(None)):
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        await client.pause_item(item_id)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    async with async_session() as session:
        row = await session.get(MLListingDB, item_id)
        if row:
            row.status = "paused"
        await session.commit()

    return {"item_id": item_id, "status": "paused"}


@router.post("/listings/{item_id}/activate")
async def activate_listing(item_id: str, ml_user_id: Optional[int] = Query(None)):
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        await client.activate_item(item_id)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    async with async_session() as session:
        row = await session.get(MLListingDB, item_id)
        if row:
            row.status = "active"
        await session.commit()

    return {"item_id": item_id, "status": "active"}


@router.post("/listings/bulk-update")
async def bulk_update_listings(payload: BulkUpdateRequest, ml_user_id: Optional[int] = Query(None)):
    """Atualiza preço e/ou estoque de vários anúncios de uma vez.

    Processa item a item e devolve o resultado individual — uma falha em um
    anúncio não impede os demais.
    """
    account = await _require_account(ml_user_id)
    client = await build_client(account)

    succeeded: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for update in payload.updates:
        fields: Dict[str, Any] = {}
        if update.price is not None:
            fields["price"] = update.price
        if update.quantity is not None:
            fields["available_quantity"] = update.quantity
        if not fields:
            failed.append({"item_id": update.item_id, "error": "Nenhum campo para atualizar."})
            continue

        try:
            await client.update_item(update.item_id, fields)
            succeeded.append({"item_id": update.item_id, **fields})
        except MercadoLivreError as exc:
            failed.append({"item_id": update.item_id, "error": exc.message})

    if succeeded:
        async with async_session() as session:
            for item in succeeded:
                row = await session.get(MLListingDB, item["item_id"])
                if row:
                    if "price" in item:
                        row.price = item["price"]
                    if "available_quantity" in item:
                        row.available_quantity = item["available_quantity"]
            await session.commit()

    return {"updated": len(succeeded), "failed": len(failed),
            "succeeded": succeeded, "errors": failed}


@router.post("/listings")
async def create_listing(payload: CreateListingRequest, ml_user_id: Optional[int] = Query(None)):
    """Publica um novo anúncio no Mercado Livre."""
    account = await _require_account(ml_user_id)
    client = await build_client(account)

    attributes = list(payload.attributes)
    if payload.sku and not any(a.get("id") == "SELLER_SKU" for a in attributes):
        attributes.append({"id": "SELLER_SKU", "value_name": payload.sku})

    item_data: Dict[str, Any] = {
        "title": payload.title,
        "category_id": payload.category_id,
        "price": payload.price,
        "currency_id": payload.currency_id,
        "available_quantity": payload.available_quantity,
        "buying_mode": "buy_it_now",
        "listing_type_id": payload.listing_type_id,
        "condition": payload.condition,
        "pictures": [{"source": url} for url in payload.pictures],
        "attributes": attributes,
    }

    try:
        created = await client.create_item(item_data)
        if payload.description:
            await client.update_item_description(created["id"], payload.description)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    return {
        "item_id": created.get("id"),
        "permalink": created.get("permalink"),
        "status": created.get("status"),
    }


@router.post("/listings/push-stock")
async def push_stock_by_sku(payload: StockPushRequest, ml_user_id: Optional[int] = Query(None)):
    """Propaga o estoque de um SKU interno para todos os anúncios vinculados."""
    account = await _require_account(ml_user_id)
    try:
        return await ml_sync_service.push_stock(account, payload.sku, payload.quantity)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


# ---------------------------------------------------------------------------
# Categorias e De-Para
# ---------------------------------------------------------------------------

@router.get("/categories/predict")
async def predict_category(title: str = Query(..., min_length=3)):
    """Sugere a categoria do Mercado Livre a partir do título do produto."""
    client = MercadoLivreClient()
    try:
        return {"title": title, "suggestions": await client.predict_category(title)}
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.get("/categories/{category_id}/attributes")
async def get_category_attributes(category_id: str):
    """Atributos da categoria — mostra o que é obrigatório para publicar."""
    client = MercadoLivreClient()
    try:
        attributes = await client.get_category_attributes(category_id)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    required = [a for a in attributes if a.get("tags", {}).get("required")]
    return {
        "category_id": category_id,
        "total_attributes": len(attributes),
        "required_count": len(required),
        "required": required,
        "attributes": attributes,
    }


@router.get("/categories")
async def list_root_categories():
    """Categorias raiz do site configurado (MLB para Brasil)."""
    client = MercadoLivreClient()
    try:
        return {"site_id": settings.ML_SITE_ID, "categories": await client.get_site_categories()}
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.post("/categories/map")
async def create_category_map(payload: CategoryMapRequest):
    """Cria o De-Para entre a categoria interna e a do Mercado Livre."""
    client = MercadoLivreClient()
    try:
        category = await client.get_category(payload.ml_category_id)
        attributes = await client.get_category_attributes(payload.ml_category_id)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    path = " > ".join(p.get("name", "") for p in category.get("path_from_root", []))
    required = [
        {"id": a.get("id"), "name": a.get("name"), "value_type": a.get("value_type")}
        for a in attributes if a.get("tags", {}).get("required")
    ]

    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(MLCategoryMapDB).where(
                MLCategoryMapDB.internal_category == payload.internal_category
            )
        )
        mapping = result.scalars().first() or MLCategoryMapDB(
            internal_category=payload.internal_category
        )
        mapping.ml_category_id = payload.ml_category_id
        mapping.ml_category_path = path
        mapping.site_id = settings.ML_SITE_ID
        mapping.required_attributes_json = json.dumps(required)
        session.add(mapping)
        await session.commit()

    return {
        "internal_category": payload.internal_category,
        "ml_category_id": payload.ml_category_id,
        "ml_category_path": path,
        "required_attributes": required,
    }


@router.get("/categories/map")
async def list_category_maps():
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(MLCategoryMapDB))
        mappings = result.scalars().all()

    return {
        "total": len(mappings),
        "mappings": [
            {
                "id": m.id,
                "internal_category": m.internal_category,
                "ml_category_id": m.ml_category_id,
                "ml_category_path": m.ml_category_path,
                "required_attributes": json.loads(m.required_attributes_json),
            }
            for m in mappings
        ],
    }


# ---------------------------------------------------------------------------
# Pedidos
# ---------------------------------------------------------------------------

@router.get("/orders")
async def list_ml_orders(
    status: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    """Pedidos do Mercado Livre já sincronizados."""
    await init_db()
    async with async_session() as session:
        query = select(MLOrderDB)
        count_query = select(func.count(MLOrderDB.id))
        if status:
            query = query.where(MLOrderDB.status == status)
            count_query = count_query.where(MLOrderDB.status == status)

        total = (await session.execute(count_query)).scalar() or 0
        result = await session.execute(
            query.order_by(MLOrderDB.date_created.desc()).limit(limit).offset(offset)
        )
        orders = result.scalars().all()

    return {
        "total": total,
        "orders": [
            {
                "id": o.id,
                "status": o.status,
                "status_detail": o.status_detail,
                "buyer": o.buyer_nickname,
                "total_amount": o.total_amount,
                "paid_amount": o.paid_amount,
                "currency": o.currency_id,
                "shipping_id": o.shipping_id,
                "shipping_status": o.shipping_status,
                "tracking_number": o.tracking_number,
                "items": json.loads(o.items_json),
                "date_created": o.date_created.isoformat() if o.date_created else None,
            }
            for o in orders
        ],
    }


@router.get("/orders/{order_id}")
async def get_ml_order(order_id: str, refresh: bool = Query(False)):
    """Detalhe do pedido. Com ``refresh=true`` busca ao vivo no Mercado Livre."""
    if refresh:
        account = await _require_account()
        client = await build_client(account)
        try:
            return await client.get_order(order_id)
        except MercadoLivreError as exc:
            raise _handle_ml_error(exc)

    async with async_session() as session:
        order = await session.get(MLOrderDB, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Pedido não encontrado na base local.")

    return {
        "id": order.id,
        "status": order.status,
        "buyer": order.buyer_nickname,
        "total_amount": order.total_amount,
        "shipping_id": order.shipping_id,
        "tracking_number": order.tracking_number,
        "items": json.loads(order.items_json),
    }


# ---------------------------------------------------------------------------
# Envios
# ---------------------------------------------------------------------------

@router.get("/shipments/{shipment_id}")
async def get_shipment(shipment_id: str, ml_user_id: Optional[int] = Query(None)):
    """Detalhe do envio (status, rastreio, endereço, modalidade)."""
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        return await client.get_shipment(shipment_id)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


@router.get("/shipments/{shipment_id}/label")
async def get_shipment_label(
    shipment_id: str,
    response_type: str = Query("pdf", pattern="^(pdf|zpl2)$"),
    ml_user_id: Optional[int] = Query(None),
):
    """Baixa a etiqueta de envio. ``zpl2`` sai pronta para impressora térmica."""
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        content = await client.get_shipment_labels([shipment_id], response_type=response_type)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    media_type = "application/pdf" if response_type == "pdf" else "text/plain"
    extension = "pdf" if response_type == "pdf" else "zpl"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="etiqueta-{shipment_id}.{extension}"'},
    )


# ---------------------------------------------------------------------------
# Perguntas
# ---------------------------------------------------------------------------

@router.get("/questions")
async def list_questions(status: str = Query("UNANSWERED"), limit: int = Query(100, le=500)):
    """Perguntas dos compradores já sincronizadas."""
    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(MLQuestionDB)
            .where(MLQuestionDB.status == status)
            .order_by(MLQuestionDB.date_created.desc())
            .limit(limit)
        )
        questions = result.scalars().all()

    return {
        "total": len(questions),
        "questions": [
            {
                "id": q.id,
                "item_id": q.item_id,
                "text": q.text,
                "status": q.status,
                "answer": q.answer_text,
                "date_created": q.date_created.isoformat() if q.date_created else None,
            }
            for q in questions
        ],
    }


@router.post("/questions/{question_id}/answer")
async def answer_question(question_id: int, payload: AnswerRequest,
                          ml_user_id: Optional[int] = Query(None)):
    """Responde uma pergunta no anúncio."""
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        await client.answer_question(question_id, payload.text)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    async with async_session() as session:
        row = await session.get(MLQuestionDB, str(question_id))
        if row:
            row.status = "ANSWERED"
            row.answer_text = payload.text
        await session.commit()

    return {"question_id": question_id, "status": "ANSWERED", "answer": payload.text}


# ---------------------------------------------------------------------------
# Métricas e taxas
# ---------------------------------------------------------------------------

@router.get("/fees/simulate")
async def simulate_fees(
    price: float = Query(..., gt=0),
    category_id: Optional[str] = Query(None),
    listing_type_id: str = Query("gold_special"),
):
    """Simula a comissão do Mercado Livre e devolve o valor líquido estimado."""
    client = MercadoLivreClient()
    try:
        fees = await client.get_listing_fees(price, category_id, listing_type_id)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)

    sale_fee = float(fees.get("sale_fee_amount") or 0.0)
    listing_fee = float(fees.get("listing_fee_amount") or 0.0)
    return {
        "price": price,
        "sale_fee_amount": sale_fee,
        "listing_fee_amount": listing_fee,
        "net_amount": round(price - sale_fee - listing_fee, 2),
        "listing_type_id": listing_type_id,
        "raw": fees,
    }


@router.get("/listings/{item_id}/visits")
async def get_listing_visits(item_id: str, last: int = Query(30, ge=1, le=150),
                             ml_user_id: Optional[int] = Query(None)):
    """Visitas do anúncio nos últimos N dias."""
    account = await _require_account(ml_user_id)
    client = await build_client(account)
    try:
        return await client.get_item_visits(item_id, last=last)
    except MercadoLivreError as exc:
        raise _handle_ml_error(exc)


# ---------------------------------------------------------------------------
# Webhooks
# ---------------------------------------------------------------------------

@router.post("/webhooks")
async def receive_webhook(request: Request):
    """Recebe notificações do Mercado Livre.

    O ML espera resposta HTTP 200 em até 500ms, senão reenvia. Por isso aqui
    apenas gravamos o evento e devolvemos 200; o processamento acontece em
    POST /ml/webhooks/process.
    """
    try:
        payload = await request.json()
    except (ValueError, TypeError):
        payload = {}

    await init_db()
    async with async_session() as session:
        session.add(MLWebhookEventDB(
            topic=payload.get("topic", ""),
            resource=payload.get("resource", ""),
            ml_user_id=int(payload.get("user_id") or 0),
            application_id=str(payload.get("application_id", "")),
            attempts=int(payload.get("attempts") or 1),
            payload_json=json.dumps(payload)[:20000],
        ))
        await session.commit()

    return {"received": True}


@router.post("/webhooks/process")
async def process_webhooks(limit: int = Query(50, le=200)):
    """Processa a fila de notificações pendentes.

    Notificações trazem só o ponteiro do recurso (ex.: ``/orders/123``); o
    conteúdo é buscado aqui e gravado na base.
    """
    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(MLWebhookEventDB)
            .where(MLWebhookEventDB.processed == False)  # noqa: E712
            .order_by(MLWebhookEventDB.received_at)
            .limit(limit)
        )
        events = result.scalars().all()
        pending = [
            {"id": e.id, "topic": e.topic, "resource": e.resource, "ml_user_id": e.ml_user_id}
            for e in events
        ]

    processed, errors = 0, []
    for event in pending:
        try:
            account = await get_account(event["ml_user_id"] or None)
            if not account:
                raise MercadoLivreError("Conta do vendedor não conectada.")

            client = await build_client(account)
            resource = await client.fetch_resource(event["resource"])

            topic = event["topic"]
            if topic in ("orders_v2", "orders"):
                await ml_sync_service.sync_orders(account, max_orders=50)
            elif topic == "items":
                await ml_sync_service.sync_listings(account, max_items=200)
            elif topic == "questions":
                await ml_sync_service.sync_questions(account)

            async with async_session() as session:
                row = await session.get(MLWebhookEventDB, event["id"])
                if row:
                    row.processed = True
                await session.commit()
            processed += 1

        except (MercadoLivreError, HTTPException) as exc:
            message = exc.message if isinstance(exc, MercadoLivreError) else str(exc.detail)
            errors.append({"event_id": event["id"], "error": message})
            async with async_session() as session:
                row = await session.get(MLWebhookEventDB, event["id"])
                if row:
                    row.error = message
                await session.commit()

    return {"pending_found": len(pending), "processed": processed, "errors": errors}


@router.get("/webhooks/events")
async def list_webhook_events(processed: Optional[bool] = Query(None), limit: int = Query(100, le=500)):
    """Histórico de notificações recebidas — útil para depurar a integração."""
    await init_db()
    async with async_session() as session:
        query = select(MLWebhookEventDB)
        if processed is not None:
            query = query.where(MLWebhookEventDB.processed == processed)
        result = await session.execute(
            query.order_by(MLWebhookEventDB.received_at.desc()).limit(limit)
        )
        events = result.scalars().all()

    return {
        "total": len(events),
        "events": [
            {
                "id": e.id,
                "topic": e.topic,
                "resource": e.resource,
                "ml_user_id": e.ml_user_id,
                "attempts": e.attempts,
                "processed": e.processed,
                "error": e.error,
                "received_at": e.received_at.isoformat() if e.received_at else None,
            }
            for e in events
        ],
    }
