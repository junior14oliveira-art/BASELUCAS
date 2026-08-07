from fastapi import APIRouter
from pydantic import BaseModel
from src.agents.agents_orchestrator import orchestrator

router = APIRouter(prefix="/assistant", tags=["AssistantAgent IA Chat"])

class QueryRequest(BaseModel):
    prompt: str

@router.post("/chat")
async def chat_with_assistant(request: QueryRequest):
    result = await orchestrator.run_assistant_agent(request.prompt)
    return result
