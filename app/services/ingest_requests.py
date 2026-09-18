"""Turn an ingest request into a job row + resolved parameters. The pipeline runs the job."""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.config import Settings
from app.constants.market import DEFAULT_LOOKBACK_DAYS
from app.domain import ResolvedIngest
from app.models import IngestJob
from app.repositories.ingest_jobs import create_job, get_active_job
from app.schemas.api import IngestRequest


def resolve(request: IngestRequest, settings: Settings, today: date | None = None) -> ResolvedIngest:
    end = request.end or today or date.today()
    start = request.start or end - timedelta(days=request.lookback_days or DEFAULT_LOOKBACK_DAYS)
    return ResolvedIngest(
        start=start,
        end=end,
        threshold_pct=request.threshold_pct or settings.move_threshold_pct,
        max_movements=request.max_movements or settings.max_movements_with_news,
        refresh=request.refresh,
    )


def open_job(session: Session, ticker: str, resolved: ResolvedIngest) -> tuple[IngestJob, bool]:
    """(job, created). An ingest already in flight for the ticker is returned instead of starting a second one."""
    active = get_active_job(session, ticker)
    if active:
        return active, False
    job = create_job(session, ticker, resolved.as_params())
    session.commit()
    return job, True
