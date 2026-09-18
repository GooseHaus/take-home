"""Competitors: who they are, their prices, and how they moved on a given day (D5, D20).

Peers are suggested by one LLM call per ticker and cached on the company row as `[{"name", "ticker"}]`.
"""

import logging
import re
from datetime import date, timedelta

import pandas as pd
from sqlalchemy.orm import Session

from app.constants.api import TICKER_PATTERN
from app.constants.market import WARMUP_DAYS
from app.constants.news import MAX_PEERS
from app.domain import Peer, PeerMove
from app.errors import AppError, ProviderError
from app.models import Company
from app.prompts import load_prompt
from app.providers.llm import LLMClient
from app.providers.market_data import MarketDataProvider
from app.repositories.prices import load_price_frame, upsert_prices
from app.schemas.llm import PeersOutput
from app.services.movements import pct_returns

logger = logging.getLogger(__name__)

NOT_AVAILABLE = "n/a"
_TICKER = re.compile(TICKER_PATTERN)


def company_peers(company: Company) -> list[Peer]:
    """Stored peers as objects. Rows written before D20 hold plain names, which load as peers without a ticker."""
    peers = []
    for item in company.peers or []:
        if isinstance(item, str):
            peers.append(Peer(name=item))
        else:
            peers.append(Peer(name=item["name"], ticker=item.get("ticker")))
    return peers


def _needs_suggestion(company: Company) -> bool:
    # Names only means the row predates ticker support, so ask again once to get tickers
    return company.peers is None or any(isinstance(item, str) for item in company.peers)


def _clean_ticker(raw: str | None, own_ticker: str) -> str | None:
    ticker = (raw or "").strip().upper()
    return ticker if _TICKER.match(ticker) and ticker != own_ticker else None


def ensure_peers(session: Session, llm: LLMClient, company: Company) -> list[Peer]:
    if not _needs_suggestion(company):
        return company_peers(company)
    try:
        output = llm.structured(
            load_prompt("suggest_peers_system").substitute(max_peers=MAX_PEERS),
            load_prompt("suggest_peers_user").substitute(
                company_name=company.name,
                ticker=company.ticker,
                sector=company.sector or NOT_AVAILABLE,
                industry=company.industry or NOT_AVAILABLE,
            ),
            PeersOutput,
        )
    except ProviderError as exc:
        # Not cached, so the next ingest tries again. The industry tier falls back to what is stored, if anything.
        logger.warning("peer suggestion failed for %s: %s", company.ticker, exc.message)
        return company_peers(company)

    suggested = [p for p in output.peers if p.name.strip()][:MAX_PEERS]
    company.peers = [{"name": p.name.strip(), "ticker": _clean_ticker(p.ticker, company.ticker)} for p in suggested]
    session.commit()
    logger.info("peers for %s: %s", company.ticker, company.peers)
    return company_peers(company)


def ingest_peer_prices(
    session: Session, provider: MarketDataProvider, peers: list[Peer], start: date, end: date
) -> list[str]:
    """Store price history for peers that have a ticker. A peer whose prices can't be fetched is skipped.

    All fetches finish before the first write, so the write lock is never held across a network call.
    """
    fetched = {}
    for peer in peers:
        if not peer.ticker:
            continue
        try:
            fetched[peer.ticker] = provider.fetch_history(peer.ticker, start - timedelta(days=WARMUP_DAYS), end)
        except AppError as exc:
            logger.warning("no prices for peer %s (%s): %s", peer.name, peer.ticker, exc.message)
    for peer_ticker, bars in fetched.items():
        upsert_prices(session, peer_ticker, bars)
    session.commit()
    return list(fetched)


def load_peer_returns(session: Session, peers: list[Peer]) -> dict[str, pd.Series]:
    """Daily percent returns per peer ticker, for peers that have stored prices."""
    returns = {}
    for peer in peers:
        if not peer.ticker:
            continue
        frame = load_price_frame(session, peer.ticker)
        if not frame.empty:
            returns[peer.ticker] = pct_returns(frame["close"])
    return returns


def peer_moves_on(day: date, peers: list[Peer], returns: dict[str, pd.Series]) -> list[PeerMove]:
    moves = []
    for peer in peers:
        series = returns.get(peer.ticker)
        if series is None or day not in series.index or pd.isna(series[day]):
            continue
        moves.append(PeerMove(name=peer.name, ticker=peer.ticker, pct_change=round(float(series[day]), 2)))
    return moves
