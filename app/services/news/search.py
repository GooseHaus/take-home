"""Plan, run and store news searches for a set of movements. Cached searches are never repeated (D11)."""

import logging
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.constants.news import COST_DECIMALS, RESULTS_PER_SEARCH
from app.constants.pipeline import NEWS_MAX_WORKERS
from app.domain import NewsSearchResult, PlannedSearch
from app.errors import ProviderError
from app.models import Company, Movement
from app.providers.news import NewsProvider
from app.repositories.articles import get_articles, upsert_articles
from app.repositories.movements import link_articles
from app.repositories.news_search_cache import get_cached_searches, save_search
from app.services.news.news_tier_strategy import NewsTierStrategy
from app.services.news.registry import ordered_tiers

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
                key, PlannedSearch(key, strategy.tier, query, movement.window_start, movement.window_end)
            )
            search.movement_ids.append(movement.id)
    return list(planned.values())


def _run(provider: NewsProvider, search: PlannedSearch) -> NewsSearchResult | ProviderError:
    try:
        return provider.search(search.query, search.start, search.end, RESULTS_PER_SEARCH)
    except ProviderError as exc:
        return exc


def fetch_news(
    session: Session,
    provider: NewsProvider,
    movements: list[Movement],
    company: Company,
    tiers: list[NewsTierStrategy] | None = None,
) -> dict:
    """Ensure every movement has its tiers' articles linked. Returns counters for the job record."""
    planned = plan_searches(movements, company, tiers)
    cached = get_cached_searches(session, [s.cache_key for s in planned])
    to_run = [s for s in planned if s.cache_key not in cached]
    stats = {"searches_run": 0, "searches_cached": len(planned) - len(to_run), "cost_dollars": 0.0, "errors": []}

    # Network in parallel, database on this thread only
    with ThreadPoolExecutor(max_workers=NEWS_MAX_WORKERS) as pool:
        results = list(pool.map(lambda s: _run(provider, s), to_run))

    article_ids_by_key = {key: row.article_ids for key, row in cached.items()}
    for search, result in zip(to_run, results, strict=True):
        if isinstance(result, ProviderError):
            logger.warning("news search failed (%s): %s", search.cache_key, result.message)
            stats["errors"].append(f"{search.cache_key}: {result.message}")
            continue
        articles = upsert_articles(session, result.hits)
        article_ids_by_key[search.cache_key] = [a.id for a in articles]
        save_search(session, search.cache_key, article_ids_by_key[search.cache_key], result.cost_dollars)
        stats["searches_run"] += 1
        stats["cost_dollars"] += result.cost_dollars or 0.0

    by_id = {m.id: m for m in movements}
    for search in planned:  # planned order == tier priority, so the first tier to find an article labels it
        articles = get_articles(session, article_ids_by_key.get(search.cache_key, []))
        for movement_id in search.movement_ids:
            link_articles(session, by_id[movement_id], articles, search.tier)
    stats["cost_dollars"] = round(stats["cost_dollars"], COST_DECIMALS)
    return stats
