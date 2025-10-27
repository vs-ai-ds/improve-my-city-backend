# File: app\models\region.py
# Project: improve-my-city-backend
# Auto-added for reference

# app/models/region.py
from sqlalchemy import String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class StaffRegion(Base):
    __tablename__ = "staff_regions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    state_code: Mapped[str] = mapped_column(String(3), index=True)
    __table_args__ = (UniqueConstraint("user_id","state_code", name="uq_staff_region"),)