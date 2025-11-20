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
    from sqlalchemy import text, inspect
    
    # Check if auto_assign_issues column exists
    conn = db.connection()
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='app_settings' AND column_name='auto_assign_issues'
    """))
    has_auto_assign = result.fetchone() is not None
    
    if has_auto_assign:
        s = db.query(AppSettings).first()
    else:
        # Query without the missing column
        result = db.execute(text("""
            SELECT id, allow_anonymous_reporting, require_email_verification, 
                   admin_open_registration, email_from, email_from_name, features,
                   created_at, updated_at
            FROM app_settings LIMIT 1
        """)).mappings().first()
        if result:
            s = AppSettings()
            for key, value in result.items():
                if hasattr(s, key):
                    setattr(s, key, value)
        else:
            s = None
    
    if not s:
        if not has_auto_assign:
            raise HTTPException(status_code=500, detail="Database migration required. Please run: alembic upgrade head")
        s = AppSettings()
        db.add(s); db.commit(); db.refresh(s)
    return {
        "allow_anonymous_reporting": s.allow_anonymous_reporting,
        "require_email_verification": s.require_email_verification,
        "admin_open_registration": s.admin_open_registration,
        "auto_assign_issues": getattr(s, 'auto_assign_issues', False),
        "email_from": s.email_from,
        "email_from_name": s.email_from_name,
        "features": s.features or {},
        "sla_hours": getattr(s, 'sla_hours', 48),
        "sla_reminder_hours": getattr(s, 'sla_reminder_hours', None),
        "city_logo_url": getattr(s, 'city_logo_url', None),
        "support_email": getattr(s, 'support_email', None),
        "website_url": getattr(s, 'website_url', None),
        "auto_email_on_status_change": getattr(s, 'auto_email_on_status_change', True),
        "push_notifications_enabled": getattr(s, 'push_notifications_enabled', True),
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }

@router.put("", dependencies=[Depends(require_role("super_admin"))])
def update_settings(payload: dict, db: Session = Depends(get_db)):
    from datetime import datetime
    from sqlalchemy import text
    
    # Check if auto_assign_issues column exists
    conn = db.connection()
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='app_settings' AND column_name='auto_assign_issues'
    """))
    has_auto_assign = result.fetchone() is not None
    
    if has_auto_assign:
        s = db.query(AppSettings).first()
    else:
        # Query without the missing column
        result = db.execute(text("SELECT * FROM app_settings LIMIT 1")).mappings().first()
        if result:
            s = AppSettings()
            for key, value in result.items():
                if hasattr(s, key) and key != 'auto_assign_issues':
                    setattr(s, key, value)
        else:
            s = None
    
    if not s:
        # Can't create new row if column doesn't exist - migration needed
        if not has_auto_assign:
            raise HTTPException(status_code=500, detail="Database migration required. Please run: alembic upgrade head")
        s = AppSettings(); db.add(s)
    if "allow_anonymous_reporting" in payload:
        s.allow_anonymous_reporting = bool(payload["allow_anonymous_reporting"])
    if "require_email_verification" in payload:
        s.require_email_verification = bool(payload["require_email_verification"])
    if "admin_open_registration" in payload:
        s.admin_open_registration = bool(payload["admin_open_registration"])
    if "auto_assign_issues" in payload:
        if hasattr(s, 'auto_assign_issues'):
            s.auto_assign_issues = bool(payload["auto_assign_issues"])
    if "email_from" in payload:
        s.email_from = payload["email_from"] or None
    if "email_from_name" in payload:
        s.email_from_name = payload["email_from_name"] or None
    if "features" in payload:
        s.features = payload["features"] or {}
    if "sla_hours" in payload:
        s.sla_hours = int(payload["sla_hours"]) if payload["sla_hours"] is not None else 48
    if "sla_reminder_hours" in payload:
        s.sla_reminder_hours = int(payload["sla_reminder_hours"]) if payload["sla_reminder_hours"] is not None else None
    if "city_logo_url" in payload:
        s.city_logo_url = payload["city_logo_url"] or None
    if "support_email" in payload:
        s.support_email = payload["support_email"] or None
    if "website_url" in payload:
        s.website_url = payload["website_url"] or None
    if "auto_email_on_status_change" in payload:
        s.auto_email_on_status_change = bool(payload["auto_email_on_status_change"])
    if "push_notifications_enabled" in payload:
        s.push_notifications_enabled = bool(payload["push_notifications_enabled"])
    s.updated_at = datetime.utcnow()
    db.commit(); db.refresh(s)
    return {"ok": True}