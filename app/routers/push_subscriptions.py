# File: app/routers/push_subscriptions.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User
from app.models.push import PushSubscription

router = APIRouter(prefix="/push", tags=["push"])

@router.post("/subscribe")
def subscribe(sub: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    u = db.query(User).filter(User.email == user["email"]).first()
    if not u: raise HTTPException(401, "Unauthorized")
    endpoint = sub.get("endpoint"); keys = (sub.get("keys") or {})
    if not (endpoint and keys.get("p256dh") and keys.get("auth")):
        raise HTTPException(400, "Bad subscription")
    # upsert by endpoint
    existing = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
    if existing:
        existing.user_id = u.id; existing.p256dh = keys["p256dh"]; existing.auth = keys["auth"]
    else:
        db.add(PushSubscription(user_id=u.id, endpoint=endpoint, p256dh=keys["p256dh"], auth=keys["auth"]))
    db.commit()
    return {"ok": True}

@router.post("/unsubscribe")
def unsubscribe(sub: dict, db: Session = Depends(get_db), user=Depends(get_current_user)):
    endpoint = sub.get("endpoint")
    if endpoint:
        db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).delete()
        db.commit()
    return {"ok": True}