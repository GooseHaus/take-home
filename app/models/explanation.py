from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.base import utcnow

if TYPE_CHECKING:
    from app.models.movement import Movement


class Explanation(Base):
    __tablename__ = "explanations"

    movement_id: Mapped[int] = mapped_column(ForeignKey("movements.id"), primary_key=True)
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(16))  # company | industry | macro | unexplained
    confidence: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    movement: Mapped["Movement"] = relationship(back_populates="explanation")
