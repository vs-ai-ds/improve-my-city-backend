# File: app\models\push.py
# Project: improve-my-city-backend
# Auto-added for reference

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import ForeignKey, String
from app.db.base import Base

class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(String(500))
    p256dh: Mapped[str] = mapped_column(String(200))
    auth: Mapped[str] = mapped_column(String(100))