"""The ingest pipeline (D1, D7): prices -> movements -> news -> explanations, with job progress.

Idempotent per movement: anything already explained is skipped, and cached searches are never re-run, so re-posting an
ingest after a crash (or to extend the date range) only pays for what is new.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from app.constants.pipeline import LLM_MAX_WORKERS, MAX_ERRORS_RECORDED
from app.enums import IngestStage
from app.errors import AppError, ProviderError
from app.models import Company, IngestJob, Movement
from app.providers.llm import LLMClient
from app.providers.market_data import MarketDataProvider
from app.providers.news import NewsProvider
from app.repositories.explanations import save_explanation
from app.repositories.ingest_jobs import finish_job, set_stage
from app.repositories.movements import upsert_movements
from app.repositories.prices import load_price_frame
from app.schemas.llm import ExplanationOutput
from app.services.explain import build_user_prompt, prompt_articles, request_explanation
from app.services.movements import detect_movements
from app.services.news.search import fetch_news
from app.services.price_ingest import benchmark_tickers, ingest_prices

logger = logging.getLogger(__name__)


def select_for_explanation(movements: list[Movement], limit: int) -> list[Movement]:
    """Cost guard: only the `limit` largest moves (by absolute size) get paid news searches and LLM calls."""
    largest = sorted(movements, key=lambda m: abs(m.pct_change), reverse=True)[:limit]
    return [m for m in largest if m.explanation is None]


def detect_and_store(
    session: Session, company: Company, start: date, end: date, threshold_pct: float
) -> list[Movement]:
    frames = [load_price_frame(session, t) for t in (company.ticker, *benchmark_tickers(company))]
    prices, market = frames[0], frames[1]
    sector = frames[2] if len(frames) > 2 else None
    detected = detect_movements(prices, market, sector, threshold_pct, start, end)
    return upsert_movements(session, company.ticker, detected)


def _request(llm: LLMClient, prompt: str) -> ExplanationOutput | ProviderError:
    try:
        return request_explanation(llm, prompt)
    except ProviderError as exc:
        return exc


def explain_movements(session: Session, llm: LLMClient, movements: list[Movement], company: Company) -> dict:
    """Prompts are built and results saved on this thread; only the LLM calls fan out."""
    prompts = [build_user_prompt(m, company, prompt_articles(session, m)) for m in movements]
    with ThreadPoolExecutor(max_workers=LLM_MAX_WORKERS) as pool:
        outputs = list(pool.map(lambda p: _request(llm, p), prompts))

    stats = {"explained": 0, "errors": []}
    for movement, output in zip(movements, outputs, strict=True):
        if isinstance(output, ProviderError):
            # One bad call marks that movement only; it stays unexplained and is retried on the next ingest
            logger.warning("explanation failed for %s %s: %s", movement.ticker, movement.date, output.message)
            stats["errors"].append(f"{movement.date}: {output.message}")
            continue
        save_explanation(session, movement, output, llm.model)
        stats["explained"] += 1
    return stats


def run_ingest(
    session_factory: sessionmaker,
    job_id: int,
    ticker: str,
    start: date,
    end: date,
    threshold_pct: float,
    max_movements_with_news: int,
    market_data: MarketDataProvider,
    news: NewsProvider,
    llm: LLMClient,
) -> None:
    """Entry point for the background task. Owns its session; never raises (failures land on the job row)."""
    with session_factory() as session:
        job = session.get(IngestJob, job_id)
        try:
            set_stage(session, job, IngestStage.PRICES)
            company = ingest_prices(session, market_data, ticker, start, end)

            set_stage(session, job, IngestStage.MOVEMENTS)
            movements = detect_and_store(session, company, start, end, threshold_pct)
            selected = select_for_explanation(movements, max_movements_with_news)

            set_stage(session, job, IngestStage.NEWS, movements=len(movements), selected=len(selected))
            news_stats = fetch_news(session, news, selected, company)

            set_stage(session, job, IngestStage.EXPLANATIONS, news=_without_errors(news_stats))
            explain_stats = explain_movements(session, llm, selected, company)

            errors = (news_stats["errors"] + explain_stats["errors"])[:MAX_ERRORS_RECORDED]
            finish_job(session, job, explained=explain_stats["explained"], errors=errors)
            logger.info(
                "ingest %s done: %d movements, %d explained", ticker, len(movements), explain_stats["explained"]
            )
        except AppError as exc:
            session.rollback()
            finish_job(session, job, error=exc.message)
        except Exception as exc:
            logger.exception("ingest %s crashed", ticker)
            session.rollback()
            finish_job(session, job, error=f"{type(exc).__name__}: {exc}")


def _without_errors(stats: dict) -> dict:
    return {k: v for k, v in stats.items() if k != "errors"}
