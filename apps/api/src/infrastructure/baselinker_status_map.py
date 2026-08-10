"""Mapeia filas BaseLinker → pedidos locais (SQLite) via getOrders READ-ONLY.

Nunca chama setOrderStatus / addOrderStatus / qualquer escrita no BaseLinker.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import delete, select

from src.infrastructure.baselinker_client import baselinker_client
from src.infrastructure.database import (
    RealOrderDB,
    RealOrderStatusDB,
    SyncMetaDB,
    async_session,
    init_db,
)
from src.infrastructure.order_pickup import (
    is_personal_status_id,
    is_personal_status_name,
)

META_KEY = "baselinker_status_map"
DEFAULT_STATUS_NAME = "Novos pedidos"
# ~3 req/s; BaseLinker limita 100 pedidos/página · 100 req/min
PAGE_SLEEP_SEC = 0.35
MAX_PAGES_FULL = 250
MAX_PAGES_DELTA = 20
# Janela delta padrão quando não há cursor (polling quase real)
DELTA_LOOKBACK_SEC = 48 * 3600


def _status_name_by_id(statuses: List[RealOrderStatusDB]) -> Dict[int, str]:
    return {int(s.id): s.name for s in statuses}


async def dedupe_status_names() -> int:
    """Remove duplicatas de nome em RealOrderStatusDB (mantém menor id)."""
    await init_db()
    removed = 0
    async with async_session() as session:
        rows = (await session.execute(select(RealOrderStatusDB).order_by(RealOrderStatusDB.id))).scalars().all()
        seen: Dict[str, int] = {}
        drop_ids: List[int] = []
        for r in rows:
            key = (r.name or "").strip().lower()
            if not key:
                continue
            if key in seen:
                drop_ids.append(int(r.id))
            else:
                seen[key] = int(r.id)
        for did in drop_ids:
            await session.execute(delete(RealOrderStatusDB).where(RealOrderStatusDB.id == did))
            removed += 1
        if removed:
            await session.commit()
    return removed


async def get_baselinker_status_map_meta() -> Dict[str, Any]:
    """Lê SyncMetaDB do último mapa BL (sem rede)."""
    await init_db()
    async with async_session() as session:
        row = await session.get(SyncMetaDB, META_KEY)
        if not row or not (row.value or "").strip():
            return {"ok": True, "synced_at": None, "has_meta": False}
        try:
            payload = json.loads(row.value)
        except (TypeError, ValueError, json.JSONDecodeError):
            payload = {"raw": (row.value or "")[:200]}
        if not isinstance(payload, dict):
            payload = {}
        return {
            "ok": True,
            "has_meta": True,
            "updated_at": row.updated_at.isoformat(timespec="seconds") if row.updated_at else None,
            **payload,
        }


async def _fetch_bl_orders_paginated(
    *,
    mode: str = "full",
    date_confirmed_from: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """getOrders com paginação date_confirmed_from (+1s). Só leitura."""
    all_orders: List[Dict[str, Any]] = []
    seen_ids: set = set()
    mode_l = (mode or "full").strip().lower()
    if mode_l not in ("full", "delta"):
        mode_l = "full"

    if date_confirmed_from is None:
        if mode_l == "delta":
            date_confirmed_from = int(time.time()) - DELTA_LOOKBACK_SEC
        else:
            # ~3 anos atrás para cobrir o cache ML sem varrer desde 1970
            date_confirmed_from = int(time.time()) - (3 * 365 * 24 * 3600)

    max_pages = MAX_PAGES_DELTA if mode_l == "delta" else MAX_PAGES_FULL
    pages = 0
    meta: Dict[str, Any] = {
        "pages": 0,
        "bl_orders_fetched": 0,
        "method": "getOrders",
        "write": False,
        "mode": mode_l,
        "date_confirmed_from": date_confirmed_from,
    }

    if not (baselinker_client.token or "").strip():
        return [], {"ok": False, "error": "BASELINKER_API_TOKEN ausente no .env", **meta}

    while pages < max_pages:
        params: Dict[str, Any] = {
            "get_unconfirmed_orders": False,
            "date_confirmed_from": date_confirmed_from,
        }

        try:
            raw = await baselinker_client.get_orders_page(params)
        except Exception as exc:
            meta["ok"] = False
            meta["error"] = f"Falha getOrders: {exc}"
            meta["pages"] = pages
            return all_orders, meta

        if not isinstance(raw, dict):
            meta["ok"] = False
            meta["error"] = "Resposta inválida getOrders"
            return all_orders, meta

        st = str(raw.get("status") or "").upper()
        if st and st not in ("SUCCESS", "OK"):
            meta["ok"] = False
            meta["error"] = raw.get("error_message") or raw.get("error") or f"status={st}"
            meta["pages"] = pages
            return all_orders, meta

        batch = raw.get("orders") or []
        if not isinstance(batch, list):
            batch = []
        pages += 1
        print(
            f"[bl-map] mode={mode_l} page={pages} batch={len(batch)} total={len(all_orders)}",
            flush=True,
        )

        if not batch:
            break

        max_confirmed = None
        new_in_page = 0
        for o in batch:
            if not isinstance(o, dict):
                continue
            oid = o.get("order_id")
            try:
                oid_i = int(oid)
            except (TypeError, ValueError):
                continue
            if oid_i in seen_ids:
                continue
            seen_ids.add(oid_i)
            all_orders.append(o)
            new_in_page += 1
            conf = o.get("date_confirmed") or o.get("date_add")
            try:
                conf_i = int(conf)
                if max_confirmed is None or conf_i > max_confirmed:
                    max_confirmed = conf_i
            except (TypeError, ValueError):
                pass

        if len(batch) < 100 or max_confirmed is None or new_in_page == 0:
            break
        # Docs BL: próximo pacote = date_confirmed do último + 1 segundo
        date_confirmed_from = max_confirmed + 1
        await asyncio.sleep(PAGE_SLEEP_SEC)

    meta["ok"] = True
    meta["pages"] = pages
    meta["bl_orders_fetched"] = len(all_orders)
    meta["date_confirmed_to"] = date_confirmed_from
    return all_orders, meta


def _build_lookup_keys(order: Dict[str, Any]) -> List[str]:
    keys: List[str] = []
    for field in (
        "shop_order_id",
        "external_order_id",
        "order_id",
        "transaction_id",
        "invoice_number",
    ):
        v = order.get(field)
        if v is None or v == "" or v == 0:
            continue
        keys.append(str(v).strip())
    # ML costuma aparecer em shop_order_id / external
    return keys


async def sync_baselinker_status_map_readonly(
    mode: str = "full",
    lookback_hours: Optional[float] = None,
) -> Dict[str, Any]:
    """Lê getOrders e atualiza status_id/status_name só no SQLite local.

    mode=full  → varredura longa (histórico)
    mode=delta → janela recente (polling quase real; respeita rate limit)
    """
    await init_db()
    mode_l = (mode or "full").strip().lower()
    if mode_l not in ("full", "delta"):
        mode_l = "full"

    removed_dupes = 0
    if mode_l == "full":
        removed_dupes = await dedupe_status_names()

    date_from: Optional[int] = None
    if mode_l == "delta":
        # Cursor: última sync bem-sucedida − 2h de overlap; senão lookback
        hours = float(lookback_hours) if lookback_hours and lookback_hours > 0 else (DELTA_LOOKBACK_SEC / 3600)
        date_from = int(time.time()) - int(hours * 3600)
        async with async_session() as session:
            prev = await session.get(SyncMetaDB, META_KEY)
            if prev and prev.value:
                try:
                    prev_meta = json.loads(prev.value)
                    cursor = prev_meta.get("delta_cursor") or prev_meta.get("date_confirmed_to")
                    if cursor is not None:
                        # overlap 2h para não perder mudanças de status
                        date_from = max(int(cursor) - 7200, int(time.time()) - int(hours * 3600))
                except (TypeError, ValueError, json.JSONDecodeError):
                    pass

    bl_orders, fetch_meta = await _fetch_bl_orders_paginated(
        mode=mode_l,
        date_confirmed_from=date_from,
    )
    if fetch_meta.get("ok") is False and not bl_orders:
        return {
            "ok": False,
            "error": fetch_meta.get("error") or "Falha ao ler pedidos BaseLinker",
            "remapped": 0,
            "write": False,
            "baselinker_write": False,
            **fetch_meta,
            "deduped_statuses": removed_dupes,
        }

    async with async_session() as session:
        statuses = (await session.execute(select(RealOrderStatusDB))).scalars().all()
        if not statuses:
            return {
                "ok": False,
                "error": "Nenhum status local. Importe status BaseLinker primeiro.",
                "remapped": 0,
                "write": False,
                "baselinker_write": False,
            }

        name_by_id = _status_name_by_id(statuses)
        # default = Novos pedidos se existir
        default_id = None
        default_name = DEFAULT_STATUS_NAME
        for s in statuses:
            if (s.name or "").strip().lower() == DEFAULT_STATUS_NAME.lower():
                default_id = int(s.id)
                default_name = s.name
                break
        if default_id is None:
            default_id = int(statuses[0].id)
            default_name = statuses[0].name

        local_orders = (await session.execute(select(RealOrderDB))).scalars().all()
        # índice: chave → pedido local
        index: Dict[str, RealOrderDB] = {}
        for o in local_orders:
            for k in (o.id, o.external_id):
                if k is None or str(k).strip() == "":
                    continue
                index[str(k).strip()] = o
                sk = str(k).strip()
                if sk.startswith("ML-"):
                    index[sk[3:]] = o

        remapped = 0
        matched_bl = 0
        by_status: Counter = Counter()

        for bl in bl_orders:
            sid = bl.get("order_status_id")
            try:
                sid_i = int(sid)
            except (TypeError, ValueError):
                continue
            sname = name_by_id.get(sid_i)
            if not sname:
                continue  # status não importado localmente

            keys = _build_lookup_keys(bl)
            local: Optional[RealOrderDB] = None
            for k in keys:
                local = index.get(k)
                if local:
                    break
            if not local:
                continue

            matched_bl += 1
            # Pickup / fila pessoal: não sobrescrever com status BL (sync é leitura)
            if (getattr(local, "picked_by", None) or "").strip():
                by_status[(local.status_name or "").strip() or "—"] += 1
                continue
            if is_personal_status_id(local.status_id) or is_personal_status_name(local.status_name):
                by_status[(local.status_name or "").strip() or "—"] += 1
                continue
            if int(local.status_id or 0) != sid_i or (local.status_name or "") != sname:
                local.status_id = sid_i
                local.status_name = sname
                remapped += 1
            by_status[sname] += 1

        # Recalcular counts nas filas
        all_local = (await session.execute(select(RealOrderDB))).scalars().all()
        counts: Dict[int, int] = {}
        for o in all_local:
            counts[int(o.status_id or 0)] = counts.get(int(o.status_id or 0), 0) + 1
        for s in statuses:
            s.count = counts.get(int(s.id), 0)

        now = datetime.now()
        dist = dict(by_status.most_common(15))
        # Distribuição local completa (amostra top) — útil pós-full ou delta
        local_dist: Counter = Counter()
        for o in all_local:
            local_dist[(o.status_name or "").strip() or "—"] += 1
        meta = {
            "source": "baselinker_getOrders_status_map",
            "write": False,
            "baselinker_write": False,
            "mode": mode_l,
            "remapped": remapped,
            "matched_bl": matched_bl,
            "bl_orders_fetched": len(bl_orders),
            "local_orders": len(local_orders),
            "deduped_statuses": removed_dupes,
            "distribution_sample": dist,
            "local_distribution_top": dict(local_dist.most_common(12)),
            "default_status": default_name,
            "synced_at": now.isoformat(timespec="seconds"),
            "delta_cursor": fetch_meta.get("date_confirmed_to") or int(time.time()),
            **{k: fetch_meta.get(k) for k in ("pages", "method", "date_confirmed_from", "date_confirmed_to")},
        }
        await session.merge(
            SyncMetaDB(key=META_KEY, value=json.dumps(meta, ensure_ascii=False), updated_at=now)
        )
        await session.commit()

    return {
        "ok": True,
        "mode": mode_l,
        "remapped": remapped,
        "matched_bl": matched_bl,
        "bl_orders_fetched": len(bl_orders),
        "local_orders": len(local_orders),
        "deduped_statuses": removed_dupes,
        "distribution_sample": dist,
        "local_distribution_top": dict(local_dist.most_common(12)),
        "pages": fetch_meta.get("pages"),
        "unmapped_stay_default": True,
        "default_status": default_name,
        "synced_at": now.isoformat(timespec="seconds"),
        "write": False,
        "baselinker_write": False,
        "message": (
            f"{remapped} pedidos locais atualizados com filas BaseLinker (somente leitura, mode={mode_l}). "
            f"{matched_bl} matches; pedidos só no ML permanecem em '{default_name}'."
        ),
    }

