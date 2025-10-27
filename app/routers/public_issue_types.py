# File: app/routers/public_issue_types.py

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.issue_type import IssueType

router = APIRouter(prefix="/issue-types", tags=["issue-types"])

@router.get("")
def list_public_issue_types(db: Session = Depends(get_db)):
    rows = (
        db.query(IssueType)
        .filter(IssueType.is_active.is_(True))
        .order_by(IssueType.name.asc())
        .all()
    )
    # return minimal fields the frontend needs
    return [{"id": r.id, "name": r.name, "slug": getattr(r, "slug", None)} for r in rows]