# File: app\routers\settings.py
# Project: improve-my-city-backend
# Auto-added for reference

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.app_settings import AppSettings
from app.core.security import require_role

router = APIRouter(prefix="/admin/settings", tags=["admin-settings"])

@router.get("", dependencies=[Depends(require_role("admin","super_admin"))])
def get_settings(db: Session = Depends(get_db)):
    from datetime import datetime
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings()
        db.add(s); db.commit(); db.refresh(s)
    return {
        "allow_anonymous_reporting": s.allow_anonymous_reporting,
        "require_email_verification": s.require_email_verification,
        "admin_open_registration": s.admin_open_registration,
        "email_from": s.email_from,
        "features": s.features or {},
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }

@router.put("", dependencies=[Depends(require_role("super_admin"))])
def update_settings(payload: dict, db: Session = Depends(get_db)):
    from datetime import datetime
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings(); db.add(s)
    if "allow_anonymous_reporting" in payload:
        s.allow_anonymous_reporting = bool(payload["allow_anonymous_reporting"])
    if "require_email_verification" in payload:
        s.require_email_verification = bool(payload["require_email_verification"])
    if "admin_open_registration" in payload:
        s.admin_open_registration = bool(payload["admin_open_registration"])
    if "email_from" in payload:
        s.email_from = payload["email_from"] or None
    if "features" in payload:
        s.features = payload["features"] or {}
    s.updated_at = datetime.utcnow()
    db.commit(); db.refresh(s)
    return {"ok": True}