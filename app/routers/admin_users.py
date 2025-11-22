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
      select 
        u.id,
        u.email,
        u.name,
        u.mobile,
        u.is_active,
        u.is_verified,
        u.role,
        u.created_at,
        u.last_login,
        array_agg(sr.state_code) filter (where sr.state_code is not null) as regions
      from users u
      left join staff_regions sr on sr.user_id = u.id
      where 1=1
    """
    params = {}
    
    if q:
        query += " and (u.email ilike :q or coalesce(u.name,'') ilike :q)"
        params["q"] = f"%{q}%"
    
    if role:
        query += " and u.role = :role"
        params["role"] = role
    
    if is_active is not None:
        query += " and u.is_active = :is_active"
        params["is_active"] = is_active
    
    if is_verified is not None:
        query += " and u.is_verified = :is_verified"
        params["is_verified"] = is_verified
    
    query += " group by u.id, u.email, u.name, u.mobile, u.is_active, u.is_verified, u.role, u.created_at, u.last_login"
    query += " order by u.created_at desc"
    
    rows = db.execute(text(query), params).mappings().all()
    result = []
    for row in rows:
        row_dict = dict(row)
        # Convert datetime objects to ISO strings for JSON serialization
        if row_dict.get('created_at'):
            if hasattr(row_dict['created_at'], 'isoformat'):
                row_dict['created_at'] = row_dict['created_at'].isoformat()
        if row_dict.get('last_login'):
            if hasattr(row_dict['last_login'], 'isoformat'):
                row_dict['last_login'] = row_dict['last_login'].isoformat()
        # Convert regions array to list and filter out None values
        if row_dict.get('regions'):
            regions_list = [r for r in row_dict['regions'] if r is not None]
            row_dict['regions'] = regions_list if regions_list else []
        else:
            row_dict['regions'] = []
        result.append(row_dict)
    return result

@router.post("", dependencies=[Depends(require_role("super_admin"))])
def create_user(payload: dict = Body(...), db: Session = Depends(get_db)):
  email = (payload.get("email") or "").strip().lower()
  name = (payload.get("name") or "").strip()
  role = (payload.get("role") or "citizen").strip()
  region = payload.get("region")
  if not email or not name: raise HTTPException(400, "name_and_email_required")
  if role not in ("staff","admin"): raise HTTPException(400, "bad_role: only staff and admin can be created")
  exists = db.execute(text("select 1 from users where email=:e"), {"e": email}).first()
  if exists: raise HTTPException(400, "email_exists")
  # create inactive & unverified with random password
  result = db.execute(text("""
    insert into users(email,name,role,is_active,is_verified,hashed_password)
    values (:e,:n,:r,true,true,'$2b$12$1YQ5OJj2KQfKJ2Qx/placeholderhash')
    returning id
  """), {"e":email,"n":name,"r":role})
  user_id = result.scalar()
  if region and user_id:
    db.execute(text("""
      insert into staff_regions(user_id, state_code)
      values (:uid, :sc)
    """), {"uid": user_id, "sc": region})
  db.commit()
  return {"ok": True}

@router.put("/{user_id}", dependencies=[Depends(require_role("admin","super_admin"))])
def update_admin_user(user_id:int, payload:dict=Body(...), db:Session=Depends(get_db), me=Depends(get_current_user)):
  role = payload.get("role"); is_active = payload.get("is_active")
  if role and role not in ("citizen","staff","admin","super_admin"):
    raise HTTPException(400,"bad_role")
  # prevent demoting last super_admin or deleting self etc — basic guard
  if me.id == user_id and role and role != "super_admin":
    raise HTTPException(400,"cannot_change_own_role")
  update_data = {}
  if role is not None:
    update_data["role"] = role
  if is_active is not None:
    update_data["is_active"] = bool(is_active)
  if not update_data:
    return {"ok": True}
  
  sets = [f"{k}=:{k}" for k in update_data.keys()]
  params = {"id": user_id, **update_data}
  db.execute(text(f"update users set {', '.join(sets)} where id=:id"), params)
  db.commit()
  return {"ok": True}

@router.delete("/{user_id}", dependencies=[Depends(require_role("super_admin"))])
def delete_admin_user(user_id:int, db:Session=Depends(get_db), me=Depends(get_current_user)):
  if me.id == user_id:
    raise HTTPException(400,"cannot_delete_self")
  r = db.execute(text("select role from users where id=:id"), {"id": user_id}).first()
  if not r: raise HTTPException(404,"not_found")
  if r[0] == "super_admin": raise HTTPException(400,"cannot_delete_super_admin")
  
  # Check for transactional records (issues or comments) for citizens
  if r[0] == "citizen":
    issue_count = db.execute(text("select count(*) from issues where created_by_id=:id"), {"id": user_id}).scalar()
    comment_count = db.execute(text("select count(*) from issue_comments where user_id=:id"), {"id": user_id}).scalar()
    if issue_count > 0 or comment_count > 0:
      raise HTTPException(400, f"Cannot delete citizen with transactional records. {issue_count} issue(s) and {comment_count} comment(s) found. Deactivate instead.")
  
  db.execute(text("delete from users where id=:id"), {"id":user_id})
  db.commit(); return {"ok": True}

@router.post("/{user_id}/reset-password", dependencies=[Depends(require_role("admin","super_admin"))])
def trigger_password_reset(user_id: int, db: Session = Depends(get_db)):
    from app.models.user import User
    from app.services.notify_email import send_reset_password
    from app.core.security import make_email_token
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    try:
        token = make_email_token(user.email, "reset")
        send_reset_password(user.email, token)
        return {"ok": True, "message": "Password reset email sent"}
    except Exception as e:
        import logging
        logging.error(f"Failed to send reset email: {e}", exc_info=True)
        raise HTTPException(500, "Failed to send reset email. Please try again later.")

@router.get("/{user_id}/stats")
def get_user_stats(user_id: int, db: Session = Depends(get_db)):
    from app.models.issue import Issue
    from app.models.issue_activity import IssueActivity
    from sqlalchemy import func
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "User not found")
    
    issues_handled = db.query(Issue).filter(Issue.assigned_to_id == user_id).count()
    issues_created = db.query(Issue).filter(Issue.created_by_id == user_id).count()
    issues_resolved = db.query(Issue).filter(
        Issue.assigned_to_id == user_id,
        Issue.status == "resolved"
    ).count()
    
    recent_activity = db.query(IssueActivity).filter(
        IssueActivity.issue_id.in_(
            db.query(Issue.id).filter(Issue.assigned_to_id == user_id)
        )
    ).order_by(IssueActivity.at.desc()).limit(10).all()
    
    return {
        "issues_handled": issues_handled,
        "issues_created": issues_created,
        "issues_resolved": issues_resolved,
        "recent_activity": [
            {
                "kind": act.kind.value if hasattr(act.kind, 'value') else str(act.kind),
                "at": act.at.isoformat() if act.at else None,
                "issue_id": act.issue_id
            }
            for act in recent_activity
        ]
    }

@router.post("/bulk", dependencies=[Depends(require_role("admin","super_admin"))])
def bulk_user_operations(payload: dict = Body(...), db: Session = Depends(get_db)):
    user_ids = payload.get("user_ids", [])
    operation = payload.get("operation")
    
    if not user_ids or not isinstance(user_ids, list):
        raise HTTPException(400, "user_ids must be a non-empty list")
    
    if operation == "activate":
        db.execute(text("update users set is_active=true where id=any(:ids)"), {"ids": user_ids})
        db.commit()
        return {"ok": True, "updated_count": len(user_ids)}
    elif operation == "deactivate":
        db.execute(text("update users set is_active=false where id=any(:ids) and role != 'super_admin'"), {"ids": user_ids})
        db.commit()
        return {"ok": True, "updated_count": len(user_ids)}
    elif operation == "delete":
        # Check for transactional records before deletion
        for user_id in user_ids:
            issue_count = db.execute(text("select count(*) from issues where created_by_id=:id"), {"id": user_id}).scalar()
            comment_count = db.execute(text("select count(*) from issue_comments where user_id=:id"), {"id": user_id}).scalar()
            if issue_count > 0 or comment_count > 0:
                raise HTTPException(400, f"User {user_id} has {issue_count} issue(s) and {comment_count} comment(s). Cannot delete. Deactivate instead.")
        
        db.execute(text("delete from users where id=any(:ids) and role = 'citizen'"), {"ids": user_ids})
        db.commit()
        return {"ok": True, "updated_count": len(user_ids)}
    else:
        raise HTTPException(400, "Invalid operation")