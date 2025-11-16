# app/core/security.py
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import time, jwt
from datetime import timedelta
from sqlalchemy.orm import Session
from app.core.config import settings
from passlib.hash import bcrypt_sha256
from app.db.session import get_db
from app.models.user import User

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

def _decode_token(creds: Optional[HTTPAuthorizationCredentials]) -> dict:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        return jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    payload = _decode_token(creds)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="user_inactive")
    return user

def get_optional_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
                      db: Session = Depends(get_db)) -> Optional[User]:
    if not creds:
        return None
    try:
        payload = jwt.decode(creds.credentials, settings.jwt_secret, algorithms=[ALGO])
        email = payload.get("sub")
        if not email:
            return None
        return db.query(User).filter(User.email == email).first()
    except Exception:
        return None

def require_role(*roles):
    from app.models.user import UserRole
    role_values = [r.value if isinstance(r, UserRole) else r for r in roles]
    def _dep(user: User = Depends(get_current_user)):
        if user.role.value not in role_values:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
        return user
    return _dep

def require_verified_user(user: User = Depends(get_current_user)):
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="email_not_verified")
    return user