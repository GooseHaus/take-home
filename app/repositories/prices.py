import pandas as pd
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from app.constants.market import PRICE_UPSERT_CHUNK_SIZE
from app.models import Price

VALUE_COLUMNS = ("open", "high", "low", "close", "volume")


def upsert_prices(session: Session, ticker: str, bars: pd.DataFrame) -> int:
    rows = [
        {
            "ticker": ticker,
            "date": day,
            "open": float(bar.open),
            "high": float(bar.high),
            "low": float(bar.low),
            "close": float(bar.close),
            "volume": int(bar.volume),
        }
        for day, bar in bars.iterrows()
    ]
    for i in range(0, len(rows), PRICE_UPSERT_CHUNK_SIZE):
        stmt = insert(Price).values(rows[i : i + PRICE_UPSERT_CHUNK_SIZE])
        # Adjusted closes shift after each dividend, so refresh existing rows rather than skipping them (D12)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "date"],
            set_={column: stmt.excluded[column] for column in VALUE_COLUMNS},
        )
        session.execute(stmt)
    return len(rows)


def load_price_frame(session: Session, ticker: str) -> pd.DataFrame:
    """Date-indexed close/volume frame, the shape movement detection consumes."""
    rows = session.execute(
        select(Price.date, Price.close, Price.volume).where(Price.ticker == ticker).order_by(Price.date)
    ).all()
    return pd.DataFrame(
        {"close": [r.close for r in rows], "volume": [r.volume for r in rows]},
        index=pd.Index([r.date for r in rows], name="date"),
    )
