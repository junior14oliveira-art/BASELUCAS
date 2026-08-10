"""Cliente HTTP da API Bling v3 (OAuth2 + rate limit 3 req/s).

Defaults seguros:
  BLING_READ_ONLY=true  → bloqueia POST/PUT/PATCH/DELETE (só GET)
  NFE_EMIT_ENABLED=false → bloqueia POST /nfe mesmo com READ_ONLY=false

Não inventa "conectado": use is_app_configured() / tokens no SQLite.
"""

from __future__ import annotations

import asyncio
import base64
import time
from typing import Any, Awaitable, Callable, Dict, Optional
from urllib.parse import urlencode

import httpx

from src.config import settings

BLING_API_BASE = (settings.BLING_API_BASE_URL or "https://api.bling.com.br/Api/v3").rstrip("/")
BLING_OAUTH_BASE = (settings.BLING_AUTH_BASE_URL or "https://www.bling.com.br/Api/v3/oauth").rstrip("/")

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class BlingError(Exception):
    def __init__(self, message: str, status_code: int = 0, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


class BlingAuthError(BlingError):
    pass


class BlingReadOnlyError(BlingError):
    pass


class BlingNfeDisabledError(BlingError):
    pass


class _RateLimiter:
    """Bling: máx. 3 req/s — intervalo mínimo ~0.34s + semáforo."""

    def __init__(self, max_concurrent: int = 2, min_interval: float = 0.35):
        self._sem = asyncio.Semaphore(max_concurrent)
        self._min_interval = min_interval
        self._last_call = 0.0
        self._lock = asyncio.Lock()

    async def __aenter__(self):
        await self._sem.acquire()
        async with self._lock:
            delta = time.monotonic() - self._last_call
            if delta < self._min_interval:
                await asyncio.sleep(self._min_interval - delta)
            self._last_call = time.monotonic()
        return self

    async def __aexit__(self, *exc):
        self._sem.release()
        return False


_rate_limiter = _RateLimiter()


def resolve_app_credentials(row: Any = None) -> tuple[str, str]:
    """Client ID/Secret: preferência pela linha SQLite; fallback .env/settings."""
    cid = ""
    csec = ""
    if row is not None:
        cid = (getattr(row, "client_id", None) or "").strip()
        csec = (getattr(row, "client_secret", None) or "").strip()
    if not cid:
        cid = (settings.BLING_CLIENT_ID or "").strip()
    if not csec:
        csec = (settings.BLING_CLIENT_SECRET or "").strip()
    return cid, csec


def is_app_configured(row: Any = None) -> bool:
    """True se client_id/secret existem (SQLite ou .env). Sem token = Aguardando OAuth."""
    cid, csec = resolve_app_credentials(row)
    return bool(cid and csec)


def bling_read_only() -> bool:
    return bool(getattr(settings, "BLING_READ_ONLY", True))


def nfe_emit_enabled() -> bool:
    return bool(getattr(settings, "NFE_EMIT_ENABLED", False))


def build_authorize_url(*, state: str, redirect_uri: Optional[str] = None, row: Any = None) -> str:
    cid, _csec = resolve_app_credentials(row)
    if not is_app_configured(row):
        raise BlingAuthError(
            "BLING_CLIENT_ID / BLING_CLIENT_SECRET ausentes — "
            "informe no card Bling da UI ou no .env (developer.bling.com.br)."
        )
    params = {
        "response_type": "code",
        "client_id": cid,
        "state": state,
    }
    # redirect_uri é configurado no painel do app Bling; alguns apps aceitam na query
    uri = (redirect_uri or settings.BLING_REDIRECT_URI or "").strip()
    if uri:
        params["redirect_uri"] = uri
    return f"{BLING_OAUTH_BASE}/authorize?{urlencode(params)}"


def _basic_auth_header(row: Any = None) -> str:
    cid, csec = resolve_app_credentials(row)
    raw = f"{cid}:{csec}"
    return "Basic " + base64.b64encode(raw.encode()).decode()


async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Troca authorization_code por access_token + refresh_token."""
    if not is_app_configured():
        raise BlingAuthError("App Bling não configurado (CLIENT_ID/SECRET).")
    data = {
        "grant_type": "authorization_code",
        "code": code,
    }
    uri = (settings.BLING_REDIRECT_URI or "").strip()
    if uri:
        data["redirect_uri"] = uri
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{BLING_OAUTH_BASE}/token",
            data=data,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
    payload = _safe_json(resp)
    if resp.status_code >= 400:
        raise BlingAuthError(
            f"Falha ao trocar code por token Bling ({resp.status_code})",
            status_code=resp.status_code,
            payload=payload if isinstance(payload, dict) else {"raw": payload},
        )
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise BlingAuthError("Resposta OAuth Bling sem access_token", payload={"raw": payload})
    return payload


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    if not is_app_configured():
        raise BlingAuthError("App Bling não configurado (CLIENT_ID/SECRET).")
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{BLING_OAUTH_BASE}/token",
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
    payload = _safe_json(resp)
    if resp.status_code >= 400:
        raise BlingAuthError(
            f"Falha no refresh token Bling ({resp.status_code})",
            status_code=resp.status_code,
            payload=payload if isinstance(payload, dict) else {"raw": payload},
        )
    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise BlingAuthError("Refresh Bling sem access_token", payload={"raw": payload})
    return payload


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"text": (resp.text or "")[:500]}


class BlingClient:
    """Cliente autenticado. Persistência de tokens via on_token_refresh."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        expires_at: float = 0.0,
        on_token_refresh: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        self.access_token = access_token or ""
        self.refresh_token = refresh_token or ""
        self.expires_at = float(expires_at or 0.0)
        self.on_token_refresh = on_token_refresh
        self._refresh_lock = asyncio.Lock()

    async def ensure_token(self) -> str:
        if not self.access_token:
            raise BlingAuthError("Sem access_token Bling — conclua o OAuth em GET /api/v1/bling/auth.")
        # Renova 2 min antes de expirar
        if self.expires_at > 0 and time.time() >= (self.expires_at - 120):
            await self._do_refresh()
        return self.access_token

    async def _do_refresh(self) -> None:
        async with self._refresh_lock:
            if self.expires_at > 0 and time.time() < (self.expires_at - 120):
                return
            if not self.refresh_token:
                raise BlingAuthError("Token Bling expirado e sem refresh_token.")
            data = await refresh_access_token(self.refresh_token)
            self.access_token = str(data.get("access_token") or "")
            if data.get("refresh_token"):
                self.refresh_token = str(data["refresh_token"])
            expires_in = float(data.get("expires_in") or 21600)
            self.expires_at = time.time() + expires_in
            if self.on_token_refresh:
                await self.on_token_refresh(
                    {
                        "access_token": self.access_token,
                        "refresh_token": self.refresh_token,
                        "expires_at": self.expires_at,
                        "expires_in": expires_in,
                        "scope": data.get("scope") or data.get("scopes") or "",
                        "token_type": data.get("token_type") or "Bearer",
                    }
                )

    async def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        allow_write: bool = False,
        allow_nfe: bool = False,
    ) -> Dict[str, Any]:
        method_u = method.upper()
        path_norm = path if path.startswith("/") else f"/{path}"

        path_base = path_norm.split("?", 1)[0].rstrip("/")
        is_nfe_create = method_u == "POST" and path_base == "/nfe"

        if method_u in WRITE_METHODS:
            if bling_read_only() and not allow_write:
                raise BlingReadOnlyError(
                    f"Bloqueado: BLING_READ_ONLY=true — {method_u} {path_norm} "
                    "alteraria dados no Bling. Para homologação: BLING_READ_ONLY=false "
                    "(mantenha NFE_EMIT_ENABLED=false até autorizar emissão)."
                )
            if is_nfe_create and (not nfe_emit_enabled() or not allow_nfe):
                raise BlingNfeDisabledError(
                    "Bloqueado: NFE_EMIT_ENABLED=false — emissão de NF-e desligada "
                    "até homologação. Pedido de venda pode ser criado com "
                    "BLING_READ_ONLY=false sem emitir nota."
                )

        token = await self.ensure_token()
        url = f"{BLING_API_BASE}{path_norm}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        async with _rate_limiter:
            async with httpx.AsyncClient(timeout=45.0) as client:
                resp = await client.request(
                    method_u, url, headers=headers, json=json_body, params=params
                )

        # Token inválido → tenta refresh uma vez
        if resp.status_code == 401 and self.refresh_token:
            await self._do_refresh()
            headers["Authorization"] = f"Bearer {self.access_token}"
            async with _rate_limiter:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.request(
                        method_u, url, headers=headers, json=json_body, params=params
                    )

        payload = _safe_json(resp)
        if resp.status_code >= 400:
            msg = "Erro na API Bling"
            if isinstance(payload, dict):
                err = payload.get("error") or payload.get("message") or payload
                msg = f"Bling {resp.status_code}: {err}"
            raise BlingError(msg, status_code=resp.status_code, payload=payload if isinstance(payload, dict) else {})
        if isinstance(payload, dict):
            return payload
        return {"data": payload}

    async def get(self, path: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.request("GET", path, **kwargs)

    async def create_pedido_venda(self, body: Dict[str, Any], *, allow_write: bool = False) -> Dict[str, Any]:
        return await self.request("POST", "/pedidos/vendas", json_body=body, allow_write=allow_write)

    async def create_nfe(self, body: Dict[str, Any], *, allow_write: bool = False, allow_nfe: bool = False) -> Dict[str, Any]:
        return await self.request(
            "POST", "/nfe", json_body=body, allow_write=allow_write, allow_nfe=allow_nfe
        )

    async def get_empresa(self) -> Dict[str, Any]:
        """GET leve para validar token (não marca 'conectado' sozinho na UI)."""
        return await self.get("/empresas/meus-dados")

    async def get_nfe(self, nfe_id: str | int) -> Dict[str, Any]:
        """GET /nfe/{id} — chave de acesso / XML após SEFAZ (Etapa 3 webhook)."""
        return await self.get(f"/nfe/{nfe_id}")
