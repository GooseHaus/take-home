from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import IngestStage, JobStatus
from app.models import IngestJob
from app.models.base import utcnow

ACTIVE_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING)


def create_job(session: Session, ticker: str, params: dict) -> IngestJob:
    job = IngestJob(ticker=ticker, status=JobStatus.PENDING, detail={"params": params})
    session.add(job)
    session.flush()
    return job


def get_active_job(session: Session, ticker: str) -> IngestJob | None:
    return session.scalars(
        select(IngestJob).where(IngestJob.ticker == ticker, IngestJob.status.in_(ACTIVE_STATUSES))
    ).first()


def get_latest_job(session: Session, ticker: str) -> IngestJob | None:
    return session.scalars(select(IngestJob).where(IngestJob.ticker == ticker).order_by(IngestJob.id.desc())).first()


def set_stage(session: Session, job: IngestJob, stage: IngestStage, **detail) -> None:
    """Record progress and commit immediately so the status endpoint sees it mid-run."""
    job.status = JobStatus.RUNNING
    job.stage = stage.value
    job.detail = {**(job.detail or {}), **detail}
    session.commit()


def finish_job(session: Session, job: IngestJob, error: str | None = None, **detail) -> None:
    job.status = JobStatus.FAILED if error else JobStatus.DONE
    if not error:
        job.stage = IngestStage.COMPLETE.value
    job.error = error
    job.detail = {**(job.detail or {}), **detail}
    job.finished_at = utcnow()
    session.commit()
