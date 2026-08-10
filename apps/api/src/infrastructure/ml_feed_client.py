"""Cliente HTTP read-only do feed Mercado Livre (bridge Base Antigravity)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional
from urllib.parse import urljoin

import httpx

from src.config import settings

# Bridge 4MC / ML: orders rejeita limit > 51 (400 limit.maximum_exceeded).
ORDERS_MAX_LIMIT = 50


class MLFeedClientError(RuntimeError):
    pass


class MLFeedClient:
    def __init__(self, base_url: Optional[str] = None, timeout: float = 60.0):
        raw = (base_url or settings.ML_FEED_BASE_URL or "").rstrip("/") + "/"
        self.base_url = raw
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    async def _sleep_backoff(self, attempt: int, retry_after: Optional[str] = None) -> None:
        if retry_after:
            try:
                wait = min(max(float(retry_after), 0.5), 60.0)
            except (TypeError, ValueError):
                wait = min(1.5 * (2**attempt), 30.0)
        else:
            wait = min(1.5 * (2**attempt), 30.0)
        await asyncio.sleep(wait)

    async def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = self._url(path)
        last_exc: Optional[Exception] = None
        for attempt in range(5):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.get(url, params=params or {})
                    if res.status_code == 429 and attempt < 4:
                        await self._sleep_backoff(attempt, res.headers.get("Retry-After"))
                        continue
                    # Bridge às vezes devolve 500 transitório — tenta de novo
                    if res.status_code >= 500 and attempt < 4:
                        last_exc = httpx.HTTPStatusError(
                            f"HTTP {res.status_code}",
                            request=res.request,
                            response=res,
                        )
                        await self._sleep_backoff(attempt)
                        continue
                    res.raise_for_status()
                    data = res.json()
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < 4:
                    await self._sleep_backoff(attempt)
                    continue
                raise MLFeedClientError(f"Falha ao consultar feed ML ({url}): {exc}") from exc
            if not isinstance(data, dict):
                raise MLFeedClientError(f"Resposta inesperada do feed ML ({url})")
            return data
        raise MLFeedClientError(f"Falha ao consultar feed ML ({url}): {last_exc}")

    async def get_feed(self) -> Dict[str, Any]:
        """Resumo + amostras (orders/questions/item_ids)."""
        if settings.ML_FEED_URL:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.get(settings.ML_FEED_URL)
                    if res.status_code == 429:
                        await self._sleep_backoff(0, res.headers.get("Retry-After"))
                        res = await client.get(settings.ML_FEED_URL)
                    res.raise_for_status()
                    data = res.json()
            except httpx.HTTPError as exc:
                raise MLFeedClientError(f"Falha ao consultar ML_FEED_URL: {exc}") from exc
            if not isinstance(data, dict):
                raise MLFeedClientError("ML_FEED_URL não retornou JSON objeto")
            return data
        return await self._get("feed")

    async def get_orders(self, offset: int = 0, limit: int = ORDERS_MAX_LIMIT) -> Dict[str, Any]:
        """Lista paginada de pedidos (todos os status). Bridge 4MC: limit máx. 50."""
        limit = max(1, min(int(limit or ORDERS_MAX_LIMIT), ORDERS_MAX_LIMIT))
        offset = max(0, int(offset or 0))
        if settings.ML_FEED_ORDERS_URL:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.get(
                        settings.ML_FEED_ORDERS_URL,
                        params={"offset": offset, "limit": limit},
                    )
                    if res.status_code == 429:
                        await self._sleep_backoff(0, res.headers.get("Retry-After"))
                        res = await client.get(
                            settings.ML_FEED_ORDERS_URL,
                            params={"offset": offset, "limit": limit},
                        )
                    res.raise_for_status()
                    data = res.json()
            except httpx.HTTPError as exc:
                raise MLFeedClientError(f"Falha ao consultar ML_FEED_ORDERS_URL: {exc}") from exc
            if isinstance(data, list):
                # Alguns proxies devolvem array cru — normaliza para o shape esperado
                return {
                    "success": True,
                    "orders": data,
                    "paging": {"total": len(data), "offset": offset, "limit": limit},
                }
            if not isinstance(data, dict):
                raise MLFeedClientError("ML_FEED_ORDERS_URL não retornou JSON objeto")
            return data
        return await self._get("orders", params={"offset": offset, "limit": limit})

    async def get_order(self, order_id: str | int) -> Dict[str, Any]:
        """Detalhe de um pedido (buyer/billing/payments/shipping.id)."""
        return await self._get(f"order/{order_id}")

    async def get_shipment(self, shipment_id: str | int) -> Dict[str, Any]:
        """Detalhe de envio (endereço, status, tracking)."""
        return await self._get(f"shipment/{shipment_id}")

    async def get_item(self, item_id: str) -> Dict[str, Any]:
        """Detalhe de anúncio (atributos/EAN, variações, descrição)."""
        return await self._get(f"item/{item_id}")

    async def get_items(
        self,
        offset: int = 0,
        limit: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Lista anúncios do bridge. status: active|paused|closed|… (omitir = default do bridge)."""
        params: Dict[str, Any] = {"offset": offset, "limit": limit}
        if status:
            params["status"] = status
        return await self._get("items", params=params)

    async def get_questions(self) -> Dict[str, Any]:
        return await self._get("questions")

    async def get_claims(self) -> Dict[str, Any]:
        return await self._get("claims")

    async def get_messages(self, order_id: str | int) -> Dict[str, Any]:
        return await self._get(f"messages/{order_id}")

    async def ping_token_endpoint(self) -> Dict[str, Any]:
        """Consulta metadados do endpoint /token (sem persistir o access_token)."""
        url = settings.ML_FEED_TOKEN_URL or self._url("token")
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url)
                if res.status_code == 429:
                    await self._sleep_backoff(0, res.headers.get("Retry-After"))
                    res = await client.get(url)
                res.raise_for_status()
                data = res.json()
        except httpx.HTTPError as exc:
            raise MLFeedClientError(f"Falha ao consultar token endpoint: {exc}") from exc
        if not isinstance(data, dict):
            raise MLFeedClientError("Token endpoint não retornou JSON objeto")
        # Nunca devolver o segredo ao caller de sync/UI
        return {
            "success": bool(data.get("success")),
            "nickname": data.get("nickname"),
            "ml_user_id": data.get("ml_user_id"),
            "expires_at": data.get("expires_at"),
            "token_type": data.get("token_type"),
            "has_access_token": bool(data.get("access_token")),
        }


ml_feed_client = MLFeedClient()
