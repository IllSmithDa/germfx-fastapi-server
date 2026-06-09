from __future__ import annotations

from app.schemas.user_settings import UserSettingsResponse, UserSettingsUpdateRequest
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.auth import get_authenticated_user
from app.models import User
from app.services.user_settings import (
    get_or_create_user_settings,
    reset_user_settings,
    serialize_user_settings,
    update_user_settings,
)

router = APIRouter(tags=["user-settings"])


@router.get("", response_model=UserSettingsResponse)
def read_user_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    settings = get_or_create_user_settings(db, user_id=current_user.id)
    return serialize_user_settings(settings)


@router.patch("", response_model=UserSettingsResponse)
def patch_user_settings(
    payload: UserSettingsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    print("updated user settings: ", payload)
    try:
        settings = update_user_settings(
            db,
            user_id=current_user.id,
            theme=payload.theme,
            default_report_range=payload.default_report_range,
            top_symptom_limit=payload.top_symptom_limit,
            remember_last_medication=payload.remember_last_medication,
            recent_suggestions_first=payload.recent_suggestions_first,
            default_recall_state=payload.default_recall_state,
            default_recall_type=payload.default_recall_type,
        )
        return serialize_user_settings(settings)

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.post("/reset", response_model=UserSettingsResponse)
def reset_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    settings = reset_user_settings(db, user_id=current_user.id)
    return serialize_user_settings(settings)