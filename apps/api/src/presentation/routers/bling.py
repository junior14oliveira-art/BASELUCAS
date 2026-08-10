"""Router Bling ERP v3 — status, credenciais na UI e OAuth.

GET  /api/v1/bling/status
POST /api/v1/bling/credentials   (Client ID + Secret do app)
POST /api/v1/bling/tokens        (colar access/refresh manualmente)
GET  /api/v1/bling/auth          (redirect OAuth)
GET  /api/v1/bling/callback      (troca code → tokens)
DELETE /api/v1/bling/connection  (limpa tokens; mantém client_id/secret opcional)
"""

from __future__ import annotations

import secrets
import time
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.config import settings
from src.infrastructure.bling_client import (
    BlingAuthError,
    BlingClient,
    BlingError,
    bling_read_only,
    build_authorize_url,
    exchange_code_for_tokens,
    is_app_configured,
    nfe_emit_enabled,
    resolve_app_credentials,
)
from src.infrastructure.database import BlingConfigDB, async_session, init_db

router = APIRouter(prefix="/bling", tags=["Bling ERP"])


class BlingCredentialsBody(BaseModel):
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    account_key: Optional[str] = None
    account_label: Optional[str] = None


class BlingTokensBody(BaseModel):
    access_token: str = Field(..., min_length=1)
    refresh_token: str = ""
    expires_in: Optional[int] = None
    account_key: Optional[str] = None


def _account_key(override: Optional[str] = None) -> str:
    return (override or settings.BLING_ACCOUNT_KEY or "4mc").strip() or "4mc"


async def _get_or_create_row(session, account_key: str) -> BlingConfigDB:
    result = await session.execute(
        select(BlingConfigDB).where(BlingConfigDB.account_key == account_key)
    )
    row = result.scalar_one_or_none()
    if row:
        return row
    row = BlingConfigDB(
        account_key=account_key,
        account_label=f"Bling {account_key.upper()}",
    )
    session.add(row)
    await session.flush()
    return row


async def load_bling_row(account_key: Optional[str] = None) -> Optional[BlingConfigDB]:
    await init_db()
    key = _account_key(account_key)
    async with async_session() as session:
        result = await session.execute(
            select(BlingConfigDB).where(BlingConfigDB.account_key == key)
        )
        return result.scalar_one_or_none()


def _mask(value: str, keep: int = 4) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= keep:
        return "*" * len(v)
    return ("*" * max(len(v) - keep, 4)) + v[-keep:]


def _status_payload(row: Optional[BlingConfigDB]) -> Dict[str, Any]:
    client_id, client_secret = resolve_app_credentials(row)
    app_ok = bool(client_id and client_secret)
    has_token = bool(row and (row.access_token or "").strip())
    token_expired = False
    if row and row.expires_at and row.expires_at > 0:
        token_expired = time.time() >= float(row.expires_at)

    if has_token and not token_expired:
        ui_status = "configured"
        ui_label = "Configurado (token ativo — NF-e aguardando homologação)"
        color = "amber"
    elif has_token and token_expired:
        ui_status = "awaiting_credentials"
        ui_label = "Token expirado — reconecte OAuth ou cole novo token"
        color = "amber"
    elif app_ok:
        ui_status = "awaiting_credentials"
        ui_label = "App configurado — conclua OAuth ou cole o access token"
        color = "amber"
    else:
        ui_status = "not_configured"
        ui_label = "Não configurado — clique para informar Client ID / Secret"
        color = "muted"

    # Nunca "connected" sem uso real de API fiscal — honestidade do hub
    return {
        "ok": True,
        "account_key": _account_key(row.account_key if row else None),
        "account_label": (row.account_label if row else "Bling ERP") or "Bling ERP",
        "app_configured": app_ok,
        "has_access_token": has_token,
        "token_expired": token_expired,
        "client_id_masked": _mask(client_id, 6),
        "has_client_secret": bool(client_secret),
        "connected_at": row.connected_at.isoformat() if row and row.connected_at else None,
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
        "last_error": (row.last_error if row else "") or "",
        "bling_read_only": bling_read_only(),
        "nfe_emit_enabled": nfe_emit_enabled(),
        "redirect_uri": settings.BLING_REDIRECT_URI,
        "ui_status": ui_status,
        "ui_label": ui_label,
        "ui_color": color,
        "auth_url": f"{settings.API_V1_STR}/bling/auth",
    }


