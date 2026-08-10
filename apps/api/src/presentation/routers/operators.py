"""Router FastAPI para CRUD de Operadores / Técnicos / Usuários."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, delete
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from src.infrastructure.database import async_session, init_db, OperatorDB

router = APIRouter(prefix="/operators", tags=["Operators & Users CRUD"])

class OperatorCreate(BaseModel):
    name: str
    role: str = "Técnico"
    email: Optional[str] = ""
    is_active: bool = True

class OperatorUpdate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    email: Optional[str] = None
    is_active: Optional[bool] = None

class OperatorResponse(BaseModel):
    id: int
    name: str
    role: str
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

INITIAL_OPERATORS = [
    {"id": 21, "name": "Admin (admin)", "role": "Administrador", "email": "admin@4mc.com.br"},
    {"id": 1, "name": "José Wilsom De Oliveira Junior", "role": "Gerente TI / Operações", "email": "josewilsom@4mc.com.br"},
    {"id": 2, "name": "Técnico Dayvid", "role": "Técnico Notebooks", "email": "dayvid@4mc.com.br"},
    {"id": 3, "name": "Técnico Gustavo", "role": "Técnico Computadores", "email": "gustavo@4mc.com.br"},
    {"id": 4, "name": "Técnico Luan", "role": "Técnico Hardware", "email": "luan@4mc.com.br"},
    {"id": 5, "name": "Técnica Maria Luiza", "role": "Técnica Testes", "email": "marialuiza@4mc.com.br"},
    {"id": 6, "name": "Técnico Mauricio", "role": "Técnico Bancada", "email": "mauricio@4mc.com.br"},
    {"id": 7, "name": "Técnico Pietro", "role": "Técnico Triagem", "email": "pietro@4mc.com.br"},
    {"id": 8, "name": "Técnico Thiago", "role": "Técnico Desktops", "email": "thiago@4mc.com.br"},
    {"id": 9, "name": "Técnico José Barbosa", "role": "Técnico Manutenção", "email": "josebarbosa@4mc.com.br"},
    {"id": 10, "name": "Ingrid Dorta", "role": "Separação / Expedição", "email": "ingrid@4mc.com.br"},
    {"id": 11, "name": "Gabriel", "role": "Separação / Pacotes", "email": "gabriel@4mc.com.br"},
    {"id": 12, "name": "Gustavo Cleytinho", "role": "Técnico Suporte", "email": "gustavoc@4mc.com.br"},
]

async def seed_operators_if_empty():
    await init_db()
    async with async_session() as session:
        result = await session.execute(select(OperatorDB))
        existing = result.scalars().all()
        if not existing:
            for op in INITIAL_OPERATORS:
                session.add(OperatorDB(
                    id=op["id"],
                    name=op["name"],
                    role=op["role"],
                    email=op["email"],
                    is_active=True
                ))
            await session.commit()

@router.get("", response_model=List[OperatorResponse])
async def list_operators():
    """Lista todos os operadores e técnicos cadastrados."""
    await seed_operators_if_empty()
    async with async_session() as session:
        result = await session.execute(select(OperatorDB).order_by(OperatorDB.id.asc()))
        return result.scalars().all()

@router.post("", response_model=OperatorResponse, status_code=201)
async def create_operator(data: OperatorCreate):
    """Cadastra um novo operador ou técnico."""
    await init_db()
    async with async_session() as session:
        new_op = OperatorDB(
            name=data.name.strip(),
            role=data.role.strip(),
            email=data.email.strip() if data.email else "",
            is_active=data.is_active
        )
        session.add(new_op)
        await session.commit()
        await session.refresh(new_op)
        return new_op

@router.put("/{operator_id}", response_model=OperatorResponse)
async def update_operator(operator_id: int, data: OperatorUpdate):
    """Atualiza dados de um operador existente."""
    async with async_session() as session:
        op = await session.get(OperatorDB, operator_id)
        if not op:
            raise HTTPException(status_code=404, detail="Operador não encontrado")
        if data.name is not None:
            op.name = data.name.strip()
        if data.role is not None:
            op.role = data.role.strip()
        if data.email is not None:
            op.email = data.email.strip()
        if data.is_active is not None:
            op.is_active = data.is_active
        await session.commit()
        await session.refresh(op)
        return op

@router.delete("/{operator_id}")
async def delete_operator(operator_id: int):
    """Remove um operador."""
    async with async_session() as session:
        op = await session.get(OperatorDB, operator_id)
        if not op:
            raise HTTPException(status_code=404, detail="Operador não encontrado")
        await session.delete(op)
        await session.commit()
        return {"ok": True, "message": f"Operador #{operator_id} removido com sucesso"}
