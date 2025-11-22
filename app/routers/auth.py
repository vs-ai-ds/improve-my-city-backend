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
import random, string
from datetime import datetime, timezone, timedelta
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

    code = ''.join(random.choices(string.digits, k=6))
    user.email_verify_code = code
    user.email_verify_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=60)
    db.commit()
    try:
        send_email_verification(user.email, make_email_token(user.email, "verify"), code=code)
    except Exception as e:
        import logging
        logging.error(f"Failed to send verification email: {e}", exc_info=True)

    # Sign-in immediately
    return make_tokens(user.email, user.role.value)

@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.hashed_password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Your account has been deactivated. Please contact support.")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Please verify your email address before signing in. Check your inbox for the verification link or code.")
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
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Verification link has expired. Please request a new one.")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid verification link. Please check the link or request a new one.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_verified:
        return {"ok": True, "message": "Email already verified"}

    user.is_verified = True
    user.email_verify_code = None
    user.email_verify_expires_at = None
    db.commit()
    return {"ok": True, "message": "Email verified successfully"}

@router.post("/forgot")
def forgot(body: EmailOnly, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if user:
        try:
            from app.services.notify_email import send_reset_password
            send_reset_password(user.email, make_email_token(user.email, "reset"))
        except Exception as e:
            import logging
            logging.error(f"Failed to send reset password email: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Failed to send reset password email. Please try again later.")
    return {"ok": True, "message": "If an account exists with this email, a password reset link has been sent."}

@router.post("/reset")
def reset(body: ResetIn, db: Session = Depends(get_db)):
    try:
        email = parse_email_token(body.token, "reset")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Password reset link has expired. Please request a new one.")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset link. Please request a new password reset.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated. Please contact support.")

    user.hashed_password = hash_password(body.password)
    db.commit()
    return {"ok": True, "message": "Password reset successfully. You can now sign in with your new password."}

@router.post("/send-verify")
def send_verify(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return {"ok": True, "message": "If an account exists with this email, a verification email has been sent."}
    
    if user.is_verified:
        return {"ok": True, "message": "Email is already verified."}
    
    code = ''.join(random.choices(string.digits, k=6))
    user.email_verify_code = code
    user.email_verify_expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=60)
    db.commit()
    
    try:
        link_token = make_email_token(user.email, "verify")
        send_email_verification(user.email, link_token, code=code)
        return {"ok": True, "message": "Verification email sent. Check your inbox for the code and link."}
    except Exception as e:
        import logging
        logging.error(f"Failed to send verification email: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send verification email. Please try again later.")

@router.post("/verify-code")
def verify_code(email: str, code: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_verified:
        return {"ok": True, "message": "Email is already verified."}
    
    if not user.email_verify_code or not user.email_verify_expires_at:
        raise HTTPException(status_code=400, detail="No verification code found. Please request a new verification code.")
    
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    expires_at = user.email_verify_expires_at
    
    if expires_at and now > expires_at:
        raise HTTPException(status_code=400, detail="Verification code has expired. Please request a new one.")
    
    if user.email_verify_code != code.strip():
        raise HTTPException(status_code=400, detail="Invalid verification code. Please check and try again.")
    
    user.is_verified = True
    user.email_verify_code = None
    user.email_verify_expires_at = None
    db.commit()
    return {"ok": True, "message": "Email verified successfully. You can now sign in."}

