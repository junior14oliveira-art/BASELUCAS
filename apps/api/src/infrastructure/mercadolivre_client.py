"""Cliente da API do Mercado Livre (api.mercadolibre.com).

Cobre OAuth2 (authorization_code + refresh_token), gestão de anúncios,
pedidos, envios, perguntas, categorias e métricas.

As credenciais vêm de src.config.settings (ML_CLIENT_ID / ML_CLIENT_SECRET),
preenchidas via .env quando o app for criado no DevCenter do Mercado Livre.
"""

import asyncio
import base64
import hashlib
import secrets
import time
from typing import Any, Callable, Dict, List, Optional, Awaitable
from urllib.parse import urlencode

import httpx

from src.config import settings

ML_API_URL = "https://api.mercadolibre.com"

# O domínio de autorização muda por país. MLB = Brasil.
ML_AUTH_DOMAINS = {
    "MLB": "https://auth.mercadolivre.com.br",
    "MLA": "https://auth.mercadolibre.com.ar",
    "MLM": "https://auth.mercadolibre.com.mx",
    "MLC": "https://auth.mercadolibre.cl",
    "MCO": "https://auth.mercadolibre.com.co",
    "MLU": "https://auth.mercadolibre.com.uy",
    "MPE": "https://auth.mercadolibre.com.pe",
}


