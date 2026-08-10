"""Roles canônicas do chão de fábrica (Etapa 1)."""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

# Valor persistido em OperatorDB.role (rótulo PT-BR)
ROLE_ADMIN = "Administrador"
ROLE_TECNICO = "Técnico (Montagem)"
ROLE_EXPEDICAO = "Expedição (Separação)"

CANONICAL_ROLES: Tuple[str, ...] = (ROLE_ADMIN, ROLE_TECNICO, ROLE_EXPEDICAO)

# Aliases legados / seed → canônico
_ROLE_ALIASES: Dict[str, str] = {
    "admin": ROLE_ADMIN,
    "administrador": ROLE_ADMIN,
    "administrator": ROLE_ADMIN,
    "gerente ti / operações": ROLE_ADMIN,
    "gerente": ROLE_ADMIN,
    "tecnico": ROLE_TECNICO,
    "técnico": ROLE_TECNICO,
    "tecnico (montagem)": ROLE_TECNICO,
    "técnico (montagem)": ROLE_TECNICO,
    "montagem": ROLE_TECNICO,
    "tecnico notebooks": ROLE_TECNICO,
    "técnico notebooks": ROLE_TECNICO,
    "tecnico computadores": ROLE_TECNICO,
    "técnico computadores": ROLE_TECNICO,
    "tecnico hardware": ROLE_TECNICO,
    "técnico hardware": ROLE_TECNICO,
    "tecnica testes": ROLE_TECNICO,
    "técnica testes": ROLE_TECNICO,
    "tecnico bancada": ROLE_TECNICO,
    "técnico bancada": ROLE_TECNICO,
    "tecnico triagem": ROLE_TECNICO,
    "técnico triagem": ROLE_TECNICO,
    "tecnico desktops": ROLE_TECNICO,
    "técnico desktops": ROLE_TECNICO,
    "tecnico manutenção": ROLE_TECNICO,
    "técnico manutenção": ROLE_TECNICO,
    "tecnico suporte": ROLE_TECNICO,
    "técnico suporte": ROLE_TECNICO,
    "separacao": ROLE_EXPEDICAO,
    "separação": ROLE_EXPEDICAO,
    "expedicao": ROLE_EXPEDICAO,
    "expedição": ROLE_EXPEDICAO,
    "expedição (separação)": ROLE_EXPEDICAO,
    "expedicao (separacao)": ROLE_EXPEDICAO,
    "separação / expedição": ROLE_EXPEDICAO,
    "separacao / expedicao": ROLE_EXPEDICAO,
    "separação / pacotes": ROLE_EXPEDICAO,
    "separacao / pacotes": ROLE_EXPEDICAO,
}


def normalize_role(raw: Optional[str]) -> str:
    """Normaliza qualquer string de role para um dos 3 canônicos."""
    if not raw or not str(raw).strip():
        return ROLE_TECNICO
    key = str(raw).strip().lower()
    if key in _ROLE_ALIASES:
        return _ROLE_ALIASES[key]
    # Prefixo / substring
    if "admin" in key or "gerente" in key:
        return ROLE_ADMIN
    if "separ" in key or "exped" in key or "pacote" in key:
        return ROLE_EXPEDICAO
    if "técn" in key or "tecn" in key or "montag" in key:
        return ROLE_TECNICO
    # Já canônico (case-insensitive)
    for c in CANONICAL_ROLES:
        if key == c.lower():
            return c
    return ROLE_TECNICO


def role_slug(role: Optional[str]) -> str:
    """Slug interno: admin | tecnico | separacao."""
    canon = normalize_role(role)
    if canon == ROLE_ADMIN:
        return "admin"
    if canon == ROLE_EXPEDICAO:
        return "separacao"
    return "tecnico"


def is_valid_role(raw: Optional[str]) -> bool:
    if not raw:
        return False
    key = str(raw).strip().lower()
    if key in {c.lower() for c in CANONICAL_ROLES}:
        return True
    return key in _ROLE_ALIASES


def roles_for_ui() -> List[Dict[str, str]]:
    return [
        {"value": ROLE_ADMIN, "slug": "admin", "label": ROLE_ADMIN},
        {"value": ROLE_TECNICO, "slug": "tecnico", "label": ROLE_TECNICO},
        {"value": ROLE_EXPEDICAO, "slug": "separacao", "label": ROLE_EXPEDICAO},
    ]
