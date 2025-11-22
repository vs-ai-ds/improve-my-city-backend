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
    
    # Use raw SQL to check which columns exist and query only those
    conn = db.connection()
    result = conn.execute(text("""
        SELECT column_name FROM information_schema.columns 
        WHERE table_name='app_settings'
    """))
    existing_columns = {row[0] for row in result}
    
    # Build query with only existing columns
    select_cols = []
    if 'id' in existing_columns:
        select_cols.append('id')
    if 'allow_anonymous_reporting' in existing_columns:
        select_cols.append('allow_anonymous_reporting')
    if 'require_email_verification' in existing_columns:
        select_cols.append('require_email_verification')
    if 'auto_assign_issues' in existing_columns:
        select_cols.append('auto_assign_issues')
    if 'features' in existing_columns:
        select_cols.append('features')
    if 'sla_hours' in existing_columns:
        select_cols.append('sla_hours')
    if 'sla_reminder_hours' in existing_columns:
        select_cols.append('sla_reminder_hours')
    if 'city_logo_url' in existing_columns:
        select_cols.append('city_logo_url')
    if 'support_email' in existing_columns:
        select_cols.append('support_email')
    if 'website_url' in existing_columns:
        select_cols.append('website_url')
    if 'auto_email_on_status_change' in existing_columns:
        select_cols.append('auto_email_on_status_change')
    if 'push_notifications_enabled' in existing_columns:
        select_cols.append('push_notifications_enabled')
    if 'created_at' in existing_columns:
        select_cols.append('created_at')
    if 'updated_at' in existing_columns:
        select_cols.append('updated_at')
    
    if not select_cols:
        raise HTTPException(status_code=500, detail="Database migration required. Please run: alembic upgrade head")
    
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings()
        db.add(s)
        db.commit()
        db.refresh(s)
    
    return {
        "allow_anonymous_reporting": getattr(s, 'allow_anonymous_reporting', False),
        "require_email_verification": getattr(s, 'require_email_verification', True),
        "auto_assign_issues": getattr(s, 'auto_assign_issues', False),
        "features": getattr(s, 'features', {}) or {},
        "sla_hours": getattr(s, 'sla_hours', 48),
        "sla_reminder_hours": getattr(s, 'sla_reminder_hours', None),
        "city_logo_url": getattr(s, 'city_logo_url', None),
        "support_email": getattr(s, 'support_email', None),
        "website_url": getattr(s, 'website_url', None),
        "auto_email_on_status_change": getattr(s, 'auto_email_on_status_change', True),
        "push_notifications_enabled": getattr(s, 'push_notifications_enabled', True),
        "updated_at": s.updated_at.isoformat() if hasattr(s, 'updated_at') and s.updated_at else None,
    }

@router.put("", dependencies=[Depends(require_role("super_admin"))])
def update_settings(payload: dict, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    
    try:
        s = db.query(AppSettings).first()
        if not s:
            s = AppSettings()
            db.add(s)
            db.commit()
            db.refresh(s)
    except Exception as e:
        import logging
        logging.error(f"Error querying AppSettings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database migration required. Please run: alembic upgrade head")
    
    try:
        if "allow_anonymous_reporting" in payload:
            s.allow_anonymous_reporting = bool(payload["allow_anonymous_reporting"])
        if "require_email_verification" in payload:
            s.require_email_verification = bool(payload["require_email_verification"])
        if "auto_assign_issues" in payload:
            s.auto_assign_issues = bool(payload["auto_assign_issues"])
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
        if hasattr(s, 'updated_at'):
            s.updated_at = datetime.now(timezone.utc)
        db.commit()
        return {"ok": True}
    except Exception as e:
        db.rollback()
        import logging
        logging.error(f"Error updating AppSettings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to update settings. Please check database schema.")