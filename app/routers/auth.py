# File: app/routers/auth.py

from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import RegisterIn, LoginIn, TokenPair, EmailOnly, ResetIn
from app.core.security import hash_password, verify_password, make_tokens, get_current_user
from app.core.config import settings
import time, jwt
from app.services.notify_email import send_email_verification
import random, string, datetime as dt 
from datetime import datetime, timezone
from app.core.security import require_verified_user

router = APIRouter(prefix="/auth", tags=["auth"])

# Simple email verification / reset tokens using JWT
EMAIL_TTL = 3600
def make_email_token(email: str, purpose: str):
    return jwt.encode(
        {"sub": email, "purpose": purpose, "exp": int(time.time()) + EMAIL_TTL},
        settings.jwt_secret,
        algorithm="HS256",
    )

def parse_email_token(token: str, purpose: str):
    data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if data.get("purpose") != purpose:
        raise Exception("bad purpose")
    return data["sub"]

@router.post("/register", response_model=TokenPair)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    # Ensure unique email
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        email=body.email,
        name=body.name,                    # <-- store name
        hashed_password=hash_password(body.password),
        role=UserRole.citizen,
        mobile=body.mobile,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Send verification email (link)
    try:
        send_email_verification(user.email, make_email_token(user.email, "verify"))
    except Exception:
        pass

    # Sign-in immediately
    return make_tokens(user.email, user.role.value)

@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Inactive user")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email to sign in")
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    return make_tokens(user.email, user.role.value)

@router.get("/me")
def me(current = Depends(get_current_user)):
    return {
        "id": current.id,
        "email": current.email,
        "role": current.role,
        "is_verified": current.is_verified,
        "is_active": current.is_active,
        "name": getattr(current, "name", None),
        "mobile": getattr(current, "mobile", None),
    }

@router.put("/profile")
def update_profile(
    payload: dict = Body(...),
    user = Depends(require_verified_user),
    db: Session = Depends(get_db)
):
    name = (payload.get("name") or "").strip()
    mobile = (payload.get("mobile") or "").strip() or None
    if len(name) < 2:
      raise HTTPException(status_code=400, detail="Name too short")
    user.name = name
    user.mobile = mobile
    db.commit(); db.refresh(user)
    return {"ok": True}

@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
    try:
        email = parse_email_token(token, "verify")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid/expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.is_verified = True
    db.commit()
    return {"ok": True}

@router.post("/forgot")
def forgot(body: EmailOnly, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    # Don't reveal if email exists
    if user:
        try:
            from app.services.notify_email import send_reset_password
            send_reset_password(user.email, make_email_token(user.email, "reset"))
        except Exception:
            pass
    return {"ok": True}

@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    try:
        email = parse_email_token(body.token, "reset")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid/expired token")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(body.password)
    db.commit()
    return {"ok": True}

@router.post("/send-verify")
def send_verify(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"ok": True}
    code = ''.join(random.choices(string.digits, k=6))
    user.email_verify_code = code
    user.email_verify_expires_at = dt.datetime.utcnow() + dt.timedelta(minutes=60)
    db.commit()
    # Also send link token, using the same token maker
    link_token = make_email_token(user.email, "verify")
    send_email_verification(user.email, link_token)
    return {"ok": True}

@router.post("/verify-code")
def verify_code(email: str, code: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(404, "User not found")
    if not user.email_verify_code or not user.email_verify_expires_at:
        raise HTTPException(400, "No verification code")
    if dt.datetime.utcnow() > user.email_verify_expires_at:
        raise HTTPException(400, "Code expired")
    if user.email_verify_code != code:
        raise HTTPException(400, "Invalid code")
    user.is_verified = True          # <-- fix field name
    user.email_verify_code = None
    user.email_verify_expires_at = None
    db.commit()
    return {"ok": True}