from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime

Status = Literal["pending", "in_progress", "resolved"]

class IssueCreate(BaseModel):
    title: str = Field(min_length=3, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    address: Optional[str] = None

class IssueOut(BaseModel):
    id: int
    title: str
    description: Optional[str]
    category: Optional[str]
    status: Status
    lat: Optional[float]
    lng: Optional[float]
    address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True