# File: app\routers\issue_types.py
# Project: improve-my-city-backend
# Auto-added for reference

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, outerjoin
from typing import List
from app.db.session import get_db
from app.models.issue_type import IssueType
from app.models.issue import Issue
from app.core.security import require_role

router = APIRouter(prefix="/admin/issue-types", tags=["issue-types"])

@router.get("", response_model=List[dict])
def list_types(db: Session = Depends(get_db)):
    results = (
        db.query(
            IssueType,
            func.count(Issue.id).label("issue_count")
        )
        .outerjoin(Issue, Issue.category == IssueType.name)
        .group_by(IssueType.id)
        .order_by(IssueType.display_order, IssueType.name)
        .all()
    )
    return [
        {
            "id": r[0].id,
            "name": r[0].name,
            "is_active": r[0].is_active,
            "issue_count": r[1],
            "description": getattr(r[0], 'description', None) or "",
            "color": getattr(r[0], 'color', None) or "#6366f1",
            "display_order": getattr(r[0], 'display_order', None) or 0
        }
        for r in results
    ]


@router.post("", dependencies=[Depends(require_role("admin","super_admin"))])
def create_type(payload: dict, db: Session = Depends(get_db)):
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="name required")
    if len(name) < 3:
        raise HTTPException(status_code=400, detail="name must be at least 3 characters")
    if len(name) > 40:
        raise HTTPException(status_code=400, detail="name must be at most 40 characters")
    
    existing = db.query(IssueType).filter(func.lower(IssueType.name) == func.lower(name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Type already exists")
    
    max_order = db.query(func.max(IssueType.display_order)).scalar() or 0
    t = IssueType(
        name=name,
        is_active=True,
        description=payload.get("description", "").strip() or None,
        color=payload.get("color") or "#6366f1",
        display_order=max_order + 1
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}

@router.put("/{type_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def update_type(type_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(IssueType).filter(IssueType.id == type_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="not found")
    
    if "name" in payload:
        name = (payload["name"] or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        if len(name) < 3:
            raise HTTPException(status_code=400, detail="name must be at least 3 characters")
        if len(name) > 40:
            raise HTTPException(status_code=400, detail="name must be at most 40 characters")
        
        existing = db.query(IssueType).filter(
            func.lower(IssueType.name) == func.lower(name),
            IssueType.id != type_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Type already exists")
        
        t.name = name
    
    if "is_active" in payload:
        t.is_active = bool(payload["is_active"])
    
    if "description" in payload:
        t.description = (payload["description"] or "").strip() or None
    
    if "color" in payload:
        t.color = payload["color"] or "#6366f1"
    
    if "display_order" in payload:
        t.display_order = int(payload["display_order"]) if payload["display_order"] is not None else 0
    
    db.commit()
    db.refresh(t)
    return {"ok": True}

@router.post("/reorder", dependencies=[Depends(require_role("admin","super_admin"))])
def reorder_types(payload: dict, db: Session = Depends(get_db)):
    order_map = payload.get("order", {})
    if not isinstance(order_map, dict):
        raise HTTPException(status_code=400, detail="order must be a dict mapping id to display_order")
    
    for type_id_str, display_order in order_map.items():
        try:
            type_id = int(type_id_str)
            display_order_int = int(display_order)
            t = db.query(IssueType).filter(IssueType.id == type_id).first()
            if t:
                t.display_order = display_order_int
        except (ValueError, TypeError):
            continue
    
    db.commit()
    return {"ok": True}

@router.get("/{type_id}/stats")
def get_type_stats(type_id: int, db: Session = Depends(get_db)):
    t = db.query(IssueType).get(type_id)
    if not t:
        raise HTTPException(status_code=404, detail="not found")
    
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    last_7d = now - timedelta(days=7)
    
    total_count = db.query(Issue).filter(Issue.category == t.name).count()
    last_7d_count = db.query(Issue).filter(
        Issue.category == t.name,
        Issue.created_at >= last_7d
    ).count()
    
    resolved_issues = db.query(Issue).filter(
        Issue.category == t.name,
        Issue.status == "resolved"
    ).all()
    
    avg_resolution_hours = None
    if resolved_issues:
        total_hours = 0
        count = 0
        for issue in resolved_issues:
            if issue.created_at and issue.resolved_at:
                delta = issue.resolved_at - issue.created_at
                total_hours += delta.total_seconds() / 3600
                count += 1
        if count > 0:
            avg_resolution_hours = total_hours / count
    
    return {
        "total_count": total_count,
        "last_7d_count": last_7d_count,
        "avg_resolution_hours": avg_resolution_hours
    }

@router.delete("/{type_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def delete_type(type_id: int, db: Session = Depends(get_db)):
    from app.models.issue import Issue
    t = db.query(IssueType).get(type_id)
    if not t: raise HTTPException(status_code=404, detail="not found")
    # Check if any issues use this type
    issue_count = db.query(Issue).filter(Issue.category == t.name).count()
    if issue_count > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete: {issue_count} issue(s) use this type")
    db.delete(t)
    db.commit()
    return {"ok": True}
