from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime

Status = Literal["pending", "in_progress", "resolved"]


class IssueCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None


class UserLite(BaseModel):
    """Lightweight user info for creator / assignee on issues."""
    id: Optional[int] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None


class IssueOut(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    status: Status

    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None

    # Extra fields used mainly by admin / analytics views
    country: Optional[str] = None
    state_code: Optional[str] = None

    created_at: datetime
    updated_at: Optional[datetime] = None
    in_progress_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    assigned_to_id: Optional[int] = None

    # Embedded objects for UI
    creator: Optional[UserLite] = None
    assigned_to: Optional[UserLite] = None

    photos: List[str] = []

    class Config:
        from_attributes = True


class IssueStatusPatch(BaseModel):
    status: Status


class PaginatedIssuesOut(BaseModel):
    items: list[IssueOut]
    total: int
    offset: int
    limit: int


class DuplicateIssueResponse(BaseModel):
    duplicate: bool = True
    existing_issue_id: int
    message: str

class IssueUpdate(BaseModel):
    assigned_to_id: Optional[int] = None