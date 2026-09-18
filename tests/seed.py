"""A small, fully explained dataset for API and chat tests.

ACME has two peers: Globex (GLBX, with prices) and Initech (no ticker). It has three movements:
  2026-01-06  +5.00%  idiosyncratic  company   0.90   articles: acme-earnings (company 0.95), acme-store (company 0.10)
  2026-01-08  -4.00%  market         macro     0.70   articles: fed-hike (macro, 0.80)
  2026-01-12  +3.00%  sector         (not yet explained)   no articles
"""

from datetime import date

from sqlalchemy.orm import Session

from app.enums import DriverHint, ExplanationCategory, NewsTier
from app.models import Company, Explanation, Movement, MovementArticle
from app.repositories.articles import upsert_articles
from app.repositories.prices import upsert_prices
from tests.factories import article_hit, price_frame

UP_DAY, DOWN_DAY, UNEXPLAINED_DAY = date(2026, 1, 6), date(2026, 1, 8), date(2026, 1, 12)
CLOSES = [100, 105, 105, 100.8, 100.8, 103.824]
# Globex: flat on ACME's up day, -3% alongside ACME's market-driven drop, +1% on the last move
PEER_CLOSES = [50, 50, 50, 48.5, 48.5, 48.985]


def _movement(ticker: str, day: date, pct: float, hint: DriverHint) -> Movement:
    return Movement(
        ticker=ticker,
        date=day,
        close=100 + pct,
        prev_close=100,
        pct_change=pct,
        zscore=pct / 1.5,
        volume_ratio=1.8,
        market_pct_change=-2.5 if hint is DriverHint.MARKET else 0.1,
        sector_pct_change=None,
        excess_vs_market=pct + 2.5 if hint is DriverHint.MARKET else pct - 0.1,
        excess_vs_sector=None,
        driver_hint=hint,
        window_start=day,
        window_end=day,
    )


def seed_ticker(session: Session, ticker: str = "ACME") -> None:
    peers = [{"name": "Globex", "ticker": "GLBX"}, {"name": "Initech", "ticker": None}]
    session.add(Company(ticker=ticker, name="Acme Corp", sector="Technology", industry="Widgets", peers=peers))
    upsert_prices(session, ticker, price_frame(CLOSES))
    upsert_prices(session, "GLBX", price_frame(PEER_CLOSES))

    up = _movement(ticker, UP_DAY, 5.0, DriverHint.IDIOSYNCRATIC)
    down = _movement(ticker, DOWN_DAY, -4.0, DriverHint.MARKET)
    unexplained = _movement(ticker, UNEXPLAINED_DAY, 3.0, DriverHint.SECTOR)
    session.add_all([up, down, unexplained])
    session.flush()

    earnings, store, fed = upsert_articles(
        session, [article_hit("acme-earnings"), article_hit("acme-store"), article_hit("fed-hike")]
    )
    session.add_all(
        [
            MovementArticle(movement_id=up.id, article_id=earnings.id, tier=NewsTier.COMPANY, relevance=0.95),
            MovementArticle(movement_id=up.id, article_id=store.id, tier=NewsTier.COMPANY, relevance=0.10),
            MovementArticle(movement_id=down.id, article_id=fed.id, tier=NewsTier.MACRO, relevance=0.80),
            Explanation(
                movement_id=up.id,
                summary="Acme jumped after beating earnings.",
                category=ExplanationCategory.COMPANY,
                confidence=0.9,
                model="fake-model",
            ),
            Explanation(
                movement_id=down.id,
                summary="Acme fell with the market after a rate hike.",
                category=ExplanationCategory.MACRO,
                confidence=0.7,
                model="fake-model",
            ),
        ]
    )
    session.commit()
