# File: app\models\user.py
# Project: improve-my-city-backend
# Auto-added for reference

from __future__ import annotations
from enum import Enum as PyEnum
from sqlalchemy import String, Boolean, DateTime, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from datetime import datetime

class UserRole(PyEnum):
    super_admin = "super_admin"
    admin = "admin"
    staff = "staff"
    citizen = "citizen"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    name : Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.citizen)
    created_at: Mapped["DateTime"] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped["DateTime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verify_code: Mapped[str | None] = mapped_column(String(8), nullable=True)
    email_verify_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)

    # relationships (optional; add backrefs only if you use them)
    # reported_issues = relationship("Issue", back_populates="created_by", foreign_keys="Issue.created_by_id")
    # assigned_issues = relationship("Issue", back_populates="assigned_to", foreign_keys="Issue.assigned_to_id")