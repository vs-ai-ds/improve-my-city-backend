# File: app/routers/issues.py
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.models.issue import Issue, IssueStatus
from app.schemas.issue import IssueCreate, IssueOut
from app.core.ratelimit import limiter
from app.models.attachment import IssueAttachment
from app.services.storage import upload_image, make_object_key
from app.models.region import StaffRegion
from app.models.user import User, UserRole
from app.core.security import get_current_user, get_optional_user, require_verified_user
from sqlalchemy import func, text

router = APIRouter(prefix="/issues", tags=["issues"])

MAX_FILES = 10
MAX_BYTES = 2 * 1024 * 1024
ALLOWED = {"image/jpeg","image/png","image/webp","image/gif"}

@router.post("", response_model=IssueOut, status_code=201)
@limiter.limit("10/minute")
def create_issue(
    request: Request,
    payload: IssueCreate = Depends(),
    files: List[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    auth = Depends(get_current_user),
):
    # IN-only enforcement
    if payload.country and payload.country.upper() != "IN":
        raise HTTPException(400, "Only India is supported")
    obj = Issue(
        title=payload.title.strip(),
        description=payload.description,
        category=payload.category,
        lat=payload.lat, lng=payload.lng, address=payload.address,
        status=IssueStatus.pending,
        country=payload.country or "IN",
        state_code=payload.__dict__.get("state_code"),
        created_by_id=None,
    )
    if auth:
        # set creator if logged in
        u = db.query(User).filter(User.email == auth["email"]).first()
        if u: obj.created_by_id = u.id

    db.add(obj); db.commit(); db.refresh(obj)
    db.execute("insert into issue_activity(issue_id, kind) values (:i,'created')", {"i": obj.id})
    db.commit()

    # round-robin assign staff by state_code
    if obj.state_code:
        ids = [r[0] for r in (
            db.query(User.id)
              .join(StaffRegion, StaffRegion.user_id == User.id)
              .filter(User.role == UserRole.staff, StaffRegion.state_code == obj.state_code)
              .order_by(User.id.asc())
        ).all()]
        if ids:
            obj.assigned_to_id = ids[(obj.id - 1) % len(ids)]
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

    photos = [a.url for a in db.query(IssueAttachment).filter_by(issue_id=obj.id)]
    out = IssueOut.model_validate(obj); out.photos = photos
    return out

@router.get("", response_model=List[IssueOut])
@limiter.limit("20/minute")
def list_issues(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[IssueStatus] = Query(default=None),
    category: Optional[str] = Query(default=None),
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
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = [float(x) for x in bbox.split(",")]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
        q = q.filter(Issue.lng >= min_lng, Issue.lng <= max_lng, Issue.lat >= min_lat, Issue.lat <= max_lat)
    if mine_only and auth:
        u = db.query(User).filter(User.email == auth["email"]).first()
        if u:
            q = q.filter(Issue.created_by_id == u.id)

    q = q.order_by(Issue.created_at.desc()).offset(offset).limit(limit)
    return q.all()

@router.patch("/{issue_id}/status", response_model=IssueOut)
def update_status(issue_id: int, body: dict, db: Session = Depends(get_db)):
    from app.services.notify_email import send_status_update
    from app.services.notify_push import send_push
    from app.models.push import PushSubscription

    new_status = body.get("status")
    if new_status not in ["pending", "in_progress", "resolved"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    obj = db.query(Issue).filter(Issue.id == issue_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Issue not found")

    obj.status = IssueStatus(new_status); db.commit(); db.refresh(obj)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    if new_status == "in_progress":
        obj.in_progress_at = now
        db.commit()
        db.execute("insert into issue_activity(issue_id, kind, at) values (:i,'in_progress', now())", {"i": obj.id})
    elif new_status == "resolved":
        obj.resolved_at = now
        db.commit()
        db.execute("insert into issue_activity(issue_id, kind, at) values (:i,'resolved', now())", {"i": obj.id})
    db.commit()

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

    return obj

@router.get("/{issue_id}")
def get_issue(issue_id:int, db: Session = Depends(get_db), current=Depends(get_current_user)):
    row = db.execute(text("""
      select i.id, i.title, i.description, i.category, i.status, i.lat, i.lng, i.address, i.created_at,
             u.name as creator_name, u.email as creator_email
      from issues i left join users u on u.id = i.created_by_id
      where i.id = :id
    """), {"id": issue_id}).mappings().first()
    if not row: raise HTTPException(status_code=404, detail="Not found")
    return dict(row)

@router.get("/{issue_id}/comments")
def list_comments(issue_id:int, db:Session=Depends(get_db)):
    rows = db.execute(text("""
      select c.id, c.body, c.created_at, coalesce(u.name,u.email) as author
      from issue_comments c left join users u on u.id=c.user_id
      where c.issue_id=:iid order by c.created_at desc
    """), {"iid": issue_id}).mappings().all()
    return rows

@router.post("/{issue_id}/comments", dependencies=[Depends(require_verified_user)])
def add_comment(issue_id:int, payload:dict, user=Depends(get_current_user), db:Session=Depends(get_db)):
    body = (payload.get("body") or "").strip()
    if len(body) < 1: raise HTTPException(status_code=400, detail="Empty comment")
    db.execute(text("insert into issue_comments(issue_id,user_id,body) values (:i,:u,:b)"),
               {"i":issue_id,"u":user.id,"b":body})
    db.commit()
    return {"ok": True}