# app/core/config.py
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    # Pydantic v2 settings config
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()

def cors_origins_list() -> List[str]:
    return [o.strip() for o in settings.BACKEND_CORS_ORIGINS.split(",") if o.strip()]