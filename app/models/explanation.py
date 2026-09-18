from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import ExplanationCategory
from app.models.base import enum_column, utcnow
from app.models.utc_datetime import UTCDateTime

if TYPE_CHECKING:
    from app.models.movement import Movement


class Explanation(Base):
    __tablename__ = "explanations"

    movement_id: Mapped[int] = mapped_column(ForeignKey("movements.id"), primary_key=True)
    summary: Mapped[str] = mapped_column(Text)
    category: Mapped[ExplanationCategory] = enum_column(ExplanationCategory)
    confidence: Mapped[float] = mapped_column(Float)
    model: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    movement: Mapped["Movement"] = relationship(back_populates="explanation")
