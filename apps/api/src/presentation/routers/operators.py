"""Router FastAPI para CRUD de Operadores / Usuários (Etapa 1).

API canônica: /api/v1/operators (ROADMAP). Alias /api/v1/users aponta para o mesmo router.
Roles: Administrador | Técnico (Montagem) | Expedição (Separação).
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from pydantic import BaseModel, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime

from src.infrastructure.database import async_session, init_db, OperatorDB
from src.domain.operator_roles import (
    CANONICAL_ROLES,
    ROLE_ADMIN,
    ROLE_EXPEDICAO,
    ROLE_TECNICO,
    normalize_role,
    roles_for_ui,
)

router = APIRouter(prefix="/operators", tags=["Operators & Users CRUD"])
users_alias_router = APIRouter(prefix="/users", tags=["Users alias → operators"])


class OperatorCreate(BaseModel):
    name: str
    role: str = ROLE_TECNICO
    email: Optional[str] = ""
    is_active: bool = True

    @field_validator("role")
    @classmethod
    def _canon_role(cls, v: str) -> str:
        return normalize_role(v)


class OperatorUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def _canon_role(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return normalize_role(v)


class OperatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    role: str
    email: str
    is_active: bool
    created_at: datetime


INITIAL_OPERATORS = [
    {"id": 21, "name": "Admin (admin)", "role": ROLE_ADMIN, "email": "admin@4mc.com.br"},
    {"id": 1, "name": "José Wilsom De Oliveira Junior", "role": ROLE_ADMIN, "email": "josewilsom@4mc.com.br"},
    {"id": 2, "name": "Técnico Dayvid", "role": ROLE_TECNICO, "email": "dayvid@4mc.com.br"},
    {"id": 3, "name": "Técnico Gustavo", "role": ROLE_TECNICO, "email": "gustavo@4mc.com.br"},
    {"id": 4, "name": "Técnico Luan", "role": ROLE_TECNICO, "email": "luan@4mc.com.br"},
    {"id": 5, "name": "Técnica Maria Luiza", "role": ROLE_TECNICO, "email": "marialuiza@4mc.com.br"},
    {"id": 6, "name": "Técnico Mauricio", "role": ROLE_TECNICO, "email": "mauricio@4mc.com.br"},
    {"id": 7, "name": "Técnico Pietro", "role": ROLE_TECNICO, "email": "pietro@4mc.com.br"},
    {"id": 8, "name": "Técnico Thiago", "role": ROLE_TECNICO, "email": "thiago@4mc.com.br"},
    {"id": 9, "name": "Técnico José Barbosa", "role": ROLE_TECNICO, "email": "josebarbosa@4mc.com.br"},
    {"id": 10, "name": "Ingrid Dorta", "role": ROLE_EXPEDICAO, "email": "ingrid@4mc.com.br"},
    {"id": 11, "name": "Gabriel", "role": ROLE_EXPEDICAO, "email": "gabriel@4mc.com.br"},
    {"id": 12, "name": "Gustavo Cleytinho", "role": ROLE_TECNICO, "email": "gustavoc@4mc.com.br"},
]


async def seed_operators_if_empty():
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(OperatorDB))
        existing = result.scalars().all()
        if not existing:
            for op in INITIAL_OPERATORS:
                session.add(
                    OperatorDB(
                        id=op["id"],
                        name=op["name"],
                        role=normalize_role(op["role"]),
                        email=op["email"],
                        is_active=True,
                    )
                )
            await session.commit()
            return
        # Migração leve: normaliza roles legadas já gravadas
        dirty = False
        for op in existing:
            canon = normalize_role(op.role)
            if op.role != canon:
                op.role = canon
                dirty = True
        if dirty:
            await session.commit()


def _register_crud(r: APIRouter) -> None:
    @r.get("/roles")
    async def list_roles():
        return {"roles": roles_for_ui(), "canonical": list(CANONICAL_ROLES)}

    @r.get("", response_model=List[OperatorResponse])
    async def list_operators():
        await seed_operators_if_empty()
        async with async_session() as session:
            result = await session.execute(select(OperatorDB).order_by(OperatorDB.id.asc()))
            return result.scalars().all()

    @r.post("", response_model=OperatorResponse, status_code=201)
    async def create_operator(data: OperatorCreate):
        await init_db()
        if not (data.name or "").strip():
            raise HTTPException(status_code=400, detail="Nome é obrigatório")
        async with async_session() as session:
            new_op = OperatorDB(
                name=data.name.strip(),
                role=normalize_role(data.role),
                email=data.email.strip() if data.email else "",
                is_active=data.is_active,
            )
            session.add(new_op)
            await session.commit()
            await session.refresh(new_op)
            return new_op

    @r.put("/{operator_id}", response_model=OperatorResponse)
    async def update_operator(operator_id: int, data: OperatorUpdate):
        async with async_session() as session:
            op = await session.get(OperatorDB, operator_id)
            if not op:
                raise HTTPException(status_code=404, detail="Operador não encontrado")
            if data.name is not None:
                op.name = data.name.strip()
            if data.role is not None:
                op.role = normalize_role(data.role)
            if data.email is not None:
                op.email = data.email.strip()
            if data.is_active is not None:
                op.is_active = data.is_active
            await session.commit()
            await session.refresh(op)
            return op

    @r.delete("/{operator_id}")
    async def delete_operator(operator_id: int):
        async with async_session() as session:
            op = await session.get(OperatorDB, operator_id)
            if not op:
                raise HTTPException(status_code=404, detail="Operador não encontrado")
            await session.delete(op)
            await session.commit()
            return {"ok": True, "message": f"Operador #{operator_id} removido com sucesso"}


_register_crud(router)
_register_crud(users_alias_router)
