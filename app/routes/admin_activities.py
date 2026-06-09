from datetime import datetime, timezone

from app.schemas.admin import AdminReactivateAccountRequest, AdminSuspendAccountRequest
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import models
from app.db import get_db

router = APIRouter(tags=["account-recovery"])

def get_current_admin_user():
    # Placeholder for future admin auth/authorization
    raise NotImplementedError("Admin auth not implemented yet")


@router.post("/suspend-account", status_code=status.HTTP_200_OK)
def admin_suspend_account(
    payload: AdminSuspendAccountRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user),  # future use
):
    user = db.execute(
        select(models.User).where(models.User.id == payload.user_id)
    ).scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user.is_active = False
    user.account_status = "suspended"

    if hasattr(user, "suspended_at"):
        user.suspended_at = datetime.now(datetime.timezone.utc)

    if hasattr(user, "suspension_reason"):
        user.suspension_reason = payload.reason

    if hasattr(user, "token_version"):
        user.token_version += 1

    db.add(user)
    db.commit()

    return {"message": "Account suspended successfully."}


@router.post("/reactivate-account", status_code=status.HTTP_200_OK)
def admin_reactivate_account(
    payload: AdminReactivateAccountRequest,
    db: Session = Depends(get_db),
    admin_user = Depends(get_current_admin_user),  # future use
):
    user = db.execute(
        select(models.User).where(models.User.id == payload.user_id)
    ).scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

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

    return {"message": "Account reactivated successfully by admin."}