# app/routers/issues_stats.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from sqlalchemy import func
from typing import Optional
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
    if range_key == "90d": return now - timedelta(days=90)
    if range_key == "year": return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    if range_key == "all" or range_key == "all_time": return None
    return None

def apply_filters_to_query(q, status: Optional[str] = None, category: Optional[str] = None, 
                          state_code: Optional[str] = None, mine_only: Optional[int] = None,
                          user_id: Optional[int] = None):
    if status and status != "all":
        try:
            status_enum = IssueStatus[status]
            q = q.filter(Issue.status == status_enum)
        except (KeyError, ValueError):
            pass
    if category and category != "all":
        q = q.filter(Issue.category == category)
    if state_code and state_code != "all":
        q = q.filter(Issue.state_code == state_code)
    if mine_only and user_id:
        q = q.filter(Issue.created_by_id == user_id)
    return q

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
def by_type(
    range: str = Query("7d"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    state_code: Optional[str] = Query(None),
    mine_only: Optional[int] = Query(None, ge=0, le=1),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    q = db.query(Issue.category, func.count(Issue.id))
    if since:
        q = q.filter(Issue.created_at >= since)
    q = apply_filters_to_query(q, status, category, state_code, mine_only, user_id)
    q = q.group_by(Issue.category).order_by(func.count(Issue.id).desc())
    return [{"type": c or "unknown", "count": n} for c, n in q.all()]

@router.get("/by-type-status")
def by_type_status(
    range: str = Query("7d"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    state_code: Optional[str] = Query(None),
    mine_only: Optional[int] = Query(None, ge=0, le=1),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    q = db.query(
        Issue.category,
        Issue.status,
        func.count(Issue.id).label("count")
    )
    if since:
        q = q.filter(Issue.created_at >= since)
    q = apply_filters_to_query(q, status, category, state_code, mine_only, user_id)
    q = q.group_by(Issue.category, Issue.status)
    results = q.all()
    
    by_cat: dict[str, dict[str, int]] = {}
    for cat, status_obj, count in results:
        cat_name = cat or "unknown"
        if cat_name not in by_cat:
            by_cat[cat_name] = {"pending": 0, "in_progress": 0, "resolved": 0}
        status_str = status_obj.value if hasattr(status_obj, 'value') else str(status_obj)
        if status_str in by_cat[cat_name]:
            by_cat[cat_name][status_str] = count
    
    return [
        {"type": cat, "pending": data["pending"], "in_progress": data["in_progress"], "resolved": data["resolved"]}
        for cat, data in sorted(by_cat.items(), key=lambda x: sum(x[1].values()), reverse=True)
    ]

@router.get("/by-state")
def by_state(
    range: str = Query("7d"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    state_code: Optional[str] = Query(None),
    mine_only: Optional[int] = Query(None, ge=0, le=1),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    q = db.query(Issue.state_code, func.count(Issue.id).label("count"))
    if since:
        q = q.filter(Issue.created_at >= since)
    q = apply_filters_to_query(q, status, category, state_code, mine_only, user_id)
    q = q.filter(Issue.state_code.isnot(None)).group_by(Issue.state_code).order_by(func.count(Issue.id).desc())
    return [{"state_code": r[0], "count": r[1]} for r in q.all()]

@router.get("/by-state-status")
def by_state_status(
    range: str = Query("7d"),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    state_code: Optional[str] = Query(None),
    mine_only: Optional[int] = Query(None, ge=0, le=1),
    user_id: Optional[int] = Query(None),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    q = db.query(
        Issue.state_code,
        Issue.status,
        func.count(Issue.id).label("count")
    )
    if since:
        q = q.filter(Issue.created_at >= since)
    q = apply_filters_to_query(q, status, category, state_code, mine_only, user_id)
    q = q.filter(Issue.state_code.isnot(None)).group_by(Issue.state_code, Issue.status)
    results = q.all()
    
    by_state: dict[str, dict[str, int]] = {}
    for state, status_obj, count in results:
        state_name = state or "unknown"
        if state_name not in by_state:
            by_state[state_name] = {"pending": 0, "in_progress": 0, "resolved": 0}
        status_str = status_obj.value if hasattr(status_obj, 'value') else str(status_obj)
        if status_str in by_state[state_name]:
            by_state[state_name][status_str] = count
    
    return [
        {"state_code": state, "pending": data["pending"], "in_progress": data["in_progress"], "resolved": data["resolved"]}
        for state, data in sorted(by_state.items(), key=lambda x: sum(x[1].values()), reverse=True)
    ]

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
    from sqlalchemy.orm import aliased
    Creator = aliased(User)
    Assigned = aliased(User)
    activities = (
        db.query(IssueActivity, Issue, Creator, Assigned)
        .join(Issue, Issue.id == IssueActivity.issue_id)
        .outerjoin(Creator, Creator.id == Issue.created_by_id)
        .outerjoin(Assigned, Assigned.id == Issue.assigned_to_id)
        .order_by(IssueActivity.at.desc())
        .limit(limit)
        .all()
    )
    result = []
    for act, issue, creator, assigned in activities:
        item = {
            "issue_id": act.issue_id,
            "kind": act.kind.value if hasattr(act.kind, 'value') else str(act.kind),
            "at": act.at.isoformat() if act.at else None,
            "title": issue.title or "",
            "description": issue.description or "",
            "address": issue.address or "",
            "category": issue.category or "",
            "resolved_at": issue.resolved_at.isoformat() if issue.resolved_at else None,
            "created_by": (creator.name if creator and creator.name else creator.email) if creator else "Anonymous",
            "assigned_to_name": (assigned.name if assigned and assigned.name else assigned.email) if assigned else None,
            "in_progress_at": issue.in_progress_at.isoformat() if issue.in_progress_at else None,
        }
        result.append(item)
    return result

@router.get("/avg-resolve-time")
def avg_resolve_time(db: Session = Depends(get_db)):
    secs = db.query(func.avg(func.extract('epoch', Issue.resolved_at - Issue.created_at))).scalar()
    return {"avg_seconds": float(secs or 0.0)}

@router.get("/trends/daily")
def daily_trends(
    range: str = Query("30d"),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    q = db.query(
        func.date(Issue.created_at).label("date"),
        func.count(Issue.id).label("count")
    )
    if since:
        q = q.filter(Issue.created_at >= since)
    q = q.group_by(func.date(Issue.created_at)).order_by(func.date(Issue.created_at))
    results = q.all()
    return [{"date": str(r[0]), "count": r[1]} for r in results]

@router.get("/trends/resolution-time")
def resolution_time_trend(
    range: str = Query("30d"),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    q = db.query(
        func.date(Issue.resolved_at).label("date"),
        func.avg(func.extract('epoch', Issue.resolved_at - Issue.created_at)).label("avg_seconds")
    ).filter(Issue.status == IssueStatus.resolved, Issue.resolved_at.isnot(None))
    if since:
        q = q.filter(Issue.resolved_at >= since)
    q = q.group_by(func.date(Issue.resolved_at)).order_by(func.date(Issue.resolved_at))
    results = q.all()
    return [{"date": str(r[0]), "avg_seconds": float(r[1] or 0)} for r in results]

@router.get("/sla")
def sla_metrics(
    range: str = Query("30d"),
    db: Session = Depends(get_db)
):
    since = range_to_dt(range)
    from sqlalchemy import and_, or_
    
    q = db.query(Issue).filter(
        Issue.status == IssueStatus.resolved,
        Issue.resolved_at.isnot(None)
    )
    if since:
        q = q.filter(Issue.resolved_at >= since)
    
    resolved_issues = q.all()
    total_resolved = len(resolved_issues)
    
    if total_resolved == 0:
        return {
            "avg_response_time_seconds": 0,
            "avg_resolution_time_seconds": 0,
            "within_sla_percentage": 0,
            "total_resolved": 0
        }
    
    response_times = []
    resolution_times = []
    within_sla = 0
    sla_hours = 48
    
    for issue in resolved_issues:
        if hasattr(issue, 'in_progress_at') and issue.in_progress_at:
            try:
                response_secs = (issue.in_progress_at - issue.created_at).total_seconds()
                if response_secs > 0:
                    response_times.append(response_secs)
            except (TypeError, AttributeError):
                pass
        
        if issue.resolved_at and issue.created_at:
            try:
                resolution_secs = (issue.resolved_at - issue.created_at).total_seconds()
                if resolution_secs > 0:
                    resolution_times.append(resolution_secs)
                    if resolution_secs <= (sla_hours * 3600):
                        within_sla += 1
            except (TypeError, AttributeError):
                pass
    
    avg_response = sum(response_times) / len(response_times) if response_times else 0
    avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    within_sla_pct = (within_sla / len(resolution_times) * 100) if resolution_times else 0
    
    return {
        "avg_response_time_seconds": float(avg_response),
        "avg_resolution_time_seconds": float(avg_resolution),
        "within_sla_percentage": float(within_sla_pct),
        "total_resolved": total_resolved
    }
