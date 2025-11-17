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
            IssueType.id,
            IssueType.name,
            IssueType.is_active,
            func.count(Issue.id).label("issue_count")
        )
        .outerjoin(Issue, Issue.category == IssueType.name)
        .group_by(IssueType.id, IssueType.name, IssueType.is_active)
        .order_by(IssueType.name)
        .all()
    )
    return [
        {"id": r[0], "name": r[1], "is_active": r[2], "issue_count": r[3]}
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
    
    t = IssueType(name=name, is_active=True)
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"id": t.id}

@router.put("/{type_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def update_type(type_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(IssueType).get(type_id)
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
    
    db.commit()
    db.refresh(t)
    return {"ok": True}

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
