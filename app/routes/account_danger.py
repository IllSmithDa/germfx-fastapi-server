# app/routes/account_danger.py
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import models
from app.db import get_db
from app.core.auth import get_authenticated_user
from app.schemas.users import ConfirmPasswordRequest
from app.util.security import verify_password

router = APIRouter(tags=["account-danger"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_PATH = "/"


@router.post("/deactivate-account", status_code=status.HTTP_200_OK)
def deactivate_account(
    payload: ConfirmPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if hasattr(current_user, "is_active"):
        current_user.is_active = False

    if hasattr(current_user, "deactivated_at"):
        current_user.deactivated_at = datetime.now(timezone.utc)

    if hasattr(current_user, "account_status"):
        current_user.account_status = "deactivated"
    
    if hasattr(current_user, "suspension_reason"):
        current_user.suspension_reason = None
    
    if hasattr(current_user, "suspended_at"):
        current_user.suspended_at = None

    if hasattr(current_user, "token_version"):
        current_user.token_version += 1

    db.add(current_user)
    db.commit()

    response.delete_cookie(key=ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH)

    return {"message": "Account deactivated successfully."}


@router.delete("/delete-account", status_code=status.HTTP_200_OK)
def delete_account(
    payload: ConfirmPasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    if hasattr(current_user, "token_version"):
        current_user.token_version += 1

    db.delete(current_user)
    db.commit()

    response.delete_cookie(key=ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH)

    return {"message": "Account deleted successfully."}