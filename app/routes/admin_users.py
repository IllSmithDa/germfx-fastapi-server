from __future__ import annotations

import hmac
import os
import re
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User
from app.core.auth import get_authenticated_user, get_optional_user
from app.util.security import canonicalize_email, hash_email


router = APIRouter()


AllowedRole = Literal["user", "admin"]


class AssignUserRoleRequest(BaseModel):
    role: AllowedRole = "admin"

    user_id: Optional[int] = None
    username: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=320)

    reason: Optional[str] = Field(default=None, max_length=300)


class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    account_status: str | None = None


class AdminStatusOut(BaseModel):
    is_admin: bool
    role: str
    user_id: int
    username: str


def _looks_like_email(value: str) -> bool:
    return bool(
        re.match(
            r"[^@]+@[^@]+\.[^@]+",
            value.strip(),
        )
    )


def _get_admin_bootstrap_token() -> str | None:
    """
    Read this at request time instead of module import time.

    This makes local dev less confusing if you add/change the env var and
    restart behavior is inconsistent.
    """
    token = os.getenv("ADMIN_BOOTSTRAP_TOKEN")

    if not token:
        return None

    return token.strip()


def _has_valid_bootstrap_token(
    x_admin_bootstrap_token: str | None,
) -> bool:
    expected_token = _get_admin_bootstrap_token()

    if not expected_token:
        return False

    if not x_admin_bootstrap_token:
        return False

    return hmac.compare_digest(
        x_admin_bootstrap_token.strip(),
        expected_token,
    )


def require_admin(
    current_user: User = Depends(get_authenticated_user),
) -> User:
    """
    Strict admin dependency for normal admin tools.

    Use this for routes like:
    - UPC/NDC curation
    - admin dashboards
    - admin-only mutation routes

    This does NOT allow bootstrap-token access.
    """
    # print("got current user role: ", current_user.role)
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


def require_admin_or_bootstrap(
    current_user: User | None = Depends(get_optional_user),
    x_admin_bootstrap_token: str | None = Header(
        default=None,
        alias="X-Admin-Bootstrap-Token",
    ),
) -> User | None:
    """
    Allows either:
    1. Existing admin user via normal auth cookie/bearer token.
    2. Bootstrap token via ADMIN_BOOTSTRAP_TOKEN.

    Use this only for role assignment/bootstrap routes.
    """
    if current_user and getattr(current_user, "role", "user") == "admin":
        return current_user

    if _has_valid_bootstrap_token(x_admin_bootstrap_token):
        return None

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Admin access required",
    )


def _find_user_for_role_assignment(
    db: Session,
    payload: AssignUserRoleRequest,
) -> User:
    supplied = [
        payload.user_id is not None,
        bool(payload.username and payload.username.strip()),
        bool(payload.email and payload.email.strip()),
    ]

    if sum(supplied) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of user_id, username, or email.",
        )

    if payload.user_id is not None:
        user = db.get(User, payload.user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    if payload.username:
        username = payload.username.strip()

        user = db.execute(
            select(User).where(
                func.lower(User.username) == username.lower()
            )
        ).scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    if payload.email:
        email = canonicalize_email(payload.email)

        if not _looks_like_email(email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid email format.",
            )

        email_hash = hash_email(email)

        user = db.execute(
            select(User).where(
                User.email_hash == email_hash
            )
        ).scalars().first()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

        return user

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Missing user lookup value.",
    )


@router.patch(
    "/users/assign-role",
    response_model=AdminUserOut,
)
def assign_user_role(
    payload: AssignUserRoleRequest,
    db: Session = Depends(get_db),
    acting_admin: User | None = Depends(require_admin_or_bootstrap),
):
    """
    Assign a user role by user_id, username, or email.

    Bootstrap usage:
    PATCH /api/admin/users/assign-role
    Header: X-Admin-Bootstrap-Token: <ADMIN_BOOTSTRAP_TOKEN>

    Normal admin usage:
    authenticated admin cookie/bearer token.

    After your first admin is assigned, remove ADMIN_BOOTSTRAP_TOKEN from
    production/Render unless you intentionally need emergency bootstrap access.
    """
    
    user = _find_user_for_role_assignment(
        db,
        payload,
    )

    user.role = payload.role

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "is_active": user.is_active,
        "account_status": getattr(user, "account_status", None),
    }


@router.get(
    "/users/me/admin-status",
    response_model=AdminStatusOut,
)
def get_my_admin_status(
    current_user: User = Depends(require_admin),
):
    """
    Verify that the currently authenticated account has real admin access.

    Unlike assign-role, this route does not accept the bootstrap token.
    Use this to confirm your logged-in admin account works normally.
    """
    # print("current role: ", current_user.role)
    return {
        "is_admin": True,
        "role": getattr(current_user, "role", "user"),
        "user_id": current_user.id,
        "username": current_user.username,
    }