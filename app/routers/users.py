# File: app/routers/users.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import require_role
from app.models.user import User, UserRole

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

@router.get("", dependencies=[Depends(require_role("admin","super_admin"))])
def list_users(db: Session = Depends(get_db)):
    return [{"id":u.id,"email":u.email,"name":u.name,"role":u.role.value,"is_active":u.is_active,"is_verified":u.is_verified} for u in db.query(User).order_by(User.id.desc())]

@router.put("/{user_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def update_user(user_id:int, body:dict, db: Session = Depends(get_db)):
    u = db.query(User).get(user_id)
    if not u: raise HTTPException(404, "Not found")
    if u.role == UserRole.super_admin and body.get("is_active") is False:
        raise HTTPException(400, "Super admin cannot be disabled")
    if "name" in body: u.name = body["name"]
    if "is_active" in body: u.is_active = bool(body["is_active"])
    if "role" in body:
        r = body["role"]
        if r not in [x.value for x in UserRole]: raise HTTPException(400, "Bad role")
        u.role = UserRole(r)
    db.commit(); db.refresh(u)
    return {"ok": True}

@router.delete("/{user_id}", dependencies=[Depends(require_role("super_admin"))])
def delete_user(user_id:int, db: Session = Depends(get_db)):
    u = db.query(User).get(user_id)
    if not u: return {"ok": True}
    if u.role == UserRole.super_admin: raise HTTPException(400, "Super admin cannot be deleted")
    db.delete(u); db.commit()
    return {"ok": True}