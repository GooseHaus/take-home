from datetime import datetime

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(primary_key=True)
    url: Mapped[str] = mapped_column(String(2048), unique=True)
    title: Mapped[str] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(255))  # publisher domain
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    snippet: Mapped[str | None] = mapped_column(Text)
