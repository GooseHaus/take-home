from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api import tickers
from app.config import get_settings
from app.db import init_db
from app.errors import AppError
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging(get_settings().log_level)
    init_db()
    yield


app = FastAPI(
    title="Stock Movement Explainer",
    description="Explains major daily stock price movements using company, industry and macro news.",
    lifespan=lifespan,
)

app.include_router(tickers.router)


@app.exception_handler(AppError)
async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    """The single place domain errors become HTTP responses; services never raise HTTPException."""
    return JSONResponse(status_code=exc.status_code, content={"error": {"code": exc.code, "message": exc.message}})


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "exa_configured": bool(settings.exa_api_key),
        "openai_configured": bool(settings.openai_api_key),
    }
