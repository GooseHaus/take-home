from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import IngestStage, JobStatus
from app.models import IngestJob
from app.models.base import utcnow

ACTIVE_STATUSES = (JobStatus.PENDING, JobStatus.RUNNING)
INTERRUPTED_MESSAGE = "The server stopped before this ingest finished. Post the ingest again; finished work is kept."


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


def fail_interrupted_jobs(session: Session) -> int:
    """Close jobs left pending or running by a previous process.

    Jobs run inside the API process (D7), so at startup nothing can still be working on them. Left open they would
    block every later ingest of the same ticker, because an active job is returned instead of starting a new one.
    """
    jobs = list(session.scalars(select(IngestJob).where(IngestJob.status.in_(ACTIVE_STATUSES))))
    for job in jobs:
        job.status = JobStatus.FAILED
        job.error = INTERRUPTED_MESSAGE
        job.finished_at = utcnow()
    session.commit()
    return len(jobs)


def analysed_period(session: Session, ticker: str) -> tuple[date, date] | None:
    """The span covered by the ticker's finished ingests, or None if there are none.

    Prices are stored from well before this (warm-up history for the volatility stats), so responses use this span
    to show only the period that was actually analysed.
    """
    jobs = session.scalars(select(IngestJob).where(IngestJob.ticker == ticker, IngestJob.status == JobStatus.DONE))
    spans = [
        (date.fromisoformat(params["start"]), date.fromisoformat(params["end"]))
        for job in jobs
        if (params := (job.detail or {}).get("params")) and params.get("start") and params.get("end")
    ]
    if not spans:
        return None
    return min(start for start, _ in spans), max(end for _, end in spans)
