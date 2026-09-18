"""Plan, run and store news searches for a set of movements.

A cached search is reused once it is settled (D11, D19). Until then a re-ingest runs it again to pick up later coverage.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from sqlalchemy.orm import Session

from app.constants.news import COST_DECIMALS
from app.constants.pipeline import NEWS_MAX_WORKERS
from app.domain import NewsSearchResult, PlannedSearch
from app.errors import ProviderError
from app.models import Company, Movement
from app.providers.news import NewsProvider
from app.repositories.articles import get_articles, upsert_articles
from app.repositories.movements import link_articles
from app.repositories.news_search_cache import get_cached_searches, save_search
from app.services.news.freshness import is_settled
from app.services.news.news_tier_strategy import NewsTierStrategy
from app.services.news.registry import TIER_PRIORITY, ordered_tiers

logger = logging.getLogger(__name__)


def plan_searches(
    movements: list[Movement], company: Company, tiers: list[NewsTierStrategy] | None = None
) -> list[PlannedSearch]:
    """One PlannedSearch per distinct (tier, scope, window). Order per movement follows its driver hint."""
    planned: dict[str, PlannedSearch] = {}
    for movement in movements:
        for strategy in ordered_tiers(movement.driver_hint, tiers):
            query = strategy.build_query(movement, company)
            if not query:
                continue
            scope = strategy.cache_scope(movement, company)
            key = f"{strategy.tier.value}:{scope}:{movement.window_start}:{movement.window_end}"
            search = planned.setdefault(
                key,
                PlannedSearch(
                    key, strategy.tier, query, movement.window_start, movement.window_end, strategy.max_results
                ),
            )
            search.movement_ids.append(movement.id)
    return list(planned.values())


def _run(provider: NewsProvider, search: PlannedSearch) -> NewsSearchResult | ProviderError:
    try:
        return provider.search(search.query, search.start, search.end, search.limit)
    except ProviderError as exc:
        return exc


def fetch_news(
    session: Session,
    provider: NewsProvider,
    movements: list[Movement],
    company: Company,
    now: datetime,
    tiers: list[NewsTierStrategy] | None = None,
) -> dict:
    """Make sure every movement has its tiers' articles linked.

    Returns counters for the job record plus `updated_movement_ids`: movements that gained at least one new article.
    """
    planned = plan_searches(movements, company, tiers)
    cached = get_cached_searches(session, [s.cache_key for s in planned])
    settled = {key for key, row in cached.items() if is_settled(_window_end(planned, key), row.fetched_at.date())}
    to_run = [s for s in planned if s.cache_key not in settled]
    stats = {
        "searches_run": 0,
        "searches_cached": len(settled),
        "searches_refreshed": 0,
        "cost_dollars": 0.0,
        "errors": [],
    }

    # Network in parallel, database on this thread only
    with ThreadPoolExecutor(max_workers=NEWS_MAX_WORKERS) as pool:
        results = list(pool.map(lambda s: _run(provider, s), to_run))

    # Start from what is cached, so a failed re-run of an unsettled search keeps the articles it already had
    article_ids_by_key = {key: row.article_ids for key, row in cached.items()}
    for search, result in zip(to_run, results, strict=True):
        if isinstance(result, ProviderError):
            logger.warning("news search failed (%s): %s", search.cache_key, result.message)
            stats["errors"].append(f"{search.cache_key}: {result.message}")
            continue
        articles = upsert_articles(session, result.hits)
        previous = article_ids_by_key.get(search.cache_key, [])
        # A re-run adds to the earlier results: coverage found on day one should not disappear on day two
        article_ids_by_key[search.cache_key] = list(dict.fromkeys([*previous, *(a.id for a in articles)]))
        save_search(session, search.cache_key, article_ids_by_key[search.cache_key], result.cost_dollars, now)
        stats["searches_run"] += 1
        stats["searches_refreshed"] += search.cache_key in cached
        stats["cost_dollars"] += result.cost_dollars or 0.0

    updated: list[int] = []
    for movement in movements:
        # Link in this movement's own tier priority: an article found by two tiers keeps the first one's label
        priority = TIER_PRIORITY[movement.driver_hint]
        mine = sorted((s for s in planned if movement.id in s.movement_ids), key=lambda s: priority.index(s.tier))
        new_links = 0
        for search in mine:
            articles = get_articles(session, article_ids_by_key.get(search.cache_key, []))
            new_links += link_articles(session, movement, articles, search.tier)
        if new_links:
            updated.append(movement.id)
    stats["cost_dollars"] = round(stats["cost_dollars"], COST_DECIMALS)
    stats["updated_movement_ids"] = updated
    return stats


def _window_end(planned: list[PlannedSearch], cache_key: str):
    return next(s.end for s in planned if s.cache_key == cache_key)
