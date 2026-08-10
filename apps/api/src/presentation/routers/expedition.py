"""Etapa 4 — Expedição: bipagem (scanner USB) → checa ZPL engatilhada → imprime."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from src.infrastructure.database import RealOrderDB, async_session, init_db
from src.infrastructure import zpl_printer

router = APIRouter(prefix="/expedition", tags=["Expedição — Bipagem & ZPL"])

READY_STATUS_HINTS = (
    "pronto para bipagem",
    "pronto p/ bipagem",
    "pronto p/ envio",
    "pronto para envio",
)


class ScanPayload(BaseModel):
    barcode: str = Field(..., min_length=1, description="Código bipado (pedido, shipping_id, tracking…)")
    dry_run: Optional[bool] = Field(
        None,
        description="Força modo dry-run (True) ou usa ZPL_PRINT_MODE do .env (omitido).",
    )


class ArmPayload(BaseModel):
    """Engatilha ZPL de teste (simula saída da Etapa 3) sem tocar Bling/NF."""
    zpl: Optional[str] = None
    nfe_access_key: Optional[str] = None
    mark_ready_status: bool = True


def _enrichment_dict(order: RealOrderDB) -> Dict[str, Any]:
    try:
        data = json.loads(order.enrichment_json or "{}")
        return data if isinstance(data, dict) else {}
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def is_zpl_armed(order: RealOrderDB) -> bool:
    """Lê 'etiqueta engatilhada' — colunas Etapa 3/4 ou enrichment_json."""
    if bool(getattr(order, "zpl_armed", False)):
        return True
    enrich = _enrichment_dict(order)
    if enrich.get("zpl_armed") is True or enrich.get("label_armed") is True:
        return True
    if (enrich.get("zpl_content") or enrich.get("zpl") or "").strip():
        return True
    return False


def get_zpl_content(order: RealOrderDB) -> str:
    direct = (getattr(order, "zpl_content", None) or "").strip()
    if direct:
        return direct
    enrich = _enrichment_dict(order)
    return (enrich.get("zpl_content") or enrich.get("zpl") or "").strip()


async def find_order_by_barcode(barcode: str) -> Optional[RealOrderDB]:
    code = (barcode or "").strip()
    if not code:
        return None
    async with async_session() as session:
        # Match exato em IDs operacionais
        row = (
            await session.execute(
                select(RealOrderDB).where(
                    or_(
                        RealOrderDB.id == code,
                        RealOrderDB.external_id == code,
                        RealOrderDB.shipping_id == code,
                        RealOrderDB.pack_id == code,
                        RealOrderDB.tracking_number == code,
                    )
                )
            )
        ).scalars().first()
        if row:
            return row
        # Fallback: sufixo numérico comum em scanners (#123 → 123)
        stripped = code.lstrip("#").strip()
        if stripped != code:
            row = (
                await session.execute(select(RealOrderDB).where(RealOrderDB.id == stripped))
            ).scalars().first()
            if row:
                return row
        # Contém (shipping_id longo / ML)
        like = f"%{code}%"
        row = (
            await session.execute(
                select(RealOrderDB)
                .where(
                    or_(
                        RealOrderDB.id.like(like),
                        RealOrderDB.external_id.like(like),
                        RealOrderDB.shipping_id.like(like),
                        RealOrderDB.tracking_number.like(like),
                    )
                )
                .limit(1)
            )
        ).scalars().first()
        return row


def _order_public(order: RealOrderDB) -> Dict[str, Any]:
    return {
        "id": order.id,
        "external_id": order.external_id,
        "customer": order.customer_name,
        "status": order.status_name,
        "shipping_id": order.shipping_id or "",
        "tracking_number": order.tracking_number or "",
        "zpl_armed": is_zpl_armed(order),
        "nfe_access_key": (getattr(order, "nfe_access_key", None) or "")[:8] + "…"
        if (getattr(order, "nfe_access_key", None) or "")
        else "",
        "zpl_printed_at": order.zpl_printed_at.isoformat() if order.zpl_printed_at else None,
        "bling_status": getattr(order, "bling_status", "") or "",
    }


@router.get("/printer")
async def get_printer_status():
    await init_db()
    return {"ok": True, **zpl_printer.printer_status()}


@router.get("/ready")
async def list_ready_for_scan(limit: int = 50):
    """Pedidos com ZPL engatilhada (fila da bancada)."""
    await init_db()
    async with async_session() as session:
        rows = (
            await session.execute(
                select(RealOrderDB)
                .where(RealOrderDB.zpl_armed.is_(True))
                .order_by(RealOrderDB.created_at.desc())
                .limit(max(1, min(limit, 200)))
            )
        ).scalars().all()
        return {
            "ok": True,
            "total": len(rows),
            "orders": [_order_public(o) for o in rows],
            "printer": zpl_printer.printer_status(),
        }


@router.post("/scan")
async def scan_and_print(payload: ScanPayload):
    """Bipar código → verificar ZPL engatilhada → enviar à impressora (ou dry-run)."""
    await init_db()
    barcode = (payload.barcode or "").strip()
    if not barcode:
        raise HTTPException(status_code=400, detail="Código de barras vazio.")

    order = await find_order_by_barcode(barcode)
    if not order:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Pedido não encontrado para o código '{barcode}'. "
                "Confira se o scanner leu o ID do pedido / shipping_id."
            ),
        )

    if not is_zpl_armed(order):
        status_hint = (order.status_name or "").lower()
        waiting_note = ""
        if any(h in status_hint for h in READY_STATUS_HINTS):
            waiting_note = " A fila sugere pronto, mas a etiqueta ainda não foi engatilhada no banco."
        raise HTTPException(
            status_code=409,
            detail=(
                f"Pedido #{order.id} ainda sem etiqueta ZPL engatilhada "
                f"(status: {order.status_name or '—'})."
                f"{waiting_note} Aguarde a Etapa 3 (NF-e/webhook) ou use o armamento de teste."
            ),
        )

    zpl = get_zpl_content(order)
    if not zpl:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Pedido #{order.id} marcado como engatilhado, mas o conteúdo ZPL está vazio. "
                "Re-baixe a etiqueta (Etapa 3) antes de bipar."
            ),
        )

    mode_override = "dry_run" if payload.dry_run is True else None
    result = zpl_printer.send_zpl(zpl, order_id=order.id, mode_override=mode_override)

    if not result.ok:
        raise HTTPException(
            status_code=502,
            detail={
                "message": result.message,
                "printer": result.as_dict(),
                "order": _order_public(order),
            },
        )

    async with async_session() as session:
        row = (
            await session.execute(select(RealOrderDB).where(RealOrderDB.id == order.id))
        ).scalars().first()
        if row:
            row.zpl_printed_at = datetime.now()
            await session.commit()
            order = row

    return {
        "ok": True,
        "message": result.message,
        "barcode": barcode,
        "order": _order_public(order),
        "printer": result.as_dict(),
    }


@router.post("/arm/{order_id}")
async def arm_zpl_for_test(order_id: str, payload: ArmPayload = ArmPayload()):
    """Engatilha ZPL de demo no pedido (substitui Etapa 3 em testes manuais)."""
    await init_db()
    async with async_session() as session:
        order = (
            await session.execute(select(RealOrderDB).where(RealOrderDB.id == order_id))
        ).scalars().first()
        if not order:
            raise HTTPException(status_code=404, detail=f"Pedido #{order_id} não encontrado.")

        zpl = (payload.zpl or "").strip() or zpl_printer.build_sample_zpl(
            order.id, barcode=order.shipping_id or order.id
        )
        order.zpl_armed = True
        order.zpl_content = zpl
        if payload.nfe_access_key:
            order.nfe_access_key = payload.nfe_access_key.strip()
        if payload.mark_ready_status:
            order.status_name = "Pronto para Bipagem"
        # Espelha no enrichment para leitores que só olhem o JSON
        enrich = _enrichment_dict(order)
        enrich["zpl_armed"] = True
        enrich["zpl_content"] = zpl
        order.enrichment_json = json.dumps(enrich, ensure_ascii=False)
        await session.commit()
        await session.refresh(order)

        return {
            "ok": True,
            "message": f"ZPL engatilhada no pedido #{order.id} (teste / Etapa 3 simulada).",
            "order": _order_public(order),
            "zpl_chars": len(zpl),
        }
