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
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings()
        db.add(s); db.commit(); db.refresh(s)
    return {
        "allow_anonymous_reporting": s.allow_anonymous_reporting,
        "allow_open_admin_registration": s.allow_open_admin_registration,
        "email_from_name": s.email_from_name,
        "email_from_address": s.email_from_address,
    }

@router.put("", dependencies=[Depends(require_role("super_admin"))])
def update_settings(payload: dict, db: Session = Depends(get_db)):
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings(); db.add(s)
    for k in ["allow_anonymous_reporting","allow_open_admin_registration","email_from_name","email_from_address"]:
        if k in payload: setattr(s, k, payload[k])
    db.commit(); db.refresh(s)
    return {"ok": True}