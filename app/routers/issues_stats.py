# app/routers/issues_stats.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from app.models.issue_activity import IssueActivity
from app.models.user import User

router = APIRouter(prefix="/issues/stats", tags=["issues:stats"])

def range_to_dt(range_key: str):
    now = datetime.utcnow()
    if range_key == "today": return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "7d": return now - timedelta(days=7)
    if range_key == "15d": return now - timedelta(days=15)
    if range_key == "30d": return now - timedelta(days=30)
    return None

@router.get("/summary")
def summary(range: str = Query("7d"), db: Session = Depends(get_db)):
    since = range_to_dt(range)
    q = db.query(Issue)
    if since:
        q = q.filter(Issue.created_at >= since)
    total = q.count()
    resolved = q.filter(Issue.status == IssueStatus.resolved).count()
    in_progress = q.filter(Issue.status == IssueStatus.in_progress).count()
    pending = q.filter(Issue.status == IssueStatus.pending).count()
    return {"total": total, "resolved": resolved, "in_progress": in_progress, "pending": pending}

@router.get("/by-type")
def by_type(range: str = Query("7d"), db: Session = Depends(get_db)):
    since = range_to_dt(range)
    q = db.query(Issue.category, func.count(Issue.id))
    if since:
        q = q.filter(Issue.created_at >= since)
    q = q.group_by(Issue.category).order_by(func.count(Issue.id).desc())
    return [{"type": c or "unknown", "count": n} for c, n in q.all()]

@router.get("/by-type-status")
def by_type_status(range: str = Query("7d"), db: Session = Depends(get_db)):
    since = range_to_dt(range)
    q = db.query(
        Issue.category,
        Issue.status,
        func.count(Issue.id).label("count")
    )
    if since:
        q = q.filter(Issue.created_at >= since)
    q = q.group_by(Issue.category, Issue.status)
    results = q.all()
    
    # Group by category
    by_cat: dict[str, dict[str, int]] = {}
    for cat, status, count in results:
        cat_name = cat or "unknown"
        if cat_name not in by_cat:
            by_cat[cat_name] = {"pending": 0, "in_progress": 0, "resolved": 0}
        status_str = status.value if hasattr(status, 'value') else str(status)
        if status_str in by_cat[cat_name]:
            by_cat[cat_name][status_str] = count
    
    return [
        {"type": cat, "pending": data["pending"], "in_progress": data["in_progress"], "resolved": data["resolved"]}
        for cat, data in sorted(by_cat.items(), key=lambda x: sum(x[1].values()), reverse=True)
    ]

@router.get("/by-state")
def by_state(range: str = Query("7d"), db: Session = Depends(get_db)):
    since = range_to_dt(range)
    q = db.query(Issue.state_code, func.count(Issue.id).label("count"))
    if since:
        q = q.filter(Issue.created_at >= since)
    q = q.filter(Issue.state_code.isnot(None)).group_by(Issue.state_code).order_by(func.count(Issue.id).desc())
    return [{"state_code": r[0], "count": r[1]} for r in q.all()]

@router.get("/top-contributors")
def top_contributors(limit: int = 10, db: Session = Depends(get_db)):
    q = (
        db.query(User.name, func.count(Issue.id))
        .join(Issue, Issue.created_by_id == User.id)
        .group_by(User.id, User.name)
        .order_by(func.count(Issue.id).desc())
        .limit(limit)
    )
    return [{"name": n or "Unknown", "count": c} for n, c in q.all()]

@router.get("/recent-activity")
def recent_activity(limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    from app.models.user import User
    activities = (
        db.query(IssueActivity, Issue, User)
        .join(Issue, Issue.id == IssueActivity.issue_id)
        .outerjoin(User, User.id == Issue.created_by_id)
        .order_by(IssueActivity.at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "issue_id": act.issue_id,
            "kind": act.kind.value if hasattr(act.kind, 'value') else str(act.kind),
            "at": act.at.isoformat() if act.at else None,
            "title": issue.title or "",
            "description": issue.description or "",
            "address": issue.address or "",
            "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
            "created_by": (user.name if user and user.name else user.email) if user else "Anonymous"
        }
        for act, issue, user in activities
    ]

@router.get("/avg-resolve-time")
def avg_resolve_time(db: Session = Depends(get_db)):
    secs = db.query(func.avg(func.extract('epoch', Issue.resolved_at - Issue.created_at))).scalar()
    return {"avg_seconds": float(secs or 0.0)}
