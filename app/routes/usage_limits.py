from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import models
from app.core.auth import get_authenticated_user
from app.db import get_db
from app.services.usage_limits import (
    SUPPORTED_USAGE_FEATURES,
    get_user_usage_status,
)

router = APIRouter(tags=["usage-limits"])


@router.get("")
def get_my_usage_limits(
    feature_key: str | None = Query(None, min_length=1, max_length=80),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    user = db.get(models.User, current_user.id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if feature_key:
        return get_user_usage_status(
            db=db,
            user=user,
            feature_key=feature_key,
        )

    items = [
        get_user_usage_status(
            db=db,
            user=user,
            feature_key=key,
        )
        for key in sorted(SUPPORTED_USAGE_FEATURES)
    ]

    return {
        "items": items,
        "total": len(items),
    }