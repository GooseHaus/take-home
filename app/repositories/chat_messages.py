from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ChatMessage


def add_messages(session: Session, conversation_id: str, messages: list[dict]) -> None:
    """Store full chat-completions message dicts (tool calls and tool results included) as an audit trail."""
    session.add_all(ChatMessage(conversation_id=conversation_id, role=m["role"], content=m) for m in messages)
    session.flush()


def get_messages(session: Session, conversation_id: str) -> list[ChatMessage]:
    return list(
        session.scalars(
            select(ChatMessage).where(ChatMessage.conversation_id == conversation_id).order_by(ChatMessage.id)
        )
    )


def conversation_exists(session: Session, conversation_id: str) -> bool:
    return (
        session.scalars(select(ChatMessage.id).where(ChatMessage.conversation_id == conversation_id)).first()
        is not None
    )
