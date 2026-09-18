from datetime import datetime

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base
from app.models.base import utcnow


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict] = mapped_column(JSON)  # full OpenAI message dict, incl. tool calls
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
