# File: app/routers/regions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import require_role
from app.models.region import StaffRegion
from app.models.user import User

router = APIRouter(prefix="/admin/regions", tags=["admin-regions"])

@router.get("/{user_id}")
def list_user_regions(user_id:int, db: Session = Depends(get_db), _=Depends(require_role("admin","super_admin"))):
    rows = db.query(StaffRegion).filter(StaffRegion.user_id == user_id).all()
    return [{"id":r.id,"state_code":r.state_code} for r in rows]

@router.post("/{user_id}")
def add_user_region(user_id:int, body:dict, db: Session = Depends(get_db), _=Depends(require_role("admin","super_admin"))):
    code = (body.get("state_code") or "").upper()
    if not code: raise HTTPException(400, "state_code required")
    db.add(StaffRegion(user_id=user_id, state_code=code)); db.commit()
    return {"ok": True}

@router.delete("/{region_id}")
def remove_user_region(region_id:int, db: Session = Depends(get_db), _=Depends(require_role("admin","super_admin"))):
    db.query(StaffRegion).filter(StaffRegion.id==region_id).delete()
    db.commit(); return {"ok": True}