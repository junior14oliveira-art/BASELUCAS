"""Pickup local de pedidos: Pegar / Enviar / Liberar (SQLite only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select

from src.domain.operator_roles import normalize_role
from src.infrastructure.database import (
    OperatorDB,
    RealOrderDB,
    RealOrderStatusDB,
    async_session,
    init_db,
)
from src.domain.operator_roles import ROLE_ADMIN
from src.infrastructure.native_queues import (
    PERSONAL_STATUS_ID_BASE,
    default_send_queue_name,
    is_personal_status_id,
    is_personal_status_name,
    personal_queue_name,
    personal_status_id,
    pickable_queue_names,
    resolve_status_name_variants,
)

# Re-export para baselinker_status_map e outros
__all__ = [
    "is_personal_status_id",
    "is_personal_status_name",
    "pickup_order",
    "send_order_to_queue",
    "release_order",
]


async def _find_status_by_name(session, name: str) -> Optional[RealOrderStatusDB]:
    for candidate in resolve_status_name_variants(name):
        row = (
            await session.execute(
                select(RealOrderStatusDB).where(RealOrderStatusDB.name == candidate)
            )
        ).scalars().first()
        if row:
            return row
    # case-insensitive fallback
    all_st = (await session.execute(select(RealOrderStatusDB))).scalars().all()
    target = (name or "").strip().lower()
    for s in all_st:
        if (s.name or "").strip().lower() == target:
            return s
        for cand in resolve_status_name_variants(name):
            if (s.name or "").strip().lower() == cand.lower():
                return s
    return None


async def _ensure_personal_status(
    session, operator: OperatorDB
) -> RealOrderStatusDB:
    sid = personal_status_id(int(operator.id))
    sname = personal_queue_name(operator.name)
    existing = await session.get(RealOrderStatusDB, sid)
    if existing:
        if (existing.name or "") != sname:
            existing.name = sname
        return existing
    # Também procura por nome (legado)
    by_name = await _find_status_by_name(session, sname)
    if by_name:
        return by_name
    row = RealOrderStatusDB(id=sid, name=sname, color="#0066FF", count=0)
    session.add(row)
    await session.flush()
    return row


async def _recalc_status_counts(session) -> None:
    statuses = (await session.execute(select(RealOrderStatusDB))).scalars().all()
    orders = (await session.execute(select(RealOrderDB))).scalars().all()
    counts: Dict[int, int] = {}
    for o in orders:
        counts[int(o.status_id or 0)] = counts.get(int(o.status_id or 0), 0) + 1
    for s in statuses:
        s.count = counts.get(int(s.id), 0)


def _order_payload(order: RealOrderDB) -> Dict[str, Any]:
    return {
        "id": order.id,
        "status_id": order.status_id,
        "status_name": order.status_name,
        "picked_by": getattr(order, "picked_by", "") or "",
        "picked_by_id": getattr(order, "picked_by_id", 0) or 0,
        "picked_from_status_id": getattr(order, "picked_from_status_id", 0) or 0,
        "picked_from_status_name": getattr(order, "picked_from_status_name", "") or "",
    }


async def pickup_order(order_id: str, operator_id: int) -> Dict[str, Any]:
    """Puxa pedido da fila geral pickable → Fila · {nome} do operador."""
    await init_db()
    async with async_session() as session:
        operator = await session.get(OperatorDB, int(operator_id))
        if not operator or not operator.is_active:
            return {"ok": False, "error": "Operador não encontrado ou inativo."}

        order = await session.get(RealOrderDB, str(order_id))
        if not order:
            return {"ok": False, "error": "Pedido não encontrado no banco local."}

        already = (getattr(order, "picked_by", None) or "").strip()
        if already:
            return {
                "ok": False,
                "error": f"Pedido já está com {already}. Liberar antes de pegar de novo.",
            }

        role = normalize_role(operator.role)
        allowed = pickable_queue_names(role)
        current = (order.status_name or "").strip()
        if current.lower() not in {a.lower() for a in allowed}:
            return {
                "ok": False,
                "error": (
                    f"Fila '{current}' não é pickable para role {role}. "
                    f"Permitidas: {', '.join(sorted(allowed))}."
                ),
            }

        personal = await _ensure_personal_status(session, operator)
        order.picked_from_status_id = int(order.status_id or 0)
        order.picked_from_status_name = current
        order.picked_by = operator.name
        order.picked_by_id = int(operator.id)
        order.picked_at = datetime.now()
        order.status_id = int(personal.id)
        order.status_name = personal.name

        await _recalc_status_counts(session)
        await session.commit()
        await session.refresh(order)
        return {
            "ok": True,
            "action": "pickup",
            "message": f"Pedido #{order_id} puxado para {personal.name}.",
            "order": _order_payload(order),
        }


async def send_order_to_queue(
    order_id: str,
    operator_id: int,
    target_queue: Optional[str] = None,
) -> Dict[str, Any]:
    """Envia pedido da fila pessoal para destino padrão (ou explícito) por role."""
    await init_db()
    async with async_session() as session:
        operator = await session.get(OperatorDB, int(operator_id))
        if not operator or not operator.is_active:
            return {"ok": False, "error": "Operador não encontrado ou inativo."}

        order = await session.get(RealOrderDB, str(order_id))
        if not order:
            return {"ok": False, "error": "Pedido não encontrado no banco local."}

        role = normalize_role(operator.role)
        picked_id = int(getattr(order, "picked_by_id", 0) or 0)
        if picked_id and picked_id != int(operator.id) and role != ROLE_ADMIN:
            return {
                "ok": False,
                "error": f"Pedido está com {order.picked_by}. Só quem pegou ou Admin pode enviar.",
            }

        if not (getattr(order, "picked_by", None) or "").strip():
            if not is_personal_status_name(order.status_name) and not is_personal_status_id(
                order.status_id
            ):
                return {
                    "ok": False,
                    "error": "Pedido não está em fila pessoal. Use Pegar antes de Enviar.",
                }

        dest_name = (target_queue or "").strip() or default_send_queue_name(role)
        dest = await _find_status_by_name(session, dest_name)
        if not dest:
            max_id = 0
            all_st = (await session.execute(select(RealOrderStatusDB))).scalars().all()
            for s in all_st:
                if int(s.id) < PERSONAL_STATUS_ID_BASE:
                    max_id = max(max_id, int(s.id))
            dest = RealOrderStatusDB(
                id=max_id + 1 if max_id else 50,
                name=dest_name,
                color="#b80af7" if "Separ" in dest_name else "#22a564",
                count=0,
            )
            session.add(dest)
            await session.flush()

        order.status_id = int(dest.id)
        order.status_name = dest.name
        order.picked_by = ""
        order.picked_by_id = 0
        order.picked_from_status_id = 0
        order.picked_from_status_name = ""
        order.picked_at = None

        await _recalc_status_counts(session)
        await session.commit()
        await session.refresh(order)
        return {
            "ok": True,
            "action": "send",
            "message": f"Pedido #{order_id} enviado para {dest.name}.",
            "order": _order_payload(order),
        }


async def release_order(order_id: str, operator_id: int) -> Dict[str, Any]:
    """Libera pedido da fila pessoal → volta à fila geral de origem."""
    await init_db()
    async with async_session() as session:
        operator = await session.get(OperatorDB, int(operator_id))
        if not operator or not operator.is_active:
            return {"ok": False, "error": "Operador não encontrado ou inativo."}

        order = await session.get(RealOrderDB, str(order_id))
        if not order:
            return {"ok": False, "error": "Pedido não encontrado no banco local."}

        picked_id = int(getattr(order, "picked_by_id", 0) or 0)
        role = normalize_role(operator.role)
        if picked_id and picked_id != int(operator.id) and role != "Administrador":
            return {
                "ok": False,
                "error": f"Pedido está com {order.picked_by}. Só quem pegou ou Admin pode liberar.",
            }

        if not (getattr(order, "picked_by", None) or "").strip() and not is_personal_status_name(
            order.status_name
        ):
            return {"ok": False, "error": "Pedido não está pego (nada a liberar)."}

        origin_name = (getattr(order, "picked_from_status_name", None) or "").strip()
        origin_id = int(getattr(order, "picked_from_status_id", 0) or 0)
        origin = None
        if origin_id:
            origin = await session.get(RealOrderStatusDB, origin_id)
        if not origin and origin_name:
            origin = await _find_status_by_name(session, origin_name)
        if not origin:
            # fallback: Novos pedidos / Notebook - Geral
            for fallback in ("Novos pedidos", "Notebook - Geral", "Em Separação - Geral"):
                origin = await _find_status_by_name(session, fallback)
                if origin:
                    break
        if not origin:
            return {"ok": False, "error": "Não foi possível determinar a fila de origem."}

        order.status_id = int(origin.id)
        order.status_name = origin.name
        order.picked_by = ""
        order.picked_by_id = 0
        order.picked_from_status_id = 0
        order.picked_from_status_name = ""
        order.picked_at = None

        await _recalc_status_counts(session)
        await session.commit()
        await session.refresh(order)
        return {
            "ok": True,
            "action": "release",
            "message": f"Pedido #{order_id} liberado para {origin.name}.",
            "order": _order_payload(order),
        }
