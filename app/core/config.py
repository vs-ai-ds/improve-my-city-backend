# File: app\core\config.py
# Project: improve-my-city-backend
# Auto-added for reference

from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    .env file should contain:
    
    Required:
    - DATABASE_URL=postgresql://user:password@host:port/database
    - JWT_SECRET=your-secret-key-here
    
    Optional (with defaults):
    - BACKEND_CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
    - FRONTEND_BASE_URL=http://localhost:5173
    - EMAIL_DOMAIN_VERIFIED=false (or true, 1, yes - Pydantic converts to bool)
    - SUPABASE_BUCKET=issue-photos
    - VAPID_SUB=mailto:noreply@example.com
    
    Optional (no defaults - will be None if not set):
    - EMAIL_PROVIDER=smtp (or resend) - default is smtp
    - SMTP_HOST=smtp.gmail.com (or your SMTP server)
    - SMTP_PORT=587 (or 465 for SSL)
    - SMTP_USERNAME=your-email@example.com
    - SMTP_PASSWORD=your-app-password
    - SMTP_USE_SSL=true (or false for SSL)
    - RESEND_API_KEY=re_xxxxx (Resend API key if using Resend)
    - EMAIL_FROM_NAME=Your App Name
    - EMAIL_FROM_ADDRESS=noreply@yourdomain.com
    - EMAIL_REDIRECT_TO=test@example.com (for testing)
    - VAPID_PRIVATE_KEY=your-vapid-private-key
    - VAPID_PUBLIC_KEY=your-vapid-public-key
    - SUPABASE_URL=https://your-project.supabase.co
    - SUPABASE_SERVICE_ROLE=your-service-role-key
    """
    database_url: str = Field(..., alias="DATABASE_URL")
    jwt_secret: str = Field(..., alias="JWT_SECRET")
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="BACKEND_CORS_ORIGINS",
    )
    
    email_provider: str = Field(default="smtp", alias="EMAIL_PROVIDER")
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(default=587, alias="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, alias="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    smtp_use_ssl: bool = Field(default=True, alias="SMTP_USE_SSL")
    resend_api_key: Optional[str] = Field(default=None, alias="RESEND_API_KEY")
    email_from_name: Optional[str] = Field(default=None, alias="EMAIL_FROM_NAME")
    email_from_address: Optional[str] = Field(default=None, alias="EMAIL_FROM_ADDRESS")
    email_redirect_to: Optional[str] = Field(default=None, alias="EMAIL_REDIRECT_TO")
    email_domain_verified: bool = Field(default=False, alias="EMAIL_DOMAIN_VERIFIED")
    frontend_base_url: str = Field(default="", alias="FRONTEND_BASE_URL")
    
    vapid_private_key: Optional[str] = Field(default=None, alias="VAPID_PRIVATE_KEY")
    vapid_public_key: Optional[str] = Field(default=None, alias="VAPID_PUBLIC_KEY")
    vapid_sub: str = Field(default="mailto:noreply@example.com", alias="VAPID_SUB")
    
    supabase_url: Optional[str] = Field(default=None, alias="SUPABASE_URL")
    supabase_service_role: Optional[str] = Field(default=None, alias="SUPABASE_SERVICE_ROLE")
    supabase_bucket: str = Field(default="issue-photos", alias="SUPABASE_BUCKET")

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