class MercadoLivreError(Exception):
    """Erro genérico da API do Mercado Livre."""

    def __init__(self, message: str, status_code: int = 0, payload: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


class MercadoLivreAuthError(MercadoLivreError):
    """Falha de autenticação/autorização (token inválido, expirado ou sem escopo)."""


class MercadoLivreReadOnlyError(MercadoLivreError):
    """Operação bloqueada porque a integração está em modo somente leitura."""

    def __init__(self, message_or_method: str, path: str = "", **kwargs: Any):
        if path:
            message = (
                f"ML_READ_ONLY=true — bloqueado {message_or_method} {path}. "
                "Defina ML_READ_ONLY=false apenas após homologação explícita."
            )
            payload = {"method": message_or_method, "path": path, "gated": True}
        else:
            message = message_or_method
            payload = kwargs.get("payload") or {"gated": True}
        super().__init__(message, status_code=int(kwargs.get("status_code") or 403), payload=payload)


class _RateLimiter:
    """Limitador simples de chamadas concorrentes + intervalo mínimo entre requisições.

    O Mercado Livre não publica um número fixo de req/s; responde 429 quando
    o app excede a cota. Mantemos uma folga conservadora e o retry com backoff
    do _request cobre os 429 restantes.
    """

    def __init__(self, max_concurrent: int = 8, min_interval: float = 0.05):
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


def generate_pkce_pair() -> Dict[str, str]:
    """Gera o par code_verifier / code_challenge (S256) para o fluxo PKCE."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return {"code_verifier": verifier, "code_challenge": challenge}


class MercadoLivreClient:
    """Cliente autenticado por conta de vendedor.

    Cada vendedor conectado tem seu próprio access_token/refresh_token. Passe
    ``on_token_refresh`` para persistir os tokens renovados no banco — o
    refresh_token do Mercado Livre é de uso único, então gravar o novo valor
    é obrigatório, sob pena de perder o acesso à conta.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        user_id: Optional[int] = None,
        expires_at: Optional[float] = None,
        on_token_refresh: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.user_id = user_id
        self.expires_at = expires_at or 0.0
        self.on_token_refresh = on_token_refresh
        self._refresh_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # OAuth2
    # ------------------------------------------------------------------

    @staticmethod
    def build_authorization_url(
        state: str,
        code_challenge: Optional[str] = None,
        site_id: Optional[str] = None,
        redirect_uri: Optional[str] = None,
    ) -> str:
        """Monta a URL para onde o vendedor é redirecionado para autorizar o app."""
        site = site_id or settings.ML_SITE_ID
        domain = ML_AUTH_DOMAINS.get(site, ML_AUTH_DOMAINS["MLB"])
        params = {
            "response_type": "code",
            "client_id": settings.ML_CLIENT_ID,
            "redirect_uri": redirect_uri or settings.ML_REDIRECT_URI,
            "state": state,
        }
        if code_challenge:
            params["code_challenge"] = code_challenge
            params["code_challenge_method"] = "S256"
        return f"{domain}/authorization?{urlencode(params)}"

    @staticmethod
    async def _token_request(data: Dict[str, str]) -> Dict[str, Any]:
        headers = {
            "accept": "application/json",
            "content-type": "application/x-www-form-urlencoded",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{ML_API_URL}/oauth/token", data=data, headers=headers)

        try:
            payload = resp.json()
        except ValueError:
            payload = {"raw": resp.text}

        if resp.status_code >= 400:
            raise MercadoLivreAuthError(
                payload.get("message") or payload.get("error") or "Falha ao obter token do Mercado Livre",
                status_code=resp.status_code,
                payload=payload,
            )
        return payload

    @classmethod
    async def exchange_code(cls, code: str, code_verifier: Optional[str] = None,
                            redirect_uri: Optional[str] = None) -> Dict[str, Any]:
        """Troca o ``code`` recebido no callback por access_token + refresh_token."""
        data = {
            "grant_type": "authorization_code",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "code": code,
            "redirect_uri": redirect_uri or settings.ML_REDIRECT_URI,
        }
        if code_verifier:
            data["code_verifier"] = code_verifier
        return await cls._token_request(data)

    async def refresh_access_token(self) -> Dict[str, Any]:
        """Renova o access_token. O refresh_token retornado substitui o anterior."""
        if not self.refresh_token:
            raise MercadoLivreAuthError("Conta sem refresh_token — é necessário reconectar via OAuth.")

        payload = await self._token_request({
            "grant_type": "refresh_token",
            "client_id": settings.ML_CLIENT_ID,
            "client_secret": settings.ML_CLIENT_SECRET,
            "refresh_token": self.refresh_token,
        })

        self.access_token = payload.get("access_token")
        self.refresh_token = payload.get("refresh_token", self.refresh_token)
        self.user_id = payload.get("user_id", self.user_id)
        self.expires_at = time.time() + int(payload.get("expires_in", 21600))

        if self.on_token_refresh:
            await self.on_token_refresh({
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "user_id": self.user_id,
                "expires_at": self.expires_at,
            })
        return payload

    def is_token_expired(self, skew_seconds: int = 300) -> bool:
        """True se o token expirou (ou expira nos próximos ``skew_seconds``)."""
        if not self.expires_at:
            return False
        return time.time() >= (self.expires_at - skew_seconds)

    # ------------------------------------------------------------------
    # Transporte
    # ------------------------------------------------------------------

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
        authed: bool = True,
        max_retries: int = 3,
        raw: bool = False,
    ) -> Any:
        """Executa a chamada HTTP com refresh automático, retry e backoff."""
        if authed and self.is_token_expired():
            async with self._refresh_lock:
                if self.is_token_expired():
                    await self.refresh_access_token()

        url = path if path.startswith("http") else f"{ML_API_URL}{path}"
        attempt = 0
        refreshed = False

        while True:
            headers = {"accept": "application/json"}
            if authed and self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"

            async with _rate_limiter:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.request(
                        method, url, params=params, json=json_body, headers=headers
                    )

            # 401: tenta um refresh e repete uma única vez.
            if resp.status_code == 401 and authed and not refreshed and self.refresh_token:
                refreshed = True
                async with self._refresh_lock:
                    await self.refresh_access_token()
                continue

            # 429 / 5xx: backoff exponencial.
            if resp.status_code == 429 or resp.status_code >= 500:
                if attempt < max_retries:
                    retry_after = resp.headers.get("Retry-After")
                    delay = float(retry_after) if retry_after else min(2 ** attempt, 8)
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue

            if raw:
                if resp.status_code >= 400:
                    raise MercadoLivreError(
                        f"Erro {resp.status_code} em {method} {path}",
                        status_code=resp.status_code,
                    )
                return resp.content

            try:
                payload = resp.json()
            except ValueError:
                payload = {"raw": resp.text}

            if resp.status_code == 401:
                raise MercadoLivreAuthError(
                    payload.get("message", "Token inválido ou expirado"),
                    status_code=401,
                    payload=payload,
                )
            if resp.status_code >= 400:
                raise MercadoLivreError(
                    payload.get("message") or f"Erro {resp.status_code} em {method} {path}",
                    status_code=resp.status_code,
                    payload=payload,
                )
            return payload

    # ------------------------------------------------------------------
    # Usuários e conta
    # ------------------------------------------------------------------

    async def get_me(self) -> Dict[str, Any]:
        """Dados da conta autenticada (nickname, site_id, reputação, e-mail)."""
        return await self._request("GET", "/users/me")

    async def get_user(self, user_id: int) -> Dict[str, Any]:
        return await self._request("GET", f"/users/{user_id}")

    async def get_available_listing_types(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Tipos de anúncio disponíveis para o vendedor (clássico, premium, grátis)."""
        uid = user_id or self.user_id
        return await self._request("GET", f"/users/{uid}/available_listing_types")

    # ------------------------------------------------------------------
    # Categorias e atributos (De-Para)
    # ------------------------------------------------------------------

    async def get_site_categories(self, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Categorias raiz do site (MLB para Brasil)."""
        site = site_id or settings.ML_SITE_ID
        return await self._request("GET", f"/sites/{site}/categories", authed=False)

    async def get_category(self, category_id: str) -> Dict[str, Any]:
        """Detalhe da categoria, incluindo caminho completo e configurações de venda."""
        return await self._request("GET", f"/categories/{category_id}", authed=False)

    async def get_category_attributes(self, category_id: str) -> List[Dict[str, Any]]:
        """Atributos da categoria — usado para validar campos obrigatórios do anúncio."""
        return await self._request("GET", f"/categories/{category_id}/attributes", authed=False)

    async def predict_category(self, title: str, site_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Sugere categoria e domínio a partir do título do produto."""
        site = site_id or settings.ML_SITE_ID
        return await self._request(
            "GET", f"/sites/{site}/domain_discovery/search",
            params={"q": title}, authed=False,
        )

    # ------------------------------------------------------------------
    # Anúncios
    # ------------------------------------------------------------------

    async def search_user_items(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Busca paginada de anúncios do vendedor (limite de 1000 via offset)."""
        uid = user_id or self.user_id
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self._request("GET", f"/users/{uid}/items/search", params=params)

    async def scan_user_items(
        self,
        user_id: Optional[int] = None,
        status: Optional[str] = None,
        scroll_id: Optional[str] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Modo scan — obrigatório para contas com mais de 1000 anúncios.

        Repita passando o ``scroll_id`` retornado até ``results`` vir vazio.
        """
        uid = user_id or self.user_id
        params: Dict[str, Any] = {"search_type": "scan", "limit": limit}
        if status:
            params["status"] = status
        if scroll_id:
            params["scroll_id"] = scroll_id
        return await self._request("GET", f"/users/{uid}/items/search", params=params)

    async def get_item(self, item_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/items/{item_id}")

    async def get_items_batch(self, item_ids: List[str], attributes: Optional[str] = None) -> List[Dict[str, Any]]:
        """Multiget de anúncios — a API aceita no máximo 20 IDs por chamada."""
        results: List[Dict[str, Any]] = []
        for i in range(0, len(item_ids), 20):
            chunk = item_ids[i:i + 20]
            params: Dict[str, Any] = {"ids": ",".join(chunk)}
            if attributes:
                params["attributes"] = attributes
            payload = await self._request("GET", "/items", params=params)
            if isinstance(payload, list):
                results.extend(payload)
        return results

    async def create_item(self, item_data: Dict[str, Any]) -> Dict[str, Any]:
        """Publica um novo anúncio."""
        return await self._request("POST", "/items", json_body=item_data)

    async def update_item(self, item_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """Atualiza campos do anúncio (price, available_quantity, status, pictures...)."""
        return await self._request("PUT", f"/items/{item_id}", json_body=fields)

    async def update_item_price(self, item_id: str, price: float) -> Dict[str, Any]:
        return await self.update_item(item_id, {"price": price})

    async def update_item_stock(self, item_id: str, quantity: int) -> Dict[str, Any]:
        return await self.update_item(item_id, {"available_quantity": quantity})

    async def pause_item(self, item_id: str) -> Dict[str, Any]:
        return await self.update_item(item_id, {"status": "paused"})

    async def activate_item(self, item_id: str) -> Dict[str, Any]:
        return await self.update_item(item_id, {"status": "active"})

    async def close_item(self, item_id: str) -> Dict[str, Any]:
        """Finaliza o anúncio. Estado terminal — não é possível reativar."""
        return await self.update_item(item_id, {"status": "closed"})

    async def get_item_description(self, item_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/items/{item_id}/description")

    async def update_item_description(self, item_id: str, plain_text: str) -> Dict[str, Any]:
        return await self._request(
            "PUT", f"/items/{item_id}/description", json_body={"plain_text": plain_text}
        )

    # ------------------------------------------------------------------
    # Pedidos
    # ------------------------------------------------------------------

    async def search_orders(
        self,
        seller_id: Optional[int] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort: str = "date_desc",
    ) -> Dict[str, Any]:
        """Busca pedidos do vendedor. Datas em ISO-8601 (ex.: 2026-08-01T00:00:00.000-03:00)."""
        sid = seller_id or self.user_id
        params: Dict[str, Any] = {"seller": sid, "limit": limit, "offset": offset, "sort": sort}
        if status:
            params["order.status"] = status
        if date_from:
            params["order.date_created.from"] = date_from
        if date_to:
            params["order.date_created.to"] = date_to
        return await self._request("GET", "/orders/search", params=params)

    async def get_order(self, order_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/orders/{order_id}")

    # ------------------------------------------------------------------
    # Envios
    # ------------------------------------------------------------------

    async def get_shipment(self, shipment_id: str) -> Dict[str, Any]:
        return await self._request("GET", f"/shipments/{shipment_id}")

    async def get_shipment_labels(self, shipment_ids: List[str], response_type: str = "pdf") -> bytes:
        """Baixa etiquetas de envio. ``response_type``: ``pdf`` ou ``zpl2`` (impressão térmica).

        Endpoint oficial ME2: ``GET /shipment_labels``.
        """
        return await self._request(
            "GET", "/shipment_labels",
            params={"shipment_ids": ",".join(shipment_ids), "response_type": response_type},
            raw=True,
        )

    async def inject_nfe_billing_info(
        self,
        order_id: str,
        access_key: str,
        *,
        allow_write: bool = False,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Injeta a Chave de Acesso da NF-e no billing_info do pedido ML.

        Write gated por ``ML_READ_ONLY`` (default true). Em produção homologada:
        ``ML_READ_ONLY=false`` e ``allow_write=True``.

        Stub documentado: com gate ativo levanta ``MercadoLivreReadOnlyError`` —
        o pipeline local ainda grava a chave e pode engatilhar ZPL assim que o
        GET de etiqueta for possível.
        """
        if settings.ML_READ_ONLY and not allow_write:
            raise MercadoLivreReadOnlyError("POST", f"/orders/{order_id}/billing_info")

        key = (access_key or "").strip()
        body: Dict[str, Any] = {
            # Formato pragmático para integradores BR (chave 44 dígitos).
            "nfe": {"key": key},
            "invoice_key": key,
            "doc_type": "NFE",
            "doc_number": key,
        }
        if extra:
            body.update(extra)
        return await self._request("POST", f"/orders/{order_id}/billing_info", json_body=body)

    async def get_fulfillment_stock(self, user_id: Optional[int] = None) -> Dict[str, Any]:
        """Estoque armazenado no Full (fulfillment do Mercado Livre)."""
        uid = user_id or self.user_id
        return await self._request("GET", f"/users/{uid}/stock/fulfillment")

    # ------------------------------------------------------------------
    # Perguntas
    # ------------------------------------------------------------------

    async def search_questions(
        self,
        seller_id: Optional[int] = None,
        status: str = "UNANSWERED",
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Perguntas recebidas nos anúncios do vendedor."""
        sid = seller_id or self.user_id
        return await self._request("GET", "/questions/search", params={
            "seller_id": sid,
            "status": status,
            "api_version": 4,
            "limit": limit,
            "offset": offset,
        })

    async def answer_question(self, question_id: int, text: str) -> Dict[str, Any]:
        return await self._request(
            "POST", "/answers", json_body={"question_id": question_id, "text": text}
        )

    # ------------------------------------------------------------------
    # Métricas e taxas
    # ------------------------------------------------------------------

    async def get_item_visits(self, item_id: str, last: int = 30, unit: str = "day") -> Dict[str, Any]:
        """Série temporal de visitas do anúncio."""
        return await self._request(
            "GET", f"/items/{item_id}/visits/time_window",
            params={"last": last, "unit": unit},
        )

    async def get_listing_fees(
        self,
        price: float,
        category_id: Optional[str] = None,
        listing_type_id: str = "gold_special",
        site_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simula a comissão do Mercado Livre para um preço/categoria."""
        site = site_id or settings.ML_SITE_ID
        params: Dict[str, Any] = {"price": price, "listing_type_id": listing_type_id}
        if category_id:
            params["category_id"] = category_id
        return await self._request("GET", f"/sites/{site}/listing_prices", params=params, authed=False)

    async def get_item_promotions(self, item_id: str) -> Dict[str, Any]:
        """Promoções e campanhas disponíveis para o anúncio."""
        return await self._request(
            "GET", f"/seller-promotions/items/{item_id}", params={"app_version": "v2"}
        )

    # ------------------------------------------------------------------
    # Webhooks
    # ------------------------------------------------------------------

    async def fetch_resource(self, resource_path: str) -> Dict[str, Any]:
        """Busca o recurso apontado por uma notificação de webhook.

        As notificações trazem apenas ``resource`` (ex.: ``/orders/123``); o
        conteúdo precisa ser buscado à parte.
        """
        return await self._request("GET", resource_path)


def is_configured() -> bool:
    """True quando as credenciais do app do Mercado Livre já foram preenchidas."""
    return bool(settings.ML_CLIENT_ID and settings.ML_CLIENT_SECRET)
