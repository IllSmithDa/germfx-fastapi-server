from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app import models
from app.db import get_db
from app.schemas.users import ReactivateAccountRequest
from app.util.security import verify_password
from app.core.auth import create_access_token, create_refresh_token
from app.util.security import canonicalize_email, hash_email

router = APIRouter(tags=["account-recovery"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/"
COOKIE_SECURE = False  # replace with your config
COOKIE_SAMESITE = "lax"  # replace with your config
ACCESS_MAX_AGE = 60 * 60
REFRESH_MAX_AGE = 30 * 24 * 60 * 60


@router.post("/reactivate-account", status_code=status.HTTP_200_OK)
def reactivate_account(
    payload: ReactivateAccountRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    identifier = payload.identifier.strip()

    user = None

    # Adjust this logic if you already have a shared "find by identifier" helper
    if "@" in identifier:

        normalized_email = canonicalize_email(identifier)
        email_hash = hash_email(normalized_email)

        user = db.execute(
            select(models.User).where(models.User.email_hash == email_hash)
        ).scalars().first()
    else:

        user = db.execute(
            select(models.User).where(func.lower(models.User.username) == identifier.lower())
        ).scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found",
        )

    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid credentials",
        )

    if getattr(user, "account_status", "active") == "suspended":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been suspended and cannot be reactivated here.",
        )

    if user.is_active and getattr(user, "account_status", "active") == "active":
        return {"message": "Account is already active."}

    user.is_active = True
    user.account_status = "active"

    if hasattr(user, "deactivated_at"):
        user.deactivated_at = None

    if hasattr(user, "suspended_at"):
        user.suspended_at = None

    if hasattr(user, "suspension_reason"):
        user.suspension_reason = None

    if hasattr(user, "token_version"):
        user.token_version += 1

    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token({
        "sub": str(user.id),
        "tv": user.token_version,
    })
    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "tv": user.token_version,
    })

    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_MAX_AGE,
        path=COOKIE_PATH,
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_MAX_AGE,
        path=COOKIE_PATH,
    )

    return {"message": "Account reactivated successfully."}