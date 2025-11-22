# File: app/routers/issues.py
from fastapi import APIRouter, Depends, Query, HTTPException, UploadFile, File, Request, Form, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Union
from app.db.session import get_db, SessionLocal
from app.models.issue import Issue, IssueStatus
from app.schemas.issue import (
    IssueOut,
    PaginatedIssuesOut,
    DuplicateIssueResponse,
    IssueUpdate,
)
from app.core.ratelimit import limiter
from app.models.attachment import IssueAttachment
from app.models.issue_activity import IssueActivity, ActivityKind
from app.services.storage import upload_image, make_object_key
from app.models.region import StaffRegion
from app.models.user import User, UserRole
from app.core.security import get_current_user, get_optional_user
from sqlalchemy import text
from datetime import datetime, timezone

router = APIRouter(prefix="/issues", tags=["issues"])

MAX_FILES = 10
MAX_BYTES = 2 * 1024 * 1024
ALLOWED = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _get_issue_photos(db: Session, issue_id: int) -> list[str]:
    """Helper to fetch photos for an issue."""
    return [a.url for a in db.query(IssueAttachment).filter_by(issue_id=issue_id).all()]

def _send_assignment_notifications_safe(
    issue_id: int, assigned_id: int | None, assigner_id: int, old_assigned_id: int | None):
    db = SessionLocal()
    try:
        # Send assignment notification email and push
        from app.services.notify_email import send_assignment_notification
        from app.services.notify_push import send_push
        from app.models.push import PushSubscription

        settings = _get_app_settings(db)
        auto_email = (
            getattr(settings, "auto_email_on_status_change", True)
            if settings
            else True
        )
        push_enabled = (
            getattr(settings, "push_notifications_enabled", False)
            if settings
            else False
        )

        if assigned_id != old_assigned_id:
            assigned_user = (
                db.query(User)
                .filter(User.id == assigned_id)
                .first()
            )
            current_user = db.query(User).filter(User.id == assigner_id).first()
            issue = db.query(Issue).filter(Issue.id == issue_id).first()
            if assigned_user:
                assigner_name = (
                    current_user.name
                    or current_user.email
                    or "Admin"
                )

                # Send email
                if auto_email and assigned_user.email:
                    try:
                        send_assignment_notification(
                            assigned_user.email,
                            issue.id,
                            issue.title,
                            assigner_name,
                        )
                    except Exception:
                        pass

                # Send push notification
                if push_enabled:
                    subs = (
                        db.query(PushSubscription)
                        .filter(
                            PushSubscription.user_id == assigned_user.id
                        )
                        .all()
                    )
                    for s in subs:
                        try:
                            send_push(
                                {
                                    "endpoint": s.endpoint,
                                    "keys": {
                                        "p256dh": s.p256dh,
                                        "auth": s.auth,
                                    },
                                },
                                {
                                    "title": "Issue Assigned",
                                    "body": (
                                        f"Issue #{issue.id} "
                                        f"assigned to you by {assigner_name}"
                                    ),
                                },
                            )
                        except Exception:
                            pass
    except Exception as e:
        import logging
        logging.error(f"Error in background assignment notifications: {e}", exc_info=True)
    finally:
        db.close()


def _send_comment_notifications_safe(issue_id: int, comment_author_id: int, comment_body: str = ""):
    db = SessionLocal()
    try:
        from app.services.notify_email import send_comment_notification
        from app.services.notify_push import send_push
        from app.models.push import PushSubscription

        settings = _get_app_settings(db)
        auto_email = (
            getattr(settings, "auto_email_on_status_change", True)
            if settings
            else True
        )
        push_enabled = (
            getattr(settings, "push_notifications_enabled", False)
            if settings
            else False
        )

        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            return

        comment_author = db.query(User).filter(User.id == comment_author_id).first()
        if not comment_author:
            return

        comment_author_name = comment_author.name or comment_author.email or "Anonymous"
        
        if not comment_body:
            from sqlalchemy import text
            latest_comment = db.execute(
                text(
                    "SELECT body FROM issue_comments WHERE issue_id=:iid AND user_id=:uid ORDER BY created_at DESC LIMIT 1"
                ),
                {"iid": issue_id, "uid": comment_author_id},
            ).scalar()
            if latest_comment:
                comment_body = latest_comment
        
        recipients = set()
        recipient_users = []

        if issue.created_by_id:
            creator = db.query(User).filter(User.id == issue.created_by_id).first()
            if creator and creator.email and creator.email != comment_author.email:
                recipients.add(creator.email)
                recipient_users.append(creator)

        if issue.assigned_to_id:
            assigned = db.query(User).filter(User.id == issue.assigned_to_id).first()
            if assigned and assigned.email and assigned.email != comment_author.email:
                recipients.add(assigned.email)
                recipient_users.append(assigned)

        admins = (
            db.query(User)
            .filter(User.role.in_([UserRole.admin, UserRole.super_admin]))
            .all()
        )
        for admin in admins:
            if admin.email and admin.email != comment_author.email:
                recipients.add(admin.email)
                if admin not in recipient_users:
                    recipient_users.append(admin)

        for recipient in recipient_users:
            if auto_email and recipient.email:
                try:
                    send_comment_notification(
                        recipient.email,
                        issue.id,
                        issue.title,
                        comment_author_name,
                        comment_body,
                    )
                except Exception:
                    pass

            if push_enabled:
                subs = (
                    db.query(PushSubscription)
                    .filter(PushSubscription.user_id == recipient.id)
                    .all()
                )
                for s in subs:
                    try:
                        send_push(
                            {
                                "endpoint": s.endpoint,
                                "keys": {"p256dh": s.p256dh, "auth": s.auth},
                            },
                            {
                                "title": "New Comment",
                                "body": f"{comment_author_name} commented on issue #{issue.id}",
                            },
                        )
                    except Exception:
                        pass
    except Exception as e:
        import logging
        logging.error(f"Error in background comment notifications: {e}", exc_info=True)
    finally:
        db.close()


