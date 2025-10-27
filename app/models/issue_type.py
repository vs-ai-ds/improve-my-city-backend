# File: app\models\issue_type.py
# Project: improve-my-city-backend
# Auto-added for reference

from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class IssueType(Base):
    __tablename__ = "issue_types"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")