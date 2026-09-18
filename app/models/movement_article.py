from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models.article import Article
    from app.models.movement import Movement


class MovementArticle(Base):
    __tablename__ = "movement_articles"

    movement_id: Mapped[int] = mapped_column(ForeignKey("movements.id"), primary_key=True)
    article_id: Mapped[int] = mapped_column(ForeignKey("articles.id"), primary_key=True)
    tier: Mapped[str] = mapped_column(String(16))  # company | industry | macro
    relevance: Mapped[float | None] = mapped_column(Float)  # 0..1, set by the explanation pass (D6)

    movement: Mapped["Movement"] = relationship(back_populates="article_links")
    article: Mapped["Article"] = relationship()
