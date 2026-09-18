from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Stock Movement Explainer",
    description="Explains major daily stock price movements using company, industry and macro news.",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "exa_configured": bool(settings.exa_api_key),
        "openai_configured": bool(settings.openai_api_key),
    }
