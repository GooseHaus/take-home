import datetime as dt
from typing import TYPE_CHECKING

from sqlalchemy import Date, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.enums import DriverHint
from app.models.base import enum_column

if TYPE_CHECKING:
    from app.models.explanation import Explanation
    from app.models.movement_article import MovementArticle


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (UniqueConstraint("ticker", "date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), index=True)
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    close: Mapped[float] = mapped_column(Float)
    prev_close: Mapped[float] = mapped_column(Float)
    pct_change: Mapped[float] = mapped_column(Float)  # close-to-close, in percent (D3)
    zscore: Mapped[float | None] = mapped_column(Float)  # vs trailing 60d vol; None during warm-up
    volume_ratio: Mapped[float | None] = mapped_column(Float)  # volume / trailing 20d average
    market_pct_change: Mapped[float | None] = mapped_column(Float)
    sector_pct_change: Mapped[float | None] = mapped_column(Float)
    excess_vs_market: Mapped[float | None] = mapped_column(Float)
    excess_vs_sector: Mapped[float | None] = mapped_column(Float)
    driver_hint: Mapped[DriverHint] = enum_column(DriverHint)  # (D4)
    window_start: Mapped[dt.date] = mapped_column(Date)  # news search window
    window_end: Mapped[dt.date] = mapped_column(Date)

    explanation: Mapped["Explanation | None"] = relationship(back_populates="movement", uselist=False)
    article_links: Mapped[list["MovementArticle"]] = relationship(back_populates="movement")