def _send_status_change_notifications_safe(issue_id: int, new_status: str, changer_id: int):
    db = SessionLocal()
    try:
        from app.services.notify_email import send_status_update
        from app.services.notify_push import send_push
        from app.models.push import PushSubscription

        settings = _get_app_settings(db)
        send_emails = (
            getattr(settings, "auto_email_on_status_change", True)
            if settings
            else True
        )

        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if not issue:
            return

        if issue.created_by_id and send_emails:
            creator = db.query(User).filter(User.id == issue.created_by_id).first()
            if creator and creator.email:
                try:
                    send_status_update(creator.email, issue.id, new_status)
                except Exception:
                    pass
                subs = (
                    db.query(PushSubscription)
                    .filter(PushSubscription.user_id == creator.id)
                    .all()
                )
                for s in subs:
                    try:
                        send_push(
                            {
                                "endpoint": s.endpoint,
                                "keys": {"p256dh": s.p256dh, "auth": s.auth},
                            },
                            {
                                "title": "Improve My City",
                                "body": f"Issue #{issue.id} is now {new_status.replace('_', ' ')}",
                            },
                        )
                    except Exception:
                        pass

        if issue.assigned_to_id and send_emails and new_status in ["in_progress", "resolved"]:
            assigned = db.query(User).filter(User.id == issue.assigned_to_id).first()
            if assigned and assigned.email and assigned.id != issue.created_by_id:
                try:
                    send_status_update(assigned.email, issue.id, new_status)
                except Exception:
                    pass
                subs = (
                    db.query(PushSubscription)
                    .filter(PushSubscription.user_id == assigned.id)
                    .all()
                )
                for s in subs:
                    try:
                        send_push(
                            {
                                "endpoint": s.endpoint,
                                "keys": {"p256dh": s.p256dh, "auth": s.auth},
                            },
                            {
                                "title": "Improve My City",
                                "body": f"Issue #{issue.id} is now {new_status.replace('_', ' ')}",
                            },
                        )
                    except Exception:
                        pass
    except Exception as e:
        import logging
        logging.error(f"Error in background status change notifications: {e}", exc_info=True)
    finally:
        db.close()


def _send_report_confirmation_safe(issue_id: int, creator_email: str):
    db = SessionLocal()
    try:
        from app.services.notify_email import send_report_confirmation

        issue = db.query(Issue).filter(Issue.id == issue_id).first()
        if issue and creator_email:
            try:
                send_report_confirmation(creator_email, issue.id, issue.title)
            except Exception:
                pass
    except Exception as e:
        import logging
        logging.error(f"Error in background report confirmation: {e}", exc_info=True)
    finally:
        db.close()


