"""Compact, model-facing views of API shapes. Tool output is prompt context, so it carries less than the REST JSON."""

from app.constants.chat import TOOL_SNIPPET_CHARS
from app.schemas.api import ArticleResponse, MovementResponse
from app.utils.text import clean_text

NOT_EXPLAINED = "Not explained yet (outside the ingest's top-N largest moves)."


def _rounded(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def compact_article(article: ArticleResponse, with_snippet: bool = False) -> dict:
    row = {
        "title": article.title,
        "url": article.url,
        "source": article.source,
        "published": article.published_at.date().isoformat() if article.published_at else None,
        "tier": article.tier.value,
        "relevance": article.relevance,
    }
    if with_snippet:
        row["excerpt"] = clean_text(article.snippet, TOOL_SNIPPET_CHARS)
    return row


def compact_movement(movement: MovementResponse, max_articles: int | None, with_snippets: bool = False) -> dict:
    explanation = movement.explanation
    articles = movement.articles if max_articles is None else movement.articles[:max_articles]
    return {
        "ticker": movement.ticker,
        "date": movement.date.isoformat(),
        "pct_change": _rounded(movement.pct_change, 2),
        "market_pct_change": _rounded(movement.market_pct_change, 2),
        "sector_pct_change": _rounded(movement.sector_pct_change, 2),
        "zscore": _rounded(movement.zscore, 1),
        "volume_ratio": _rounded(movement.volume_ratio, 1),
        "driver_hint": movement.driver_hint.value,
        "peer_moves": {move.ticker: move.pct_change for move in movement.peer_moves},
        "category": explanation.category.value if explanation else None,
        "confidence": explanation.confidence if explanation else None,
        "explanation": explanation.summary if explanation else NOT_EXPLAINED,
        "articles": [compact_article(a, with_snippets) for a in articles],
    }
