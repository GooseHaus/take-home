from pydantic import BaseModel

from app.schemas.api.error_body import ErrorBody


class ErrorResponse(BaseModel):
    """Body of every error raised by the application (see `AppError`). Request validation errors use FastAPI's
    standard 422 body instead."""

    error: ErrorBody
