import datetime as dt
import hashlib
import os
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from .config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HOURS
from .db.database import get_db
from .db.models import User, MSME

security = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"):
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        if ":" in hashed_password:
            # Legacy salt:sha256 format
            salt, hashed = hashed_password.split(":", 1)
            check = hashlib.sha256((salt + plain_password).encode()).hexdigest()
            return check == hashed
        return False
    except Exception:
        return False

def needs_rehash(hashed_password: str) -> bool:
    """Returns True if the stored hash is in the legacy salt:sha256 format."""
    return not (hashed_password.startswith("$2b$") or hashed_password.startswith("$2a$"))

def create_access_token(data: dict, expires_delta: dt.timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = dt.datetime.now(dt.timezone.utc) + expires_delta
    else:
        expire = dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=JWT_EXPIRATION_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except Exception:
        return None

def get_current_user_optional(
    auth: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db)
) -> User | None:
    if not auth or not auth.credentials:
        return None
    payload = decode_access_token(auth.credentials)
    if not payload or "sub" not in payload:
        return None
    user = db.query(User).filter(User.username == payload["sub"]).first()
    return user

def get_current_user(
    user: User | None = Depends(get_current_user_optional)
) -> User:
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
