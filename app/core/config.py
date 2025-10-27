# File: app\core\config.py
# Project: improve-my-city-backend
# Auto-added for reference

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # env vars (with aliases) — read from process + .env
    database_url: str = Field(..., alias="DATABASE_URL")
    jwt_secret: str = Field(..., alias="JWT_SECRET")  # <-- IMPORTANT
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="BACKEND_CORS_ORIGINS",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

def cors_origins_list() -> List[str]:
    raw = settings.backend_cors_origins or ""
    return [x.strip().rstrip("/") for x in raw.split(",") if x.strip()]

settings = Settings()