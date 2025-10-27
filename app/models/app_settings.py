# File: app\models\app_settings.py
# Project: improve-my-city-backend
# Auto-added for reference

from sqlalchemy import Boolean, String, DateTime, JSON, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class AppSettings(Base):
    __tablename__ = "app_settings"

    # single-row table pattern; enforce one row in code
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    allow_anonymous_reporting: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    require_email_verification: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    admin_open_registration: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    email_from: Mapped[str | None] = mapped_column(String(255), nullable=True)
    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # extra flags, e.g. {"chatbot": true}

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
