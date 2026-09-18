from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.dependencies import get_llm_client
from app.providers.llm import LLMClient
from app.schemas.chat import ChatMessageResponse, ChatRequest, ChatResponse
from app.services.chat import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, summary="Ask questions about the stored movements and news")
def chat(
    request: ChatRequest,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[LLMClient, Depends(get_llm_client)],
):
    """Answers come only from stored data, via the same queries the REST endpoints use. `citations` lists the
    articles the answer links to; `tool_calls` shows which lookups it was built from. Pass the returned
    `conversation_id` back to ask a follow-up."""
    return chat_service.chat(session, llm, settings, request)


@router.get("/{conversation_id}", response_model=list[ChatMessageResponse], summary="The questions and answers so far")
def get_conversation(conversation_id: str, session: Annotated[Session, Depends(get_session)]):
    return chat_service.get_conversation(session, conversation_id)