def _get_app_settings(db: Session):
    """Helper to safely get AppSettings, handling missing columns."""
    from app.models.app_settings import AppSettings
    try:
        settings = db.query(AppSettings).first()
        return settings
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        try:
            result = db.execute(text("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name='app_settings'
            """))
            existing_columns = {row[0] for row in result}
            select_cols = [
                col
                for col in [
                    "id",
                    "auto_assign_issues",
                    "auto_email_on_status_change",
                    "push_notifications_enabled",
                ]
                if col in existing_columns
            ]
            if not select_cols:
                return None
            result = (
                db.execute(
                    text(f"SELECT {', '.join(select_cols)} FROM app_settings LIMIT :limit_val")
                ).params(limit_val=1)
                .mappings()
                .first()
            )
            if result:
                settings = AppSettings()
                for key, value in result.items():
                    if hasattr(settings, key):
                        setattr(settings, key, value)
                return settings
        except Exception:
            pass
        return None


@router.post("", response_model=Union[IssueOut, DuplicateIssueResponse], status_code=201)
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
    bypass_duplicate_check: Optional[str] = Form(None),
    files: List[UploadFile] | None = File(default=None),
    db: Session = Depends(get_db),
    auth=Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    # IN-only enforcement
    if country and country.upper() != "IN":
        raise HTTPException(400, "Only India is supported")

    # Address validation
    if not address or not address.strip() or len(address.strip()) < 3:
        raise HTTPException(
            status_code=400,
            detail="Address is required and must be at least 3 characters",
        )

    obj = Issue(
        title=title.strip(),
        description=description,
        category=category,
        lat=lat,
        lng=lng,
        address=address.strip(),
        status=IssueStatus.pending,
        country="IN",
        state_code=state_code,
    )
    if obj.lat is not None and obj.lng is not None:
        if not (6.5 <= obj.lat <= 37.6 and 68.1 <= obj.lng <= 97.4):
            raise HTTPException(status_code=400, detail="Only India is supported")

    # Duplicate detection: same address + same type within 2 hours
    bypass_duplicate = bypass_duplicate_check == "true"
    if obj.lat and obj.lng and category and not bypass_duplicate:
        from datetime import timedelta

        two_hours_ago = datetime.utcnow() - timedelta(hours=2)
        similar_issues = (
            db.query(Issue)
            .filter(
                Issue.category == category,
                Issue.created_at >= two_hours_ago,
                Issue.lat.isnot(None),
                Issue.lng.isnot(None),
            )
            .all()
        )

        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371000
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return R * c

        for existing in similar_issues:
            if existing.lat and existing.lng:
                distance = haversine(obj.lat, obj.lng, existing.lat, existing.lng)
                if distance <= 50:  # Within 50 meters
                    return DuplicateIssueResponse(
                        duplicate=True,
                        existing_issue_id=existing.id,
                        message=(
                            f"A similar issue (#{existing.id}) was reported recently at this location. "
                            "Would you like to view it instead?"
                        ),
                    )

    if auth:
        obj.created_by_id = auth.id

    db.add(obj)
    db.commit()
    db.refresh(obj)
    db.add(IssueActivity(issue_id=obj.id, kind=ActivityKind.created))
    db.commit()

    # Check auto-assign setting
    settings = _get_app_settings(db)
    auto_assign_enabled = (
        getattr(settings, "auto_assign_issues", False) if settings else False
    )

    from sqlalchemy import func as sa_func

    if auto_assign_enabled and obj.state_code:
        # First try: staff assigned to this state, with least open issues
        staff_with_counts = (
            db.query(User.id, sa_func.count(Issue.id).label("open_count"))
            .join(StaffRegion, StaffRegion.user_id == User.id)
            .outerjoin(
                Issue,
                (Issue.assigned_to_id == User.id)
                & (
                    Issue.status.in_(
                        [IssueStatus.pending, IssueStatus.in_progress]
                    )
                ),
            )
            .filter(
                User.role == UserRole.staff,
                User.is_active.is_(True),
                StaffRegion.state_code == obj.state_code,
            )
            .group_by(User.id)
            .order_by(sa_func.count(Issue.id).asc(), User.id.asc())
            .limit(1)
            .first()
        )
        if staff_with_counts:
            obj.assigned_to_id = staff_with_counts[0]
        else:
            # Second try: admin (excluding super_admin) with least open issues
            admin_with_counts = (
                db.query(User.id, sa_func.count(Issue.id).label("open_count"))
                .outerjoin(
                    Issue,
                    (Issue.assigned_to_id == User.id)
                    & (
                        Issue.status.in_(
                            [IssueStatus.pending, IssueStatus.in_progress]
                        )
                    ),
                )
                .filter(
                    User.role == UserRole.admin,
                    User.is_active.is_(True),
                )
                .group_by(User.id)
                .order_by(sa_func.count(Issue.id).asc(), User.id.asc())
                .limit(1)
                .first()
            )
            if admin_with_counts:
                obj.assigned_to_id = admin_with_counts[0]
            else:
                # Third try: any super_admin
                super_admin = (
                    db.query(User)
                    .filter(
                        User.role == UserRole.super_admin,
                        User.is_active.is_(True),
                    )
                    .first()
                )
                if super_admin:
                    obj.assigned_to_id = super_admin.id
        if auto_assign_enabled:
            db.commit()

    # images
    if files:
        if len(files) > MAX_FILES:
            raise HTTPException(
                status_code=400, detail=f"Max {MAX_FILES} images"
            )
        for f in files:
            if f.content_type not in ALLOWED:
                raise HTTPException(
                    status_code=400, detail="Unsupported image type"
                )
            data = f.file.read()
            if len(data) > MAX_BYTES:
                raise HTTPException(
                    status_code=400, detail="Image exceeds 2MB"
                )
            key = make_object_key(obj.id, f.filename or "upload.jpg")
            url = upload_image(data, f.content_type, key)
            db.add(
                IssueAttachment(
                    issue_id=obj.id,
                    url=url,
                    content_type=f.content_type,
                    size=len(data),
                )
            )
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
            background_tasks.add_task(
                _send_report_confirmation_safe,
                issue_id=obj.id,
                creator_email=creator.email,
            )

    return out


@router.get("", response_model=PaginatedIssuesOut)
@limiter.limit("20/minute")
def list_issues(
    request: Request,
    db: Session = Depends(get_db),
    status: Optional[IssueStatus] = Query(default=None),
    statuses: Optional[str] = Query(
        default=None, description="Comma-separated list of statuses"
    ),
    category: Optional[str] = Query(default=None),
    state_code: Optional[str] = Query(default=None),
    bbox: Optional[str] = Query(
        default=None, description="minLng,minLat,maxLng,maxLat"
    ),
    limit: int = Query(default=20, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    mine_only: int = Query(default=0, ge=0, le=1),
    date_range: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    assigned_to_id: Optional[int] = Query(default=None),
    overdue: int = Query(default=0, ge=0, le=1),
    needs_attention: int = Query(default=0, ge=0, le=1),
    auth=Depends(get_optional_user),
):
    from datetime import timedelta

    q = db.query(Issue)
    now = datetime.utcnow()

    # --------- STATUS FILTERING ---------
    if statuses:
        status_list = [s.strip() for s in statuses.split(",") if s.strip()]
        if status_list:
            valid_statuses = []
            for s in status_list:
                try:
                    valid_statuses.append(IssueStatus(s))
                except ValueError:
                    # ignore invalid values
                    pass
            if valid_statuses:
                q = q.filter(Issue.status.in_(valid_statuses))
    elif status:
        q = q.filter(Issue.status == status)

    # Category / Region
    if category:
        q = q.filter(Issue.category == category)
    if state_code:
        q = q.filter(Issue.state_code == state_code)

    # --------- DATE RANGE FILTER ---------
    if date_range:
        if date_range == "7d":
            since = now - timedelta(days=7)
            q = q.filter(Issue.created_at >= since)
        elif date_range == "30d":
            since = now - timedelta(days=30)
            q = q.filter(Issue.created_at >= since)
        elif date_range == "90d":
            since = now - timedelta(days=90)
            q = q.filter(Issue.created_at >= since)
        # "all_time" → front-end simply does not send date_range

    # --------- SEARCH (ID + TEXT FIELDS) ---------
    if search:
        search_term = f"%{search}%"
        if search.isdigit():
            q = q.filter(
                (Issue.id == int(search))
                | Issue.title.ilike(search_term)
                | Issue.description.ilike(search_term)
                | Issue.address.ilike(search_term)
            )
        else:
            q = q.filter(
                Issue.title.ilike(search_term)
                | Issue.description.ilike(search_term)
                | Issue.address.ilike(search_term)
            )

    # --------- BBOX FILTER ---------
    if bbox:
        try:
            min_lng, min_lat, max_lng, max_lat = [
                float(x) for x in bbox.split(",")
            ]
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid bbox format")
        q = q.filter(
            Issue.lng >= min_lng,
            Issue.lng <= max_lng,
            Issue.lat >= min_lat,
            Issue.lat <= max_lat,
        )

    # --------- MINE ONLY (issues created by logged-in user) ---------
    if mine_only and auth:
        q = q.filter(Issue.created_by_id == auth.id)

    # --------- EXPLICIT ASSIGNED FILTER (dropdown / quick "assigned_to_me") ---------
    if assigned_to_id is not None:
        if assigned_to_id == 0:
            # 0 means "Unassigned"
            q = q.filter(Issue.assigned_to_id.is_(None))
        else:
            q = q.filter(Issue.assigned_to_id == assigned_to_id)

    # --------- OVERDUE / NEEDS ATTENTION QUICK FILTERS ---------
    if overdue:
        seven_days_ago = now - timedelta(days=7)
        q = q.filter(
            Issue.status.in_(
                [IssueStatus.pending, IssueStatus.in_progress]
            ),
            Issue.created_at < seven_days_ago,
        )
    if needs_attention:
        q = q.filter(
            Issue.status.in_(
                [IssueStatus.pending, IssueStatus.in_progress]
            ),
            Issue.assigned_to_id.is_(None),
        )

    total_count = q.count()
    issues = (
        q.order_by(Issue.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    if not issues:
        return {
            "items": [],
            "total": total_count,
            "offset": offset,
            "limit": limit,
        }

    # --------- BATCH FETCH RELATED DATA ---------
    issue_ids = [i.id for i in issues]

    # Photos
    attachments = (
        db.query(IssueAttachment)
        .filter(IssueAttachment.issue_id.in_(issue_ids))
        .all()
    )
    photos_by_issue: dict[int, list[str]] = {}
    for a in attachments:
        photos_by_issue.setdefault(a.issue_id, []).append(a.url)

    # Creators
    creator_ids = {i.created_by_id for i in issues if i.created_by_id}
    creators: dict[int, User] = {}
    if creator_ids:
        for u in db.query(User).filter(User.id.in_(creator_ids)):
            creators[u.id] = u

    # Assigned users
    assigned_ids = {
        i.assigned_to_id for i in issues if i.assigned_to_id
    }
    assignees: dict[int, User] = {}
    if assigned_ids:
        for u in db.query(User).filter(User.id.in_(assigned_ids)):
            assignees[u.id] = u

    result: list[IssueOut] = []
    for issue in issues:
        creator_user = (
            creators.get(issue.created_by_id) if issue.created_by_id else None
        )
        assigned_user = (
            assignees.get(issue.assigned_to_id)
            if issue.assigned_to_id
            else None
        )

        # Filter email based on user role
        show_creator_email = False
        show_assigned_email = False
        if auth:
            if auth.role.value in ["super_admin", "admin", "staff"]:
                show_creator_email = True
                show_assigned_email = True
            elif creator_user and creator_user.id == auth.id:
                show_creator_email = True
            elif assigned_user and assigned_user.id == auth.id:
                show_assigned_email = True

        creator_data = (
            {
                "id": creator_user.id,
                "name": creator_user.name,
                "email": creator_user.email if show_creator_email else None,
                "role": (
                    creator_user.role.value
                    if hasattr(creator_user.role, "value")
                    else str(creator_user.role)
                )
                if creator_user and creator_user.role
                else None,
            }
            if creator_user
            else None
        )

        assigned_data = (
            {
                "id": assigned_user.id,
                "name": assigned_user.name,
                "email": assigned_user.email
                if show_assigned_email
                else None,
                "role": (
                    assigned_user.role.value
                    if hasattr(assigned_user.role, "value")
                    else str(assigned_user.role)
                )
                if assigned_user and assigned_user.role
                else None,
            }
            if assigned_user
            else None
        )

        issue_dict = {
            "id": issue.id,
            "title": issue.title,
            "description": issue.description,
            "category": issue.category,
            "status": issue.status.value,
            "lat": issue.lat,
            "lng": issue.lng,
            "address": issue.address,
            "country": issue.country,
            "state_code": issue.state_code,
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "in_progress_at": issue.in_progress_at,
            "resolved_at": issue.resolved_at,
            "assigned_to_id": issue.assigned_to_id,
            "creator": creator_data,
            "assigned_to": assigned_data,
        }

        out = IssueOut.model_validate(issue_dict)
        out.photos = photos_by_issue.get(issue.id, [])
        result.append(out)

    return {
        "items": result,
        "total": total_count,
        "offset": offset,
        "limit": limit,
    }


@router.patch("/{issue_id}/status", response_model=IssueOut)
def update_status(
    issue_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):

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
        raise HTTPException(
            status_code=403,
            detail="Only admins/staff or assigned staff can update status",
        )

    # Require assignment before moving to in_progress
    if new_status == "in_progress" and not obj.assigned_to_id:
        raise HTTPException(
            status_code=400,
            detail="Issue must be assigned before marking as in progress",
        )

    # Require comment when changing status
    if new_status != "pending" and not comment_body:
        raise HTTPException(
            status_code=400,
            detail="Comment is required when changing status",
        )

    if new_status == "resolved" and obj.status != IssueStatus.resolved:
        if not comment_body:
            raise HTTPException(
                status_code=400,
                detail="Comment is required when resolving an issue",
            )

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
        db.execute(
            text(
                "insert into issue_comments(issue_id,user_id,body,created_at) values (:i,:u,:b,:t)"
            ),
            {"i": issue_id, "u": current_user.id, "b": comment_body, "t": now},
        )

    db.commit()
    db.refresh(obj)

    background_tasks.add_task(
        _send_status_change_notifications_safe,
        issue_id=issue_id,
        new_status=new_status,
        changer_id=current_user.id,
    )

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
def get_issue(
    issue_id: int,
    db: Session = Depends(get_db),
    current=Depends(get_optional_user),
):
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
            show_creator_email = False
            if current:
                if current.role.value in ["super_admin", "admin", "staff"]:
                    show_creator_email = True
                elif creator_user.id == current.id:
                    show_creator_email = True
            creator = {
                "id": creator_user.id,
                "name": creator_user.name,
                "email": creator_user.email if show_creator_email else None,
            }

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

    # Add assigned_to object for detail view too
    if issue.assigned_to_id:
        assigned_user = (
            db.query(User).filter(User.id == issue.assigned_to_id).first()
        )
        if assigned_user:
            show_assigned_email = False
            if current:
                if current.role.value in ["super_admin", "admin", "staff"]:
                    show_assigned_email = True
                elif assigned_user.id == current.id:
                    show_assigned_email = True
            result_dict["assigned_to"] = {
                "id": assigned_user.id,
                "name": assigned_user.name,
                "email": assigned_user.email if show_assigned_email else None,
                "role": assigned_user.role.value
                if hasattr(assigned_user.role, "value")
                else str(assigned_user.role),
            }

    return result_dict


@router.patch("/{issue_id}")
def update_issue(
    issue_id: int,
    body: IssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    from datetime import datetime

    obj = db.query(Issue).filter(Issue.id == issue_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Issue not found")

    # ---- ASSIGNMENT LOGIC ----
    if "assigned_to_id" in body.__fields_set__:
        # Only staff/admin/super_admin can assign issues (citizens blocked)
        if current_user.role not in [
            UserRole.admin,
            UserRole.super_admin,
            UserRole.staff,
        ]:
            raise HTTPException(
                status_code=403,
                detail="You are not allowed to assign issues",
            )

        if obj.status == IssueStatus.resolved:
            raise HTTPException(
                status_code=400,
                detail="Cannot assign or reassign a resolved issue",
            )

        assigned_id = body.assigned_to_id
        old_assigned_id = obj.assigned_to_id
        
        if assigned_id is not None:
            assigned_user = (
                db.query(User).filter(User.id == assigned_id).first()
            )
            if not assigned_user:
                raise HTTPException(status_code=400, detail="User not found")

            # Staff-specific rules
            if current_user.role == UserRole.staff:
                # Staff can only assign to themselves
                if assigned_id != current_user.id:
                    raise HTTPException(
                        status_code=403,
                        detail="Staff can only assign issues to themselves",
                    )

                # And only within their regions
                if obj.state_code:
                    from app.models.user_region import UserRegion

                    user_regions = (
                        db.query(UserRegion)
                        .filter(UserRegion.user_id == current_user.id)
                        .all()
                    )
                    region_codes = [ur.state_code for ur in user_regions]
                    if obj.state_code not in region_codes:
                        raise HTTPException(
                            status_code=403,
                            detail=(
                                "You can only assign issues "
                                "in your assigned regions"
                            ),
                        )

        # Apply assignment / unassignment
        
        if assigned_id is None:
            obj.assigned_to_id = None
        else:
            obj.assigned_to_id = assigned_id
            obj.updated_at = datetime.utcnow()
            try:
                db.commit()
                db.refresh(obj)
            except Exception:
                db.rollback()
                raise HTTPException(status_code=500, detail="Failed to update issue")

            background_tasks.add_task(
                _send_assignment_notifications_safe,
                issue_id=obj.id,
                assigned_id=obj.assigned_to_id,
                assigner_id=current_user.id,
                old_assigned_id=old_assigned_id,
            )

    # ---- RESPONSE ----
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

    # Creator (with email privacy)
    if obj.created_by_id:
        creator_user = (
            db.query(User).filter(User.id == obj.created_by_id).first()
        )
        if creator_user:
            show_creator_email = False
            if current_user:
                if current_user.role.value in ["super_admin", "admin", "staff"]:
                    show_creator_email = True
                elif creator_user.id == current_user.id:
                    show_creator_email = True
            out_dict["creator"] = {
                "name": creator_user.name,
                "email": creator_user.email if show_creator_email else None,
            }

    # Assigned_to (with email privacy)
    if obj.assigned_to_id:
        assigned_user = (
            db.query(User).filter(User.id == obj.assigned_to_id).first()
        )
        if assigned_user:
            show_assigned_email = False
            if current_user:
                if current_user.role.value in ["super_admin", "admin", "staff"]:
                    show_assigned_email = True
                elif assigned_user.id == current_user.id:
                    show_assigned_email = True
            out_dict["assigned_to"] = {
                "id": assigned_user.id,
                "name": assigned_user.name,
                "email": assigned_user.email if show_assigned_email else None,
                "role": assigned_user.role.value
                if hasattr(assigned_user.role, "value")
                else str(assigned_user.role),
            }

    return out_dict


@router.get("/{issue_id}/comments")
def list_comments(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    creator_id = issue.created_by_id if issue else None
    rows = db.execute(
        text(
            """
      select c.id, c.body, c.created_at, c.user_id, 
             coalesce(u.name, u.email, 'Anonymous') as author,
             u.role as user_role
      from issue_comments c left join users u on u.id=c.user_id
      where c.issue_id=:iid order by c.created_at desc
    """
        ),
        {"iid": issue_id},
    ).mappings().all()
    result = []
    for r in rows:
        user_role = r["user_role"]
        if user_role and hasattr(user_role, "value"):
            user_role_str = user_role.value
        elif user_role:
            user_role_str = str(user_role)
        else:
            user_role_str = None
        comment = {
            "id": r["id"],
            "body": r["body"],
            "created_at": r["created_at"].isoformat()
            if r["created_at"]
            else None,
            "author": r["author"],
            "user_role": user_role_str,
            "is_creator": (
                r["user_id"] == creator_id
                if creator_id and r["user_id"]
                else False
            ),
        }
        result.append(comment)
    return result


@router.post("/{issue_id}/comments")
def add_comment(
    issue_id: int,
    payload: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    if not user:
        raise HTTPException(
            status_code=401,
            detail="You must be logged in to post comments",
        )

    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if issue.status == IssueStatus.resolved:
        raise HTTPException(
            status_code=400, detail="Cannot comment on resolved issues"
        )

    body = (payload.get("body") or "").strip()
    if len(body) < 1:
        raise HTTPException(status_code=400, detail="Empty comment")
    from datetime import datetime, timezone as dt_tz

    now = datetime.now(dt_tz.utc)
    db.execute(
        text(
            "insert into issue_comments(issue_id,user_id,body,created_at) values (:i,:u,:b,:t)"
        ),
        {"i": issue_id, "u": user.id, "b": body, "t": now},
    )
    db.commit()

    background_tasks.add_task(
        _send_comment_notifications_safe,
        issue_id=issue_id,
        comment_author_id=user.id,
        comment_body=body,
    )

    # Fetch the created comment
    creator_id = issue.created_by_id
    row = db.execute(
        text(
            """
      select c.id, c.body, c.created_at, c.user_id,
             coalesce(u.name, u.email, 'Anonymous') as author,
             u.role as user_role
      from issue_comments c left join users u on u.id=c.user_id
      where c.issue_id=:iid and c.user_id=:uid and c.body=:b
      order by c.created_at desc limit 1
    """
        ),
        {"iid": issue_id, "uid": user.id, "b": body},
    ).mappings().first()
    if row:
        user_role = row["user_role"]
        if user_role and hasattr(user_role, "value"):
            user_role_str = user_role.value
        elif user_role:
            user_role_str = str(user_role)
        else:
            user_role_str = None
        return {
            "id": row["id"],
            "body": row["body"],
            "created_at": row["created_at"].isoformat()
            if row["created_at"]
            else None,
            "author": row["author"],
            "user_role": user_role_str,
            "is_creator": (
                row["user_id"] == creator_id
                if creator_id and row["user_id"]
                else False
            ),
        }
    return {"ok": True}


@router.get("/{issue_id}/related")
def get_related_issues(issue_id: int, db: Session = Depends(get_db)):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    if not issue.lat or not issue.lng:
        return []

    from math import radians, cos, sin, asin, sqrt

    def haversine(lat1, lon1, lat2, lon2):
        R = 6371000
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * asin(sqrt(a))
        return R * c

    all_issues = (
        db.query(Issue).filter(Issue.id != issue_id).all()
    )
    nearby = []
    for other in all_issues:
        if other.lat and other.lng:
            distance = haversine(
                issue.lat, issue.lng, other.lat, other.lng
            )
            if distance <= 50:
                nearby.append(
                    {
                        "id": other.id,
                        "title": other.title,
                        "status": other.status.value,
                        "category": other.category,
                        "distance_m": round(distance),
                    }
                )

    nearby.sort(key=lambda x: x["distance_m"])
    return nearby[:10]


@router.get("/{issue_id}/activity")
def get_issue_activity(
    issue_id: int, db: Session = Depends(get_db)
):
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    activities = []

    if issue.created_at:
        creator = None
        if issue.created_by_id:
            creator_user = (
                db.query(User)
                .filter(User.id == issue.created_by_id)
                .first()
            )
            creator = (
                creator_user.name
                if creator_user and creator_user.name
                else (
                    creator_user.email
                    if creator_user
                    else "Anonymous"
                )
            )
        activities.append(
            {
                "kind": "created",
                "at": issue.created_at.isoformat(),
                "user": creator,
                "comment": None,
            }
        )

    if issue.assigned_to_id:
        assigned_user = (
            db.query(User)
            .filter(User.id == issue.assigned_to_id)
            .first()
        )
        assigned_name = (
            assigned_user.name
            if assigned_user and assigned_user.name
            else (
                assigned_user.email if assigned_user else "Unknown"
            )
        )
        activities.append(
            {
                "kind": "assigned",
                "at": issue.updated_at.isoformat()
                if issue.updated_at
                else issue.created_at.isoformat(),
                "user": assigned_name,
                "comment": None,
            }
        )

    activity_records = (
        db.query(IssueActivity)
        .filter(IssueActivity.issue_id == issue_id)
        .order_by(IssueActivity.at)
        .all()
    )
    for act in activity_records:
        act_kind = (
            act.kind.value if hasattr(act.kind, "value") else str(act.kind)
        )
        # Skip "created" from IssueActivity since we already added it from issue.created_at
        if act_kind == "created":
            continue
        activities.append(
            {
                "kind": act_kind,
                "at": act.at.isoformat() if act.at else None,
                "user": None,
                "comment": None,
            }
        )

    comments = db.execute(
        text(
            """
      select c.id, c.body, c.created_at, c.user_id, 
             coalesce(u.name, u.email, 'Anonymous') as author
      from issue_comments c left join users u on u.id=c.user_id
      where c.issue_id=:iid order by c.created_at
    """
        ),
        {"iid": issue_id},
    ).mappings().all()

    for comment in comments:
        activities.append(
            {
                "kind": "comment",
                "at": comment["created_at"].isoformat()
                if comment["created_at"]
                else None,
                "user": comment["author"],
                "comment": comment["body"],
            }
        )

    activities.sort(key=lambda x: x["at"] if x["at"] else "")
    return activities


@router.post("/bulk")
def bulk_operations(
    body: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in [UserRole.admin, UserRole.super_admin]:
        raise HTTPException(
            status_code=403, detail="Only admins can perform bulk operations"
        )

    issue_ids = body.get("issue_ids", [])
    operation = body.get("operation")

    if not issue_ids or not isinstance(issue_ids, list):
        raise HTTPException(
            status_code=400,
            detail="issue_ids must be a non-empty list",
        )

    issues = db.query(Issue).filter(Issue.id.in_(issue_ids)).all()
    if len(issues) != len(issue_ids):
        raise HTTPException(
            status_code=400, detail="Some issue IDs not found"
        )

    updated_count = 0

    if operation == "assign":
        user_id = body.get("user_id")
        if user_id is not None:
            if user_id:
                user = (
                    db.query(User).filter(User.id == user_id).first()
                )
                if not user:
                    raise HTTPException(
                        status_code=400, detail="User not found"
                    )
            for issue in issues:
                issue.assigned_to_id = user_id
                issue.updated_at = datetime.now(timezone.utc)
                if user_id:
                    try:
                        db.add(
                            IssueActivity(
                                issue_id=issue.id,
                                kind=ActivityKind.assigned,
                            )
                        )
                    except Exception:
                        pass
            updated_count = len(issues)

    elif operation == "status":
        new_status = body.get("status")
        if new_status not in ["pending", "in_progress", "resolved"]:
            raise HTTPException(
                status_code=400, detail="Invalid status"
            )
        for issue in issues:
            issue.status = IssueStatus(new_status)
            issue.updated_at = datetime.now(timezone.utc)
            if new_status == "in_progress":
                issue.in_progress_at = datetime.now(timezone.utc)
                db.add(
                    IssueActivity(
                        issue_id=issue.id,
                        kind=ActivityKind.in_progress,
                    )
                )
            elif new_status == "resolved":
                issue.resolved_at = datetime.now(timezone.utc)
                db.add(
                    IssueActivity(
                        issue_id=issue.id,
                        kind=ActivityKind.resolved,
                    )
                )
        updated_count = len(issues)

    elif operation == "delete":
        for issue in issues:
            db.delete(issue)
        updated_count = len(issues)

    else:
        raise HTTPException(status_code=400, detail="Invalid operation")

    db.commit()
    return {"ok": True, "updated_count": updated_count}