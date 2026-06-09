# app/core/auth.py
from datetime import datetime, timedelta, timezone
from typing import Optional  # ← add timezone
from jose import jwt, JWTError
from fastapi import HTTPException, status, Cookie, Depends, Header
from sqlalchemy.orm import Session
from app.util.security import verify_password, hash_email
from app import models
from app.db import get_db
from sqlalchemy import select
import os, re
from app.core.auth_config import ACCESS_TOKEN_SECONDS, REFRESH_TOKEN_SECONDS

# Move secret to env (fallback only for local/dev)
SECRET_KEY = os.getenv("JWT_SECRET", "dev-only-secret-change-me")
ALGORITHM = "HS256"


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    exp = now + (expires_delta or timedelta(seconds=ACCESS_TOKEN_SECONDS))
    to_encode.update({"exp": exp, "iat": now, "type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    now = datetime.now(timezone.utc)
    exp = now + timedelta(seconds=REFRESH_TOKEN_SECONDS)
    to_encode = data.copy()
    to_encode.update({"exp": exp, "iat": now, "type": "refresh"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str, token_type: str = "access") -> dict:
    """
    Decodes and validates the token and (optionally) enforces the expected token_type.
    token_type: "access" or "refresh"
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        t = payload.get("type")  # may be missing on legacy tokens

        if token_type == "refresh":
            if t != "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")
        else:  # token_type == "access"
            if t == "refresh":
                raise HTTPException(status_code=401, detail="Invalid token type")

        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def verify_user(identifier: str, password: str, db: Session) -> models.User:
    """
    Verify that the user exists by either email or username, and that their password matches.
    - If `identifier` looks like an email, use hashed email lookup
    - Otherwise, treat it as a username.
    """
    is_email = bool(re.match(r"[^@]+@[^@]+\.[^@]+", identifier))

    if is_email:
        email_hash = hash_email(identifier)
        query = select(models.User).where(models.User.email_hash == email_hash)
    else:
        query = select(models.User).where(models.User.username == identifier)

    user = db.execute(query).scalars().first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "message": "Invalid username/email or password.",
                "code": "INVALID_CREDENTIALS",
            },
        )

    print("verify_user: authenticated user:", user.username)
    return user

def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


def get_authenticated_user(
    access_token: str | None = Cookie(default=None, alias="access_token"),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> models.User:
    """
    Supports both:
    - Web auth via HttpOnly access_token cookie
    - Mobile auth via Authorization: Bearer <access_token>
    """
    bearer_token = _extract_bearer_token(authorization)
    token = bearer_token or access_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    payload = verify_token(token, token_type="access")
    user_id = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.get(models.User, int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    token_version = payload.get("tv")

    try:
        token_version = int(token_version)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if token_version != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token revoked",
        )

    return user


def get_optional_user(
    access_token: Optional[str] = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db),
):
    if not access_token:
        return None

    try:
        return get_authenticated_user(access_token=access_token, db=db)
    except Exception:
        return None
    

