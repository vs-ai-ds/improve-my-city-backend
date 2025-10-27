# File: app/models/issue.py
from __future__ import annotations
from enum import Enum as PyEnum
from sqlalchemy import String, Float, Enum, Integer, DateTime, ForeignKey, func, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class IssueStatus(PyEnum):
    pending = "pending"
    in_progress = "in_progress"
    resolved = "resolved"

class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), index=True, nullable=True)
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), default=IssueStatus.pending, index=True)

    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lng: Mapped[float | None] = mapped_column(Float, nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    country: Mapped[str | None] = mapped_column(String(2), index=True, nullable=True)
    state_code: Mapped[str | None] = mapped_column(String(3), index=True, nullable=True)

    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    
    in_progress_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True))

Index("ix_issues_lat_lng", Issue.lat, Issue.lng)