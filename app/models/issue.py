from sqlalchemy.orm import Mapped, mapped_column, declarative_base
from sqlalchemy import String, Text, Enum, Float
import enum, datetime

Base = declarative_base()

class IssueStatus(str, enum.Enum):
    pending = "pending"
    in_progress = "in_progress"
    resolved = "resolved"

class Issue(Base):
    __tablename__ = "issues"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    category: Mapped[str | None] = mapped_column(String(100), default=None)
    status: Mapped[IssueStatus] = mapped_column(Enum(IssueStatus), default=IssueStatus.pending)
    lat: Mapped[float | None] = mapped_column(Float, default=None)
    lng: Mapped[float | None] = mapped_column(Float, default=None)
    address: Mapped[str | None] = mapped_column(String(255), default=None)
    created_at: Mapped[datetime.datetime] = mapped_column(default=datetime.datetime.utcnow)