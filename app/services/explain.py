"""Turn a movement + its candidate articles into a stored, cited explanation (D6)."""

import logging

from sqlalchemy.orm import Session

from app.constants.llm import MAX_ARTICLES_IN_PROMPT
from app.constants.market import MARKET_TICKER
from app.domain import PeerMove
from app.enums import NewsTier
from app.models import Article, Company, Explanation, Movement
from app.prompts import load_prompt
from app.providers.llm import LLMClient
from app.repositories.explanations import save_explanation
from app.repositories.movements import linked_articles
from app.schemas.llm import ExplanationOutput
from app.services.news.registry import NEWS_TIERS

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = "explain_movement_system"
USER_PROMPT = "explain_movement_user"
NOT_AVAILABLE = "n/a"
TIER_QUOTAS = {strategy.tier: strategy.max_results for strategy in NEWS_TIERS}
NO_ARTICLES = "(no articles were found for this window)"
NO_PEER_MOVES = "(no competitor prices available)"


def _signed_pct(value: float | None) -> str:
    return NOT_AVAILABLE if value is None else f"{value:+.2f}%"


def _ratio(value: float | None, suffix: str = "") -> str:
    return NOT_AVAILABLE if value is None else f"{value:.1f}{suffix}"


def format_article(article: Article, tier: str) -> str:
    published = article.published_at.date().isoformat() if article.published_at else "undated"
    return (
        f"[id={article.id}] {published} | {article.source or 'unknown source'} | found by: {tier} search\n"
        f"  Title: {article.title}\n"
        f"  Excerpt: {article.snippet or '(none)'}"
    )


def format_peer_moves(peer_moves: list[PeerMove]) -> str:
    return "\n".join(f"{p.name} ({p.ticker}): {p.pct_change:+.2f}%" for p in peer_moves) or NO_PEER_MOVES


def build_user_prompt(
    movement: Movement, company: Company, articles: list[tuple[str, Article]], peer_moves: list[PeerMove] | None = None
) -> str:
    """`articles` is (tier, article) pairs, already trimmed to what the model should see."""
    return load_prompt(USER_PROMPT).substitute(
        company_name=company.name,
        ticker=company.ticker,
        sector=company.sector or NOT_AVAILABLE,
        industry=company.industry or NOT_AVAILABLE,
        date=movement.date.isoformat(),
        weekday=movement.date.strftime("%A"),
        pct_change=f"{movement.pct_change:+.2f}",
        prev_close=f"{movement.prev_close:.2f}",
        close=f"{movement.close:.2f}",
        zscore=_ratio(movement.zscore),
        volume_ratio=_ratio(movement.volume_ratio, "x"),
        market_ticker=MARKET_TICKER,
        market_pct_change=_signed_pct(movement.market_pct_change),
        sector_etf=company.sector_etf or NOT_AVAILABLE,
        sector_pct_change=_signed_pct(movement.sector_pct_change),
        excess_vs_market=_signed_pct(movement.excess_vs_market),
        excess_vs_sector=_signed_pct(movement.excess_vs_sector),
        driver_hint=movement.driver_hint.value,
        peer_moves=format_peer_moves(peer_moves or []),
        window_start=movement.window_start.isoformat(),
        window_end=movement.window_end.isoformat(),
        articles="\n\n".join(format_article(a, tier) for tier, a in articles) or NO_ARTICLES,
    )


def prompt_articles(session: Session, movement: Movement) -> list[tuple[str, Article]]:
    """The articles the model sees: up to each tier's quota, newest first within a tier, shown oldest to newest.

    Re-fetching news for a recent move (D19) can link more articles than fit. Later coverage ("shares fell
    after...") is the strongest evidence, so when something has to go it is the oldest article of that tier.
    """
    by_tier: dict[NewsTier, list[Article]] = {}
    for link, article in linked_articles(session, movement):
        by_tier.setdefault(link.tier, []).append(article)

    chosen = []
    for tier, articles in by_tier.items():
        newest_first = sorted(articles, key=lambda a: (a.published_at is not None, a.published_at), reverse=True)
        chosen += [(tier.value, article) for article in newest_first[: TIER_QUOTAS[tier]]]
    chosen.sort(key=lambda pair: (pair[1].published_at is None, pair[1].published_at, pair[1].id))
    return chosen[:MAX_ARTICLES_IN_PROMPT]


def request_explanation(llm: LLMClient, user_prompt: str) -> ExplanationOutput:
    """The network half, free of any Session so the pipeline can run many of these in parallel."""
    return llm.structured(load_prompt(SYSTEM_PROMPT).template, user_prompt, ExplanationOutput)


def explain_movement(
    session: Session, llm: LLMClient, movement: Movement, company: Company, peer_moves: list[PeerMove] | None = None
) -> Explanation:
    user_prompt = build_user_prompt(movement, company, prompt_articles(session, movement), peer_moves)
    output = request_explanation(llm, user_prompt)
    logger.info("%s %s explained as %s (%.2f)", movement.ticker, movement.date, output.category, output.confidence)
    return save_explanation(session, movement, output, llm.model)
