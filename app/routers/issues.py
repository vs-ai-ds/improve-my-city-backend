# File: app/routers/issues.py
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Request, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from app.schemas.issue import IssueCreate, IssueOut, PaginatedIssuesOut
from app.core.ratelimit import limiter
from app.models.attachment import IssueAttachment
from app.models.issue_activity import IssueActivity, ActivityKind
from app.services.storage import upload_image, make_object_key
from app.models.region import StaffRegion
from app.models.user import User, UserRole
from app.core.security import get_current_user, get_optional_user, require_verified_user
from sqlalchemy import func, text
from datetime import datetime, timezone

router = APIRouter(prefix="/issues", tags=["issues"])

MAX_FILES = 10
MAX_BYTES = 2 * 1024 * 1024
ALLOWED = {"image/jpeg","image/png","image/webp","image/gif"}

def _get_issue_photos(db: Session, issue_id: int) -> list[str]:
    """Helper to fetch photos for an issue."""
    return [a.url for a in db.query(IssueAttachment).filter_by(issue_id=issue_id).all()]

@router.post("", response_model=IssueOut, status_code=201)
@limiter.limit("10/minute")
def create_issue(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    address: Optional[str] = Form(None),
    country: Optional[str] = Form("IN"),
    state_code: Optional[str] = Form(None),
    files: List[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    auth = Depends(get_current_user),
):
    # IN-only enforcement
    if country and country.upper() != "IN":
        raise HTTPException(400, "Only India is supported")
    obj = Issue(
        title=title.strip(),
        description=description,
        category=category,
        lat=lat,
        lng=lng,
        address=address,
        status=IssueStatus.pending,
        country="IN",                 
        state_code=state_code 
    )
    if obj.lat is not None and obj.lng is not None:
        if not (6.5 <= obj.lat <= 37.6 and 68.1 <= obj.lng <= 97.4):
            raise HTTPException(status_code=400, detail="Only India is supported")
    if auth:
        obj.created_by_id = auth.id

    db.add(obj); db.commit(); db.refresh(obj)
    db.add(IssueActivity(issue_id=obj.id, kind=ActivityKind.created))
    db.commit()

    # Check auto-assign setting
    from app.models.app_settings import AppSettings
    settings = db.query(AppSettings).first()
    auto_assign_enabled = settings and settings.auto_assign_issues if settings else False
    
    from sqlalchemy import func, case
    if auto_assign_enabled and obj.state_code:
        # First try: staff assigned to this state, with least open issues
        staff_with_counts = (
            db.query(
                User.id,
                func.count(Issue.id).label("open_count")
            )
            .join(StaffRegion, StaffRegion.user_id == User.id)
            .outerjoin(
                Issue,
                (Issue.assigned_to_id == User.id) & 
                (Issue.status.in_([IssueStatus.pending, IssueStatus.in_progress]))
            )
            .filter(
                User.role == UserRole.staff,
                User.is_active == True,
                StaffRegion.state_code == obj.state_code
            )
            .group_by(User.id)
            .order_by(func.count(Issue.id).asc(), User.id.asc())
            .limit(1)
            .first()
        )
        if staff_with_counts:
            obj.assigned_to_id = staff_with_counts[0]
        else:
            # Second try: admin (excluding super_admin) with least open issues
            admin_with_counts = (
                db.query(
                    User.id,
                    func.count(Issue.id).label("open_count")
                )
                .outerjoin(
                    Issue,
                    (Issue.assigned_to_id == User.id) & 
                    (Issue.status.in_([IssueStatus.pending, IssueStatus.in_progress]))
                )
                .filter(
                    User.role == UserRole.admin,
                    User.is_active == True
                )
                .group_by(User.id)
                .order_by(func.count(Issue.id).asc(), User.id.asc())
                .limit(1)
                .first()
            )
            if admin_with_counts:
                obj.assigned_to_id = admin_with_counts[0]
            else:
                # Third try: any super_admin
                super_admin = db.query(User).filter(
                    User.role == UserRole.super_admin,
                    User.is_active == True
                ).first()
                if super_admin:
                    obj.assigned_to_id = super_admin.id
        if auto_assign_enabled:
            db.commit()

    # images
    if files:
        if len(files) > MAX_FILES:
            raise HTTPException(status_code=400, detail=f"Max {MAX_FILES} images")
        for f in files:
            if f.content_type not in ALLOWED:
                raise HTTPException(status_code=400, detail="Unsupported image type")
            data = f.file.read()
            if len(data) > MAX_BYTES:
                raise HTTPException(status_code=400, detail="Image exceeds 2MB")
            key = make_object_key(obj.id, f.filename or "upload.jpg")
            url = upload_image(data, f.content_type, key)
            db.add(IssueAttachment(issue_id=obj.id, url=url, content_type=f.content_type, size=len(data)))
        db.commit()

    photos = _get_issue_photos(db, obj.id)
    issue_dict = {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "category": obj.category,
        "status": obj.status.value,  # Convert enum to string
        "lat": obj.lat,
        "lng": obj.lng,
        "address": obj.address,
        "created_at": obj.created_at,
    }
    out = IssueOut.model_validate(issue_dict)
    out.photos = photos
    
    if obj.created_by_id:
        creator = db.query(User).filter(User.id == obj.created_by_id).first()
        if creator and creator.email:
            try:
                from app.services.notify_email import send_report_confirmation
                send_report_confirmation(creator.email, obj.id, obj.title)
            except Exception:
                pass  # Don't fail report creation if email fails
    
    return out

@router.get("", response_model=PaginatedIssuesOut)
@limiter.limit("20/minute")
def list_issues(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[IssueStatus] = Query(default=None),
    category: Optional[str] = Query(default=None),
    state_code: Optional[str] = Query(default=None),
    bbox: Optional[str] = Query(default=None, description="minLng,minLat,maxLng,maxLat"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    mine_only: int = Query(default=0, ge=0, le=1),
    auth = Depends(get_optional_user), 
):
    q = db.query(Issue)
    if status:
        q = q.filter(Issue.status == status)
    if category:
        q = q.filter(Issue.category == category)
    if state_code:
        q = q.filter(Issue.state_code == state_code)
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = [float(x) for x in bbox.split(",")]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
        q = q.filter(Issue.lng >= min_lng, Issue.lng <= max_lng, Issue.lat >= min_lat, Issue.lat <= max_lat)
    if mine_only and auth:
        q = q.filter(Issue.created_by_id == auth.id)

    total_count = q.count()
    issues = q.order_by(Issue.created_at.desc()).offset(offset).limit(limit).all()
    result = []
    for issue in issues:
        photos = _get_issue_photos(db, issue.id)
        # Fetch creator info
        creator = None
        if issue.created_by_id:
            creator_user = db.query(User).filter(User.id == issue.created_by_id).first()
            if creator_user:
                creator = {"name": creator_user.name, "email": creator_user.email}
        # Fetch assigned user info
        assigned_to = None
        if issue.assigned_to_id:
            assigned_user = db.query(User).filter(User.id == issue.assigned_to_id).first()
            if assigned_user:
                assigned_to = {"id": assigned_user.id, "name": assigned_user.name, "email": assigned_user.email, "role": assigned_user.role.value}
        # Convert enum to value for Pydantic validation
        issue_dict = {
            "id": issue.id,
            "title": issue.title,
            "description": issue.description,
            "category": issue.category,
            "status": issue.status.value,
            "lat": issue.lat,
            "lng": issue.lng,
            "address": issue.address,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "country": issue.country,
            "state_code": issue.state_code,
            "assigned_to_id": issue.assigned_to_id,
        }
        out = IssueOut.model_validate(issue_dict)
        out.photos = photos
        out_dict = out.model_dump()
        out_dict["creator"] = creator
        out_dict["assigned_to"] = assigned_to
        result.append(out_dict)
    return {
        "items": result,
        "total": total_count,
        "offset": offset,
        "limit": limit,
    }

@router.patch("/{issue_id}/status", response_model=IssueOut)
def update_status(issue_id: int, body: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.services.notify_email import send_status_update
    from app.services.notify_push import send_push
    from app.models.push import PushSubscription

    new_status = body.get("status")
    comment_body = body.get("comment", "").strip()
    if new_status not in ["pending", "in_progress", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    obj = db.query(Issue).filter(Issue.id == issue_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Issue not found")

    # Check if user is admin or super_admin
    can_update = current_user.role in [UserRole.admin, UserRole.super_admin]
    # Or if user is staff and assigned to this issue
    if not can_update and current_user.role == UserRole.staff:
        can_update = obj.assigned_to_id == current_user.id
    
    if not can_update:
        raise HTTPException(status_code=403, detail="Only admins/staff or assigned staff can update status")

    # Require assignment before moving to in_progress
    if new_status == "in_progress" and not obj.assigned_to_id:
        raise HTTPException(status_code=400, detail="Issue must be assigned before marking as in progress")
    
    # Require comment when changing status (except from pending if not assigned)
    if new_status != "pending" and not comment_body:
        raise HTTPException(status_code=400, detail="Comment is required when changing status")

    # Require comment when resolving
    if new_status == "resolved" and obj.status != IssueStatus.resolved:
        if not comment_body:
            raise HTTPException(status_code=400, detail="Comment is required when resolving an issue")

    obj.status = IssueStatus(new_status)
    now = datetime.now(timezone.utc)
    if new_status == "in_progress":
        obj.in_progress_at = now
        db.add(IssueActivity(issue_id=obj.id, kind=ActivityKind.in_progress, at=now))
    elif new_status == "resolved":
        obj.resolved_at = now
        db.add(IssueActivity(issue_id=obj.id, kind=ActivityKind.resolved, at=now))
    
    # Add comment if provided
    if comment_body:
        db.execute(text("insert into issue_comments(issue_id,user_id,body,created_at) values (:i,:u,:b,:t)"),
                  {"i": issue_id, "u": current_user.id, "b": comment_body, "t": now})
    
    db.commit()
    db.refresh(obj)

    # notify creator if known
    if obj.created_by_id:
        u = db.query(User).filter(User.id == obj.created_by_id).first()
        if u:
            try: send_status_update(u.email, obj.id, new_status)
            except Exception: pass
            # push
            subs = db.query(PushSubscription).filter(PushSubscription.user_id == u.id).all()
            for s in subs:
                try:
                    send_push(
                        {"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                        {"title": "Improve My City", "body": f"Issue #{obj.id} is now {new_status.replace('_',' ')}"}
                    )
                except Exception: pass

    photos = _get_issue_photos(db, obj.id)
    issue_dict = {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "category": obj.category,
        "status": obj.status.value,  # Convert enum to string
        "lat": obj.lat,
        "lng": obj.lng,
        "address": obj.address,
        "created_at": obj.created_at,
    }
    out = IssueOut.model_validate(issue_dict)
    out.photos = photos
    return out

@router.get("/{issue_id}")
def get_issue(issue_id:int, db: Session = Depends(get_db), current=Depends(get_optional_user)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Not found")
    
    # Fetch photos
    photos = _get_issue_photos(db, issue_id)
    
    # Fetch creator info
    creator = None
    if issue.created_by_id:
        creator_user = db.query(User).filter(User.id == issue.created_by_id).first()
        if creator_user:
            creator = {"id": creator_user.id, "name": creator_user.name, "email": creator_user.email}
    
    # Build response - convert enum to string for Pydantic validation
    issue_dict = {
        "id": issue.id,
        "title": issue.title,
        "description": issue.description,
        "category": issue.category,
        "status": issue.status.value,
        "lat": issue.lat,
        "lng": issue.lng,
        "address": issue.address,
        "created_at": issue.created_at,
    }
    result = IssueOut.model_validate(issue_dict)
    result.photos = photos
    result_dict = result.model_dump()
    result_dict["creator"] = creator
    result_dict["assigned_to_id"] = issue.assigned_to_id
    result_dict["created_by_id"] = issue.created_by_id
    result_dict["country"] = issue.country
    result_dict["state_code"] = issue.state_code
    return result_dict

@router.patch("/{issue_id}")
def update_issue(issue_id: int, body: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from datetime import datetime
    
    obj = db.query(Issue).filter(Issue.id == issue_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if "assigned_to_id" in body:
        assigned_id = body.get("assigned_to_id")
        if assigned_id is None:
            obj.assigned_to_id = None
        else:
            user = db.query(User).filter(User.id == assigned_id).first()
            if not user:
                raise HTTPException(status_code=400, detail="User not found")
            obj.assigned_to_id = assigned_id
        obj.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(obj)
    
    photos = _get_issue_photos(db, obj.id)
    issue_dict = {
        "id": obj.id,
        "title": obj.title,
        "description": obj.description,
        "category": obj.category,
        "status": obj.status.value,
        "lat": obj.lat,
        "lng": obj.lng,
        "address": obj.address,
        "created_at": obj.created_at,
        "updated_at": obj.updated_at,
        "country": obj.country,
        "state_code": obj.state_code,
        "assigned_to_id": obj.assigned_to_id,
    }
    out = IssueOut.model_validate(issue_dict)
    out.photos = photos
    out_dict = out.model_dump()
    
    if obj.created_by_id:
        creator_user = db.query(User).filter(User.id == obj.created_by_id).first()
        if creator_user:
            out_dict["creator"] = {"name": creator_user.name, "email": creator_user.email}
    
    if obj.assigned_to_id:
        assigned_user = db.query(User).filter(User.id == obj.assigned_to_id).first()
        if assigned_user:
            out_dict["assigned_to"] = {"id": assigned_user.id, "name": assigned_user.name, "email": assigned_user.email, "role": assigned_user.role.value}
    
    return out_dict

@router.get("/{issue_id}/comments")
def list_comments(issue_id:int, db:Session=Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    creator_id = issue.created_by_id if issue else None
    rows = db.execute(text("""
      select c.id, c.body, c.created_at, c.user_id, 
             coalesce(u.name, u.email, 'Anonymous') as author,
             u.role as user_role
      from issue_comments c left join users u on u.id=c.user_id
      where c.issue_id=:iid order by c.created_at desc
    """), {"iid": issue_id}).mappings().all()
    result = []
    for r in rows:
        user_role = r["user_role"]
        if user_role and hasattr(user_role, 'value'):
            user_role_str = user_role.value
        elif user_role:
            user_role_str = str(user_role)
        else:
            user_role_str = None
        comment = {
            "id": r["id"], 
            "body": r["body"], 
            "created_at": r["created_at"].isoformat() if r["created_at"] else None, 
            "author": r["author"],
            "user_role": user_role_str,
            "is_creator": r["user_id"] == creator_id if creator_id and r["user_id"] else False
        }
        result.append(comment)
    return result

@router.post("/{issue_id}/comments")
def add_comment(issue_id:int, payload:dict, user: User=Depends(get_current_user), db:Session=Depends(get_db)):
    if not user:
        raise HTTPException(status_code=401, detail="You must be logged in to post comments")
    
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.status == IssueStatus.resolved:
        raise HTTPException(status_code=400, detail="Cannot comment on resolved issues")
    
    body = (payload.get("body") or "").strip()
    if len(body) < 1: raise HTTPException(status_code=400, detail="Empty comment")
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    db.execute(text("insert into issue_comments(issue_id,user_id,body,created_at) values (:i,:u,:b,:t)"),
               {"i":issue_id,"u":user.id,"b":body,"t":now})
    db.commit()
    # Fetch the created comment
    creator_id = issue.created_by_id
    row = db.execute(text("""
      select c.id, c.body, c.created_at, c.user_id,
             coalesce(u.name, u.email, 'Anonymous') as author,
             u.role as user_role
      from issue_comments c left join users u on u.id=c.user_id
      where c.issue_id=:iid and c.user_id=:uid and c.body=:b
      order by c.created_at desc limit 1
    """), {"iid": issue_id, "uid": user.id, "b": body}).mappings().first()
    if row:
        return {
            "id": row["id"], 
            "body": row["body"], 
            "created_at": row["created_at"].isoformat() if row["created_at"] else None, 
            "author": row["author"],
            "user_role": row["user_role"].value if row["user_role"] else None,
            "is_creator": row["user_id"] == creator_id if creator_id and row["user_id"] else False
        }
    return {"ok": True}