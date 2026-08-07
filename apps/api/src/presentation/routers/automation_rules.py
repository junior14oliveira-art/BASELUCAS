from fastapi import APIRouter
from typing import Dict, Any, List
from src.infrastructure.automation_engine import automation_engine

router = APIRouter(prefix="/automation-rules", tags=["Motor de Automações SE/ENTÃO"])

@router.get("")
async def get_all_rules():
    """Lista todas as regras ativas de automação 'SE / ENTÃO'"""
    return [r.dict() for r in automation_engine.rules]

@router.post("/trigger-event")
async def trigger_event(payload: Dict[str, Any]):
    """Dispara um evento na esteira para avaliação do Motor de Automações"""
    event_name = payload.get("event_name", "pedido_pago")
    event_data = payload.get("event_data", {})
    results = await automation_engine.trigger_event(event_name, event_data)
    return {
        "status": "SUCCESS",
        "event_triggered": event_name,
        "executed_actions_count": len(results),
        "history": results
    }

@router.get("/history")
async def get_execution_history():
    """Retorna o histórico imutável de automações executadas pelo sistema"""
    return {"total": len(automation_engine.execution_history), "history": automation_engine.execution_history}
