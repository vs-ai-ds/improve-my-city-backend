# File: app/core/security.py
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import time, jwt
from app.core.config import settings
from passlib.hash import bcrypt_sha256
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.user import User  # adjust import if your model path differs


ALGO = "HS256"
ACCESS_TTL = 15 * 60
REFRESH_TTL = 7 * 24 * 3600
bearer = HTTPBearer(auto_error=False) 


def hash_password(raw: str) -> str:
    return bcrypt_sha256.hash(raw)

def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt_sha256.verify(raw, hashed)

def _make_token(sub: str, role: str, ttl: int) -> str:
    now = int(time.time())
    payload = {"sub": sub, "role": role, "iat": now, "exp": now + ttl}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGO)

def make_tokens(email: str, role: str) -> dict:
    return {
        "access_token": _make_token(email, role, ACCESS_TTL),
        "refresh_token": _make_token(email, role, REFRESH_TTL),
        "token_type": "bearer",
        "expires_in": ACCESS_TTL,
    }

def get_current_user(
    creds = Depends(bearer),  # reuse your existing 'bearer = HTTPBearer(auto_error=False)'
    db: Session = Depends(get_db),
):
    token = creds.credentials if creds else None
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")
    return user

def require_verified_user(user=Depends(get_current_user)):
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email_not_verified")
    return user


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
        return {"email": payload["sub"], "role": payload["role"]}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_optional_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer)):
    if not creds:
        return None
    token = creds.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[ALGO])
        return {"email": payload["sub"], "role": payload["role"]}
    except Exception:
        # treat bad token same as anonymous for optional flow
        return None

def require_role(*roles):
    def _dep(user=Depends(get_current_user)):
        if user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user
    return _dep