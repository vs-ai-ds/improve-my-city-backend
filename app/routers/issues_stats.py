# File: app\routers\issues_stats.py
# Project: improve-my-city-backend
# Auto-added for reference

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from sqlalchemy import func, text
from app.models.user import User

router = APIRouter(prefix="/issues/stats", tags=["issues:stats"])

def range_to_dt(range_key: str):
  now = datetime.utcnow()
  if range_key == "today": return now.replace(hour=0, minute=0, second=0, microsecond=0)
  if range_key == "7d": return now - timedelta(days=7)
  if range_key == "15d": return now - timedelta(days=15)
  if range_key == "30d": return now - timedelta(days=30)
  return None  # all time

@router.get("")
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
  from sqlalchemy import func
  q = db.query(Issue.category, func.count(Issue.id))
  if since: 
    q = q.filter(Issue.created_at >= since)
  q = q.group_by(Issue.category).order_by(func.count(Issue.id).desc())
  return [{"type": c or "unknown", "count": n} for c, n in q.all()]

@router.get("/by-state")
def by_state(range: str = Query("7d"), db: Session = Depends(get_db)):
  # if you don't have a "state" column yet, start with 'address' contains <region> or return empty for now
  return []

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
def recent_activity(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.execute(
        text("""
            select ia.issue_id, ia.kind, ia.at, i.title, i.status
            from issue_activity ia
            join issues i on i.id = ia.issue_id
            order by ia.at desc
            limit :lim
        """),
        {"lim": limit}
    ).fetchall()
    return [
        {"issue_id": r[0], "kind": r[1], "at": r[2].isoformat(), "title": r[3], "status": r[4]}
        for r in rows
    ]

@router.get("/avg-resolve-time")
def avg_resolve_time(db: Session = Depends(get_db)):
    secs = db.query(func.avg(func.extract('epoch', Issue.resolved_at - Issue.created_at))).scalar()
    return {"avg_seconds": float(secs or 0.0)}