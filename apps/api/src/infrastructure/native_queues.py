"""Catálogo de filas nativas do hub (SQLite only — BaseLinker é só molde)."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from src.domain.operator_roles import ROLE_ADMIN, ROLE_EXPEDICAO, ROLE_TECNICO, normalize_role

# Prefixo de filas pessoais pós-pickup
PERSONAL_QUEUE_PREFIX = "Fila · "
# IDs locais para filas pessoais (evita colidir com IDs BL importados)
PERSONAL_STATUS_ID_BASE = 900_000

# Filas gerais pickable por role (nome exact match, case-insensitive no lookup)
PICKABLE_BY_ROLE: Dict[str, Tuple[str, ...]] = {
    ROLE_TECNICO: (
        "Novos pedidos",
        "Notebook - Geral",
        "Computadores - Geral",
        "Fila Técnico",
        "Pedidos Agendados",
        "Para Enviar Amanhã",
    ),
    ROLE_EXPEDICAO: (
        "Em Separação - Geral",
        "Separação Finalizada",
    ),
    ROLE_ADMIN: (
        "Novos pedidos",
        "Notebook - Geral",
        "Computadores - Geral",
        "Fila Técnico",
        "Em Separação - Geral",
        "Pedidos Agendados",
        "Para Enviar Amanhã",
        "Separação Finalizada",
    ),
}

# Destino padrão ao "Enviar" por role
DEFAULT_SEND_BY_ROLE: Dict[str, str] = {
    ROLE_TECNICO: "Em Separação - Geral",
    ROLE_EXPEDICAO: "Pronto P/ Envio",
    ROLE_ADMIN: "Em Separação - Geral",
}

# Fallbacks de nome (BL usa variações)
STATUS_NAME_ALIASES: Dict[str, Tuple[str, ...]] = {
    "Pronto P/ Envio": ("Pronto p/ Envio", "Pronto P/ Envio", "Pronto para Envio"),
    "Em Separação - Geral": ("Em Separação - Geral", "Em Separacao - Geral"),
}


def personal_queue_name(operator_name: str) -> str:
    name = (operator_name or "Operador").strip() or "Operador"
    return f"{PERSONAL_QUEUE_PREFIX}{name}"


def personal_status_id(operator_id: int) -> int:
    return PERSONAL_STATUS_ID_BASE + int(operator_id)


def is_personal_status_name(name: Optional[str]) -> bool:
    n = (name or "").strip()
    return n.startswith(PERSONAL_QUEUE_PREFIX) or n.lower().startswith("fila ·") or n.lower().startswith("fila ·")


def is_personal_status_id(status_id: Optional[int]) -> bool:
    try:
        sid = int(status_id or 0)
    except (TypeError, ValueError):
        return False
    return sid >= PERSONAL_STATUS_ID_BASE


def pickable_queue_names(role: Optional[str]) -> Set[str]:
    canon = normalize_role(role)
    names = PICKABLE_BY_ROLE.get(canon, PICKABLE_BY_ROLE[ROLE_TECNICO])
    out: Set[str] = set()
    for n in names:
        out.add(n)
        for aliases in STATUS_NAME_ALIASES.values():
            if n in aliases:
                out.update(aliases)
    return out


def default_send_queue_name(role: Optional[str]) -> str:
    canon = normalize_role(role)
    return DEFAULT_SEND_BY_ROLE.get(canon, "Em Separação - Geral")


def resolve_status_name_variants(preferred: str) -> List[str]:
    """Lista de nomes candidatos para achar fila no SQLite."""
    preferred = (preferred or "").strip()
    variants = [preferred]
    for canon, aliases in STATUS_NAME_ALIASES.items():
        if preferred == canon or preferred in aliases:
            variants = list(aliases)
            if canon not in variants:
                variants.insert(0, canon)
            break
    # unicidade preservando ordem
    seen = set()
    out: List[str] = []
    for v in variants:
        key = v.lower()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return out
