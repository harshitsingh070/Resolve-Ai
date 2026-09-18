from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.agent.orchestrator import handle_chat

router = APIRouter()

class ChatRequest(BaseModel):
    pnr: str = ""
    message: str

@router.post("/chat")
def post_chat(req: ChatRequest, db: Session = Depends(get_db)):
    # Validate message
    if not req.message or not req.message.strip():
        return {"response": "Please enter a message.", "intent": {"primary_intent": "unknown"}, "actions": [], "escalation": None, "decision_trace": ["Empty message"], "booking": None, "customer": None, "ask_for_pnr": False}
    if len(req.message) > 2000:
        req.message = req.message[:2000]
    res = handle_chat(db, req.pnr or "", req.message)
    return res
