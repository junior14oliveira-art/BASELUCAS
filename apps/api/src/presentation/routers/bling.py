"""Rotas Bling ERP API v3 — conexão UI + Macro Fiscal (Etapa 2).

  GET    /bling/status
  POST   /bling/credentials      (Client ID + Secret via UI)
  POST   /bling/tokens           (colar access/refresh manual)
  DELETE /bling/connection
  POST   /bling/test
  GET    /bling/auth             → OAuth (JSON ou redirect)
  GET    /bling/callback         → troca code → BlingConfigDB
  POST   /bling/orders/{id}/push
  POST   /bling/orders/auto-push-paid
  POST   /bling/orders/{id}/issue-nfe
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
from src.infrastructure import bling_service
from src.infrastructure.bling_client import (
    BlingAuthError,
    BlingClient,
    BlingError,
    BlingNfeDisabledError,
    BlingReadOnlyError,
    bling_read_only,
    build_authorize_url,
    exchange_code_for_tokens,
    is_app_configured,
    nfe_emit_enabled,
    resolve_app_credentials,
)
from src.infrastructure.database import BlingConfigDB, RealOrderDB, async_session, init_db

router = APIRouter(prefix="/bling", tags=["Bling ERP"])

_oauth_states: Dict[str, Dict[str, Any]] = {}


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


def _purge_states() -> None:
    now = time.time()
    for k, entry in list(_oauth_states.items()):
        if float(entry.get("exp") or 0) < now:
            _oauth_states.pop(k, None)


def _mask(value: str, keep: int = 4) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    if len(v) <= keep:
        return "*" * len(v)
    return ("*" * max(len(v) - keep, 4)) + v[-keep:]


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


def _status_payload(row: Optional[BlingConfigDB], *, all_rows: Optional[list] = None) -> Dict[str, Any]:
    client_id, client_secret = resolve_app_credentials(row)
    app_ok = bool(client_id and client_secret)
    has_token = bool(row and (row.access_token or "").strip())
    token_expired = False
    if row and row.expires_at and row.expires_at > 0:
        token_expired = time.time() >= float(row.expires_at)

    if has_token and not token_expired:
        ui_status = "configured"
        ui_label = "Configurado (token ativo — NF-e aguarda homologação)"
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

    accounts = []
    for r in all_rows or ([row] if row else []):
        if not r:
            continue
        accounts.append(
            {
                "account_key": r.account_key,
                "account_label": r.account_label,
                "has_token": bool((r.access_token or "").strip()),
                "token_expired": bool(r.expires_at and r.expires_at > 0 and time.time() >= r.expires_at),
                "is_active": r.is_active,
                "connected_at": r.connected_at.isoformat() if r.connected_at else None,
            }
        )

    return {
        "ok": True,
        "account_key": _account_key(row.account_key if row else None),
        "account_label": (row.account_label if row else "Bling ERP") or "Bling ERP",
        "app_configured": app_ok,
        "has_access_token": has_token,
        "oauth_token_present": has_token and not token_expired,
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
        "live_api": False,
        "accounts": accounts,
        "auth_url": f"{settings.API_V1_STR}/bling/auth?redirect=true",
        "setup_hint": (
            None if app_ok else "Informe Client ID/Secret no card Bling ou em apps/api/.env"
        ),
    }


@router.get("/status")
async def bling_status(account_key: Optional[str] = None):
    """Status honesto para o card Bling na UI /app (sem expor secrets)."""
    await init_db()
    async with async_session() as session:
        all_rows = list((await session.execute(select(BlingConfigDB))).scalars().all())
    row = await load_bling_row(account_key)
    if not row and all_rows:
        row = all_rows[0]
    return _status_payload(row, all_rows=all_rows)


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


@router.get("/auth")
async def bling_auth_start(
    redirect: bool = Query(True, description="Se true, redireciona ao Bling"),
    account_key: Optional[str] = None,
):
    _purge_states()
    row = await load_bling_row(account_key)
    cid, csec = resolve_app_credentials(row)
    if not (cid and csec):
        raise HTTPException(
            status_code=412,
            detail={
                "message": "Informe Client ID e Client Secret no card Bling antes do OAuth.",
                "ui_status": "awaiting_credentials",
            },
        )
    settings.BLING_CLIENT_ID = cid
    settings.BLING_CLIENT_SECRET = csec
    state = secrets.token_urlsafe(24)
    _oauth_states[state] = {"exp": time.time() + 600, "account_key": _account_key(account_key)}
    try:
        url = build_authorize_url(state=state, row=row)
    except BlingAuthError as exc:
        raise HTTPException(status_code=412, detail=exc.message) from exc
    if redirect:
        return RedirectResponse(url)
    return {"authorize_url": url, "state": state, "redirect_uri": settings.BLING_REDIRECT_URI}


@router.get("/callback")
async def bling_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    if error:
        msg = quote(error_description or error)
        return RedirectResponse(url=f"/app?tab=marketplaces&bling_error={msg}", status_code=302)
    if not code:
        return RedirectResponse(url="/app?tab=marketplaces&bling_error=missing_code", status_code=302)

    _purge_states()
    entry = _oauth_states.pop(state, None) if state else None
    account_key = _account_key((entry or {}).get("account_key") if entry else None)

    row = await load_bling_row(account_key)
    cid, csec = resolve_app_credentials(row)
    if not (cid and csec):
        return RedirectResponse(url="/app?tab=marketplaces&bling_error=app_not_configured", status_code=302)
    settings.BLING_CLIENT_ID = cid
    settings.BLING_CLIENT_SECRET = csec

    try:
        tokens = await exchange_code_for_tokens(code)
    except BlingAuthError as exc:
        return RedirectResponse(
            url=f"/app?tab=marketplaces&bling_error={quote(str(exc)[:180])}",
            status_code=302,
        )

    await bling_service.save_bling_tokens(tokens, account_key=account_key)
    return RedirectResponse(url="/app?tab=marketplaces&bling=ok", status_code=302)


@router.post("/orders/{order_id}/push")
async def push_order(
    order_id: str,
    dry_run: bool = Query(False),
    force: bool = Query(False),
    emit_nfe: bool = Query(True),
):
    result = await bling_service.push_order_to_bling(
        order_id, dry_run=dry_run, force=force, emit_nfe=emit_nfe
    )
    if not result.get("ok") and result.get("error") == "Pedido não encontrado no SQLite local.":
        raise HTTPException(status_code=404, detail=result)
    return result


@router.post("/orders/auto-push-paid")
async def auto_push_paid(limit: int = Query(25, ge=1, le=100)):
    return await bling_service.auto_push_paid_orders(limit=limit)


@router.post("/orders/{order_id}/issue-nfe")
async def issue_nfe_only(order_id: str, dry_run: bool = Query(False)):
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if not order:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        if not (order.bling_pedido_id or "").strip():
            raise HTTPException(
                status_code=409,
                detail={"message": "Sem bling_pedido_id. Faça POST .../push antes."},
            )
        nfe_body = bling_service.build_nfe_payload(order, order.bling_pedido_id)

    if dry_run:
        return {"ok": True, "dry_run": True, "nfe_payload": nfe_body, "nfe_emit_enabled": nfe_emit_enabled()}

    if not nfe_emit_enabled():
        return {
            "ok": False,
            "blocked": True,
            "reason": "nfe_emit_enabled=false",
            "nfe_payload_preview": nfe_body,
        }

    if bling_read_only():
        return {"ok": False, "blocked": True, "reason": "bling_read_only", "nfe_payload_preview": nfe_body}

    client, _ = await bling_service.build_client()
    if not client:
        raise HTTPException(status_code=412, detail="Sem token OAuth Bling.")

    try:
        resp = await client.create_nfe(nfe_body, allow_write=True, allow_nfe=True)
    except (BlingNfeDisabledError, BlingReadOnlyError) as exc:
        return {"ok": False, "blocked": True, "error": exc.message, "nfe_payload_preview": nfe_body}
    except BlingError as exc:
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail={"message": exc.message, "bling_payload": exc.payload},
        ) from exc

    data = resp.get("data") if isinstance(resp.get("data"), dict) else resp
    nfe_id = str(data.get("id") or "") if isinstance(data, dict) else ""
    async with async_session() as session:
        result = await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        order = result.scalar_one_or_none()
        if order:
            order.bling_nfe_id = nfe_id
            order.bling_status = "nfe_solicitada"
            order.bling_last_error = ""
            await session.commit()

    return {"ok": True, "bling_nfe_id": nfe_id, "response": resp, "bling_status": "nfe_solicitada"}
