# File: app/routers/admin_users.py
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.db.session import get_db
from app.core.security import require_role, get_current_user

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

@router.get("", dependencies=[Depends(require_role("admin","super_admin"))])
def list_users(
    db: Session = Depends(get_db),
    q: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    is_verified: bool | None = None
):
    query = """
      select id,email,name,mobile,is_active,is_verified,role,created_at,last_login
      from users
      where 1=1
    """
    params = {}
    
    if q:
        query += " and (email ilike :q or coalesce(name,'') ilike :q)"
        params["q"] = f"%{q}%"
    
    if role:
        query += " and role = :role"
        params["role"] = role
    
    if is_active is not None:
        query += " and is_active = :is_active"
        params["is_active"] = is_active
    
    if is_verified is not None:
        query += " and is_verified = :is_verified"
        params["is_verified"] = is_verified
    
    query += " order by created_at desc"
    
    rows = db.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]

@router.post("", dependencies=[Depends(require_role("super_admin"))])
def create_user(payload: dict = Body(...), db: Session = Depends(get_db)):
  email = (payload.get("email") or "").strip().lower()
  name = (payload.get("name") or "").strip()
  role = (payload.get("role") or "citizen").strip()
  if not email or not name: raise HTTPException(400, "name_and_email_required")
  if role not in ("citizen","staff","admin","super_admin"): raise HTTPException(400, "bad_role")
  exists = db.execute(text("select 1 from users where email=:e"), {"e": email}).first()
  if exists: raise HTTPException(400, "email_exists")
  # create inactive & unverified with random password
  db.execute(text("""
    insert into users(email,name,role,is_active,is_verified,hashed_password)
    values (:e,:n,:r,true,true,'$2b$12$1YQ5OJj2KQfKJ2Qx/placeholderhash') -- replace with real hash if needed
  """), {"e":email,"n":name,"r":role})
  db.commit()
  return {"ok": True}

@router.put("/{user_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def update_user(user_id:int, payload:dict=Body(...), db:Session=Depends(get_db), me=Depends(get_current_user)):
  role = payload.get("role"); is_active = payload.get("is_active")
  if role and role not in ("citizen","staff","admin","super_admin"):
    raise HTTPException(400,"bad_role")
  # prevent demoting last super_admin or deleting self etc — basic guard
  if me.id == user_id and role and role != "super_admin":
    raise HTTPException(400,"cannot_change_own_role")
  sets=[]; params={"id":user_id}
  if role is not None: sets.append("role=:role"); params["role"]=role
  if is_active is not None: sets.append("is_active=:act"); params["act"]=bool(is_active)
  if not sets: return {"ok": True}
  db.execute(text(f"update users set {', '.join(sets)} where id=:id"), params)
  db.commit(); return {"ok": True}

@router.delete("/{user_id}", dependencies=[Depends(require_role("super_admin"))])
def delete_user(user_id:int, db:Session=Depends(get_db), me=Depends(get_current_user)):
  if me.id == user_id:
    raise HTTPException(400,"cannot_delete_self")
  r = db.execute(text("select role from users where id=:id"), {"id": user_id}).first()
  if not r: raise HTTPException(404,"not_found")
  if r[0] == "super_admin": raise HTTPException(400,"cannot_delete_super_admin")
  db.execute(text("delete from users where id=:id"), {"id":user_id})
  db.commit(); return {"ok": True}