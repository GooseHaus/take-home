from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    exa_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"

    database_url: str = "sqlite:///data/app.db"
    move_threshold_pct: float = 2.0
    max_movements_with_news: int = 25
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