@router.get("/status")
async def bling_status(account_key: Optional[str] = None):
    """Status honesto para o card Bling na UI /app (sem expor secrets)."""
    row = await load_bling_row(account_key)
    return _status_payload(row)


@router.post("/credentials")
async def save_credentials(body: BlingCredentialsBody):
    """Salva Client ID + Client Secret do app Bling (developer.bling.com.br)."""
    await init_db()
    key = _account_key(body.account_key)
    async with async_session() as session:
        row = await _get_or_create_row(session, key)
        row.client_id = body.client_id.strip()
        row.client_secret = body.client_secret.strip()
        if body.account_label:
            row.account_label = body.account_label.strip()
        row.updated_at = datetime.now()
        row.last_error = ""
        await session.commit()
        await session.refresh(row)
        # Espelha em settings para OAuth na mesma sessão do processo
        settings.BLING_CLIENT_ID = row.client_id
        settings.BLING_CLIENT_SECRET = row.client_secret
        return {
            "ok": True,
            "message": "Credenciais do app Bling salvas. Conclua o OAuth ou cole o access token.",
            "status": _status_payload(row),
        }


@router.post("/tokens")
async def save_tokens(body: BlingTokensBody):
    """Cola access_token (+ refresh opcional) sem passar pelo browser OAuth."""
    await init_db()
    key = _account_key(body.account_key)
    expires_in = int(body.expires_in or 21600)
    async with async_session() as session:
        row = await _get_or_create_row(session, key)
        row.access_token = body.access_token.strip()
        if body.refresh_token is not None:
            row.refresh_token = (body.refresh_token or "").strip()
        row.expires_at = time.time() + expires_in
        row.token_type = "Bearer"
        row.is_active = True
        row.connected_at = datetime.now()
        row.updated_at = datetime.now()
        row.last_error = ""
        await session.commit()
        await session.refresh(row)
        return {
            "ok": True,
            "message": "Tokens Bling salvos no SQLite.",
            "status": _status_payload(row),
        }


@router.delete("/connection")
async def clear_connection(
    account_key: Optional[str] = None,
    clear_app: bool = Query(False, description="Também apaga client_id/secret"),
):
    await init_db()
    key = _account_key(account_key)
    async with async_session() as session:
        result = await session.execute(
            select(BlingConfigDB).where(BlingConfigDB.account_key == key)
        )
        row = result.scalar_one_or_none()
        if not row:
            return {"ok": True, "message": "Nenhuma conexão Bling para limpar."}
        row.access_token = ""
        row.refresh_token = ""
        row.expires_at = 0.0
        row.connected_at = None
        row.last_error = ""
        row.updated_at = datetime.now()
        if clear_app:
            row.client_id = ""
            row.client_secret = ""
            settings.BLING_CLIENT_ID = ""
            settings.BLING_CLIENT_SECRET = ""
        await session.commit()
        await session.refresh(row)
        return {"ok": True, "message": "Conexão Bling limpa.", "status": _status_payload(row)}


@router.get("/auth")
async def bling_auth_start(account_key: Optional[str] = None):
    """Inicia OAuth: redireciona para o Bling."""
    row = await load_bling_row(account_key)
    cid, csec = resolve_app_credentials(row)
    if not (cid and csec):
        raise HTTPException(
            status_code=400,
            detail="Informe Client ID e Client Secret no card Bling antes do OAuth.",
        )
    settings.BLING_CLIENT_ID = cid
    settings.BLING_CLIENT_SECRET = csec
    state = secrets.token_urlsafe(24)
    # Guarda state + account em SyncMeta seria ideal; state curto no cookie via query no callback
    # Usamos state = account_key|nonce
    state_full = f"{_account_key(account_key)}.{state}"
    try:
        url = build_authorize_url(state=state_full)
    except BlingAuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RedirectResponse(url=url, status_code=302)


