# File: app\routers\public.py
# Project: improve-my-city-backend
# Auto-added for reference

# app/routers/public.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.app_settings import AppSettings

router = APIRouter(prefix="/public", tags=["public"])

@router.get("/settings")
def public_settings(db: Session = Depends(get_db)):
    s = db.query(AppSettings).first()
    if not s:
        s = AppSettings()
        db.add(s); db.commit(); db.refresh(s)
    return {"allow_anonymous_reporting": s.allow_anonymous_reporting}