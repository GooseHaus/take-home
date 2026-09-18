from sqlalchemy.orm import Session

from app.repositories import movement_queries
from app.schemas.chat import PriceSummaryArgs
from app.schemas.movement_filters import MovementFilters
from app.services import ticker_data


class PriceSummaryTool:
    name = "price_summary"
    description = (
        "Price performance of a ticker over a period: start/end close, total return, high, low, and how many major "
        "movements fell inside it. Use for 'how did the stock do in Q2?' style questions."
    )
    args_model = PriceSummaryArgs

    def run(self, session: Session, args: PriceSummaryArgs) -> dict:
        ticker = ticker_data.normalize_ticker(args.ticker)
        ticker_data.require_company(session, ticker)
        # Same window rule as the REST endpoints: the warm-up history before the first ingest is not performance
        prices = movement_queries.get_prices(
            session, ticker, *ticker_data.price_window(session, ticker, args.start, args.end)
        )
        if not prices:
            return {"ticker": ticker, "error": "No stored prices in that period."}
        first, last = prices[0], prices[-1]
        high, low = max(prices, key=lambda p: p.high), min(prices, key=lambda p: p.low)
        _, movement_count = movement_queries.query_movements(
            session, ticker, MovementFilters(start=first.date, end=last.date, limit=1)
        )
        return {
            "ticker": ticker,
            "from": first.date.isoformat(),
            "to": last.date.isoformat(),
            "trading_days": len(prices),
            "start_close": round(first.close, 2),
            "end_close": round(last.close, 2),
            "total_return_pct": round((last.close / first.close - 1) * 100, 2),
            "high": {"date": high.date.isoformat(), "price": round(high.high, 2)},
            "low": {"date": low.date.isoformat(), "price": round(low.low, 2)},
            "major_movements": movement_count,
            "note": "Prices are split- and dividend-adjusted.",
        }