@router.get("/callback")
async def bling_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """Callback OAuth Bling → grava tokens e volta para /app."""
    if error:
        msg = quote(error_description or error)
        return RedirectResponse(url=f"/app?bling_error={msg}", status_code=302)
    if not code:
        return RedirectResponse(url="/app?bling_error=missing_code", status_code=302)

    account_key = _account_key()
    if state and "." in state:
        account_key = state.split(".", 1)[0] or account_key

    row = await load_bling_row(account_key)
    cid, csec = resolve_app_credentials(row)
    if not (cid and csec):
        return RedirectResponse(url="/app?bling_error=app_not_configured", status_code=302)
    settings.BLING_CLIENT_ID = cid
    settings.BLING_CLIENT_SECRET = csec

    try:
        tokens = await exchange_code_for_tokens(code)
    except BlingAuthError as exc:
        await init_db()
        async with async_session() as session:
            row2 = await _get_or_create_row(session, account_key)
            row2.last_error = str(exc)
            row2.updated_at = datetime.now()
            await session.commit()
        return RedirectResponse(url=f"/app?bling_error={quote(str(exc)[:180])}", status_code=302)

    expires_in = float(tokens.get("expires_in") or 21600)
    await init_db()
    async with async_session() as session:
        row3 = await _get_or_create_row(session, account_key)
        row3.access_token = str(tokens.get("access_token") or "")
        row3.refresh_token = str(tokens.get("refresh_token") or row3.refresh_token or "")
        row3.expires_at = time.time() + expires_in
        row3.scopes = str(tokens.get("scope") or tokens.get("scopes") or "")
        row3.token_type = str(tokens.get("token_type") or "Bearer")
        row3.is_active = True
        row3.connected_at = datetime.now()
        row3.updated_at = datetime.now()
        row3.last_error = ""
        await session.commit()

    return RedirectResponse(url="/app?tab=marketplaces&bling=ok", status_code=302)


@router.post("/test")
async def test_bling_connection(account_key: Optional[str] = None):
    """GET /empresas/meus-dados — valida token sem marcar 'Conectado' fiscal."""
    row = await load_bling_row(account_key)
    if not row or not (row.access_token or "").strip():
        raise HTTPException(status_code=400, detail="Sem access_token — salve tokens ou conclua OAuth.")

    async def _persist_refresh(data: Dict[str, Any]) -> None:
        async with async_session() as session:
            r = await _get_or_create_row(session, _account_key(account_key))
            r.access_token = data.get("access_token") or r.access_token
            r.refresh_token = data.get("refresh_token") or r.refresh_token
            r.expires_at = float(data.get("expires_at") or r.expires_at or 0)
            r.updated_at = datetime.now()
            await session.commit()

    client = BlingClient(
        access_token=row.access_token,
        refresh_token=row.refresh_token,
        expires_at=float(row.expires_at or 0),
        on_token_refresh=_persist_refresh,
    )
    try:
        data = await client.get_empresa()
    except BlingError as exc:
        async with async_session() as session:
            r = await _get_or_create_row(session, _account_key(account_key))
            r.last_error = str(exc)
            r.updated_at = datetime.now()
            await session.commit()
        raise HTTPException(status_code=exc.status_code or 502, detail=str(exc)) from exc

    return {
        "ok": True,
        "message": "Token Bling válido (leitura empresa).",
        "empresa": data.get("data") if isinstance(data, dict) else data,
        "status": _status_payload(await load_bling_row(account_key)),
        "note": "Status UI permanece 'Configurado' até emissão NF-e homologada.",
    }
