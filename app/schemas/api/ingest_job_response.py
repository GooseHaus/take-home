from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.enums import JobStatus


class IngestJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ticker: str
    status: JobStatus
    stage: str | None
    detail: dict | None
    error: str | None
    started_at: datetime
    finished_at: datetime | None
