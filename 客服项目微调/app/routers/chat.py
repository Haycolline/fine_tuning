from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ChatRequest, ChatResponse
from app.services import chat as chat_service

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    reply, conversation_id, intent, handoff = chat_service.handle_message(
        db, req.message, req.conversation_id
    )
    return ChatResponse(
        reply=reply, conversation_id=conversation_id, intent=intent, handoff=handoff
    )
