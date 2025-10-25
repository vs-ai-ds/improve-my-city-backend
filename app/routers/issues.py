from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from app.schemas.issue import IssueCreate, IssueOut

router = APIRouter(prefix="/issues", tags=["issues"])

@router.post("", response_model=IssueOut)
def create_issue(payload: IssueCreate, db: Session = Depends(get_db)):
    obj = Issue(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        lat=payload.lat,
        lng=payload.lng,
        address=payload.address,
        status=IssueStatus.pending,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

@router.get("", response_model=List[IssueOut])
def list_issues(
    db: Session = Depends(get_db),
    status: Optional[IssueStatus] = Query(default=None),
    category: Optional[str] = Query(default=None),
):
    q = db.query(Issue)
    if status:
        q = q.filter(Issue.status == status)
    if category:
        q = q.filter(Issue.category == category)
    q = q.order_by(Issue.created_at.desc())
    return q.all()