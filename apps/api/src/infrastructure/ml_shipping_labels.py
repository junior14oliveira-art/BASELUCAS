"""Etiquetas Mercado Envios — gate de produção + preview (Etapa 3/4).

Download real usa OAuth ML + GET /shipment_labels.
Com ML_READ_ONLY a *escrita* (billing_info) fica gated; o GET da etiqueta
pode seguir se o envio já estiver liberado no ML.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from sqlalchemy import select

from src.config import settings
from src.infrastructure.database import MLAccountDB, async_session, init_db


@dataclass
class LabelGate:
    allowed: bool
    reason: str
    code: str

    def as_detail(self) -> Dict[str, Any]:
        return {
            "status": "OK" if self.allowed else "GATED",
            "allowed": self.allowed,
            "reason": self.reason,
            "code": self.code,
            "ml_read_only": bool(settings.ML_READ_ONLY),
            "docs": "docs/LABELS_ML.md",
        }


def evaluate_production_gate(
    *,
    has_oauth: bool,
    has_token: bool,
    shipment_id: str,
    shipping_status: str = "",
) -> LabelGate:
    if not (shipment_id or "").strip():
        return LabelGate(False, "Pedido sem shipping_id (Mercado Envios).", "missing_shipment")
    if not has_oauth or not has_token:
        return LabelGate(
            False,
            "OAuth ML ausente — conecte a conta em /api/v1/ml/auth antes de baixar ZPL.",
            "missing_oauth",
        )
    status = (shipping_status or "").lower()
    if status in ("cancelled", "canceled", "closed"):
        return LabelGate(False, f"Envio em status terminal: {shipping_status}", "bad_shipping_status")
    return LabelGate(True, "Gate OK para tentar download da etiqueta.", "ok")


async def get_active_ml_account() -> Optional[MLAccountDB]:
    await init_db()
    async with async_session() as session:
        result = await session.execute(
            select(MLAccountDB).where(MLAccountDB.is_active == True)  # noqa: E712
        )
        return result.scalars().first()
