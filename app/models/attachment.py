# File: app\models\attachment.py
# Project: improve-my-city-backend
# Auto-added for reference

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class IssueAttachment(Base):
    __tablename__ = "issue_attachments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)