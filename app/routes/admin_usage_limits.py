# app/routers/admin_usage_limits.py

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import models
from app.core.auth import get_authenticated_user
from app.db import get_db

router = APIRouter(
  tags=["usage-limits"],
)

'''
Use this to seed default limits directly into the database if necessary. 

INSERT INTO usage_limits (feature_key, free_limit, description)
VALUES
  (
    'user_medications',
    5,
    'Maximum number of user medication records free users can create. Plus users and admins are not limited.'
  ),
  (
    'symptom_logs',
    5,
    'Maximum number of symptom log records free users can create. Plus users and admins are not limited.'
  ),
  (
    'saved_items',
    10,
    'Maximum total saved news and recall items free users can save. This is a combined limit across news and recalls. Plus users and admins are not limited.'
  ),
  ( 
    'pdf_downloads',
    5,
    'Maximum total PDF downloads for free/demo users. Plus users and admins are not limited.'
  )
ON CONFLICT (feature_key)
DO UPDATE SET
  free_limit = EXCLUDED.free_limit,
  description = EXCLUDED.description,
  updated_at = now();

'''

DEFAULT_USAGE_LIMIT_SEEDS = [
    {
        "feature_key": "user_medications",
        "free_limit": 5,
        "description": (
            "Maximum number of user medication records free users can create. "
            "Plus users and admins are not limited."
        ),
    },
    {
        "feature_key": "symptom_logs",
        "free_limit": 5,
        "description": (
            "Maximum number of symptom log records free users can create. "
            "Plus users and admins are not limited."
        ),
    },
    {
        "feature_key": "saved_items",
        "free_limit": 10,
        "description": (
            "Maximum total saved news and recall items free users can save. "
            "This is a combined limit across news and recalls. "
            "Plus users and admins are not limited."
        ),
    },
    {
        "feature_key": "pdf_downloads",
        "free_limit": 5,
        "description": (
            "Maximum total PDF downloads for free/demo users. "
            "Plus users and admins are not limited."
        ),
    },
]

class UsageLimitUpdateRequest(BaseModel):
    free_limit: int = Field(..., ge=0, le=100_000)
    description: str | None = Field(default=None, max_length=255)


def require_admin(
    current_user: models.User = Depends(get_authenticated_user),
) -> models.User:
    if getattr(current_user, "role", None) != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )

    return current_user


@router.get("")
def list_usage_limits(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    rows = (
        db.query(models.UsageLimit)
        .order_by(models.UsageLimit.feature_key.asc())
        .all()
    )

    return {
        "items": [
            {
                "id": row.id,
                "feature_key": row.feature_key,
                "free_limit": row.free_limit,
                "description": row.description,
                "updated_by_user_id": row.updated_by_user_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.post("/seed-defaults")
def seed_default_usage_limits(
    overwrite: bool = Query(
        False,
        description=(
            "If false, only missing usage-limit rows are created. "
            "If true, existing rows are reset to the current default values."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    """
    Seed default free-tier usage limits.

    Purpose:
    - Ensures the usage_limits table has editable rows for admin UI.
    - Protects the database from unlimited free/demo usage.
    - Keeps limits configurable without changing code later.

    Seeded limits:
    - user_medications: 5
    - symptom_logs: 5
    - saved_items: 10 combined saved news/recall items
    - pdf_downloads: 5 total PDF downloads

    Notes:
    - This does NOT create fake user medications.
    - This does NOT create fake symptom logs.
    - This does NOT create fake saved news/recall items.
    - This does NOT create fake PDF downloads.
    - This does NOT reset per-user PDF usage counters.
    - It only creates/updates configuration rows in usage_limits.
    """

    results: list[dict[str, Any]] = []

    for seed in DEFAULT_USAGE_LIMIT_SEEDS:
        feature_key = seed["feature_key"]

        row = (
            db.query(models.UsageLimit)
            .filter(models.UsageLimit.feature_key == feature_key)
            .first()
        )

        if row:
            if overwrite:
                row.free_limit = seed["free_limit"]
                row.description = seed["description"]
                row.updated_by_user_id = current_user.id

                results.append(
                    {
                        "feature_key": feature_key,
                        "action": "updated",
                        "free_limit": row.free_limit,
                    }
                )
            else:
                results.append(
                    {
                        "feature_key": feature_key,
                        "action": "already_exists",
                        "free_limit": row.free_limit,
                    }
                )

            continue

        row = models.UsageLimit(
            feature_key=feature_key,
            free_limit=seed["free_limit"],
            description=seed["description"],
            updated_by_user_id=current_user.id,
        )

        db.add(row)

        results.append(
            {
                "feature_key": feature_key,
                "action": "created",
                "free_limit": seed["free_limit"],
            }
        )

    db.commit()

    return {
        "message": "Usage limits seeded successfully.",
        "overwrite": overwrite,
        "items": results,
    }


@router.patch("/{feature_key}")
def update_usage_limit(
    feature_key: str,
    payload: UsageLimitUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin),
):
    row = (
        db.query(models.UsageLimit)
        .filter(models.UsageLimit.feature_key == feature_key)
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usage limit not found for feature_key: {feature_key}",
        )

    row.free_limit = payload.free_limit

    if payload.description is not None:
        row.description = payload.description

    row.updated_by_user_id = current_user.id

    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "message": "Usage limit updated successfully.",
        "item": {
            "id": row.id,
            "feature_key": row.feature_key,
            "free_limit": row.free_limit,
            "description": row.description,
            "updated_by_user_id": row.updated_by_user_id,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        },
    }