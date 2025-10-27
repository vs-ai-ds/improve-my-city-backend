# File: app\routers\issue_types.py
# Project: improve-my-city-backend
# Auto-added for reference

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db.session import get_db
from app.models.issue_type import IssueType
from app.core.security import require_role

router = APIRouter(prefix="/admin/issue-types", tags=["issue-types"])

@router.get("", response_model=List[dict])
def list_types(db: Session = Depends(get_db)):
    return [{"id": t.id, "name": t.name, "is_active": t.is_active} for t in db.query(IssueType).order_by(IssueType.name)]


@router.post("", dependencies=[Depends(require_role("admin","super_admin"))])
def create_type(payload: dict, db: Session = Depends(get_db)):
    name = payload.get("name")
    if not name: raise HTTPException(status_code=400, detail="name required")
    if db.query(IssueType).filter(IssueType.name == name).first():
        raise HTTPException(status_code=400, detail="exists")
    t = IssueType(name=name, is_active=True); db.add(t); db.commit(); db.refresh(t)
    return {"id": t.id}

@router.put("/{type_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def update_type(type_id: int, payload: dict, db: Session = Depends(get_db)):
    t = db.query(IssueType).get(type_id)
    if not t: raise HTTPException(status_code=404, detail="not found")
    if "name" in payload: t.name = payload["name"]
    if "is_active" in payload: t.is_active = bool(payload["is_active"])
    db.commit(); db.refresh(t)
    return {"ok": True}
