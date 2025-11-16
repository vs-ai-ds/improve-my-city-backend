# File: app/models/issue_activity.py
from __future__ import annotations
from enum import Enum as PyEnum
from sqlalchemy import String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class ActivityKind(PyEnum):
    created = "created"
    in_progress = "in_progress"
    resolved = "resolved"

class IssueActivity(Base):
    __tablename__ = "issue_activity"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True, nullable=False)
    kind: Mapped[ActivityKind] = mapped_column(String(20), nullable=False)
    at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

