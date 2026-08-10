"""Importação READ-ONLY dos nomes de status do BaseLinker para o SQLite local.

Usa apenas getOrderStatusList. Nunca chama set/add/delete no BaseLinker.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import delete, func, select

from src.infrastructure.baselinker_client import baselinker_client
from src.infrastructure.database import (
    RealOrderDB,
    RealOrderStatusDB,
    SyncMetaDB,
    async_session,
    init_db,
)

META_KEY = "baselinker_statuses_imported"


def _normalize_color(raw: Any) -> str:
    if raw is None:
        return "#64748B"
    text = str(raw).strip()
    if not text:
        return "#64748B"
    if text.startswith("#"):
        return text[:50]
    # BaseLinker às vezes devolve int RGB
    try:
        n = int(text)
        return f"#{n:06x}"[:50]
    except (TypeError, ValueError):
        return "#64748B"


def _extract_statuses(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    statuses = payload.get("statuses") or payload.get("status_list") or []
    if not isinstance(statuses, list):
        return []
    out: List[Dict[str, Any]] = []
    for row in statuses:
        if not isinstance(row, dict):
            continue
        sid = row.get("id")
        name = (row.get("name") or row.get("name_for_customer") or "").strip()
        if sid is None or not name:
            continue
        try:
            sid_int = int(sid)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "id": sid_int,
                "name": name,
                "color": _normalize_color(row.get("color")),
            }
        )
    out.sort(key=lambda s: s["id"])
    return out


async def import_baselinker_statuses_readonly() -> Dict[str, Any]:
    """Lê getOrderStatusList e faz upsert em RealOrderStatusDB (só local)."""
    await init_db()

    if not (baselinker_client.token or "").strip():
        return {
            "ok": False,
            "error": "BASELINKER_API_TOKEN ausente no .env",
            "imported": 0,
            "statuses": [],
        }

    try:
        raw = await baselinker_client.get_order_status_list()
    except Exception as exc:  # rede / timeout — não apaga status locais
        return {
            "ok": False,
            "error": f"Falha de rede ao ler BaseLinker: {exc}",
            "imported": 0,
            "statuses": [],
            "bl_method": "getOrderStatusList",
            "write": False,
            "local_preserved": True,
        }
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "error": "Resposta inválida do BaseLinker",
            "imported": 0,
            "statuses": [],
            "local_preserved": True,
        }

    api_status = str(raw.get("status") or "").upper()
    if api_status and api_status not in ("SUCCESS", "OK"):
        return {
            "ok": False,
            "error": raw.get("error_message") or raw.get("error") or f"BaseLinker status={api_status}",
            "imported": 0,
            "statuses": [],
            "bl_method": "getOrderStatusList",
            "write": False,
        }

    statuses = _extract_statuses(raw)
    if not statuses:
        return {
            "ok": False,
            "error": "Nenhum status retornado por getOrderStatusList",
            "imported": 0,
            "statuses": [],
            "bl_method": "getOrderStatusList",
            "write": False,
        }

    async with async_session() as session:
        # Contagens locais por status_id / status_name
        orders = (await session.execute(select(RealOrderDB))).scalars().all()
        by_id: Dict[int, int] = {}
        by_name: Dict[str, int] = {}
        for o in orders:
            by_id[int(o.status_id or 0)] = by_id.get(int(o.status_id or 0), 0) + 1
            by_name[o.status_name or ""] = by_name.get(o.status_name or "", 0) + 1

        await session.execute(delete(RealOrderStatusDB))
        for s in statuses:
            count = by_id.get(s["id"], 0) or by_name.get(s["name"], 0)
            session.add(
                RealOrderStatusDB(
                    id=s["id"],
                    name=s["name"],
                    color=s["color"],
                    count=count,
                )
            )

        # Pedidos ainda com buckets ML (ids 1–7 / nomes canônicos) → 1º status BL
        default = statuses[0]
        ml_bucket_names = {
            "Pagos",
            "Confirmados",
            "Prontos para enviar",
            "Enviados",
            "Entregues",
            "Cancelados",
            "Outros",
        }
        bl_ids = {s["id"] for s in statuses}
        bl_names = {s["name"] for s in statuses}
        remapped = 0
        for o in orders:
            if o.status_id in bl_ids and (o.status_name or "") in bl_names:
                continue
            if (o.status_name or "") in ml_bucket_names or int(o.status_id or 0) in range(1, 8):
                o.status_id = default["id"]
                o.status_name = default["name"]
                remapped += 1

        # Recalcular counts após remap
        orders2 = (await session.execute(select(RealOrderDB))).scalars().all()
        counts: Dict[int, int] = {}
        for o in orders2:
            counts[int(o.status_id or 0)] = counts.get(int(o.status_id or 0), 0) + 1
        for s in statuses:
            row = await session.get(RealOrderStatusDB, s["id"])
            if row:
                row.count = counts.get(s["id"], 0)

        now = datetime.now()
        meta = {
            "source": "baselinker_getOrderStatusList",
            "imported": len(statuses),
            "remapped_orders": remapped,
            "synced_at": now.isoformat(timespec="seconds"),
            "write": False,
            "method": "getOrderStatusList",
        }
        await session.merge(
            SyncMetaDB(
                key=META_KEY,
                value=json.dumps(meta, ensure_ascii=False),
                updated_at=now,
            )
        )
        await session.commit()

    return {
        "ok": True,
        "imported": len(statuses),
        "remapped_orders": remapped,
        "statuses": [{"id": s["id"], "name": s["name"], "color": s["color"]} for s in statuses],
        "bl_method": "getOrderStatusList",
        "write": False,
        "message": f"{len(statuses)} status BaseLinker importados (somente leitura).",
    }


async def has_baselinker_statuses() -> bool:
    await init_db()
    async with async_session() as session:
        row = await session.get(SyncMetaDB, META_KEY)
        if row and (row.value or "").strip():
            return True
        n = (
            await session.execute(select(func.count()).select_from(RealOrderStatusDB))
        ).scalar_one()
        # Heurística: catálogo ML tem exatamente 7 ids 1..7
        if int(n or 0) > 7:
            return True
        rows = (await session.execute(select(RealOrderStatusDB))).scalars().all()
        ids = {r.id for r in rows}
        return bool(ids) and ids != {1, 2, 3, 4, 5, 6, 7}
