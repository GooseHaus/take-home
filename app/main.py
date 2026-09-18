import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import chat, tickers
from app.config import get_settings
from app.constants.api import API_VERSION, OPENAPI_TAGS
from app.db import SessionLocal, init_db
from app.errors import AppError
from app.logging_config import configure_logging
from app.repositories.ingest_jobs import fail_interrupted_jobs

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(get_settings().log_level)
    init_db()
    with SessionLocal() as session:
        interrupted = fail_interrupted_jobs(session)
    if interrupted:
        logger.warning("closed %d ingest job(s) interrupted by a restart", interrupted)
    yield


app = FastAPI(
    title="Stock Movement Explainer",
    version=API_VERSION,
    description="Explains major daily stock price movements using company, industry and macro news.",
    openapi_tags=OPENAPI_TAGS,
    lifespan=lifespan,
)

app.include_router(tickers.router)
app.include_router(chat.router)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """The single place domain errors become HTTP responses; services never raise HTTPException."""
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/health", tags=["health"], summary="Liveness check and whether the API keys are configured")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "exa_configured": bool(settings.exa_api_key),
        "openai_configured": bool(settings.openai_api_key),
    }
