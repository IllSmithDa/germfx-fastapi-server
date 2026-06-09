from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import UserSettings


VALID_THEMES = {"system", "light", "dark"}
VALID_REPORT_RANGES = {"7d", "30d", "90d", "all"}
VALID_RECALL_STATES = {
    "all", "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA",
    "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY",
    "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
    "UT", "VT", "VA", "WA", "WV", "WI", "WY",
}
VALID_RECALL_TYPES = {"all", "food", "drug"}

def serialize_user_settings(settings: UserSettings) -> Dict[str, Any]:
    return {
        "id": settings.id,
        "user_id": settings.user_id,
        "theme": settings.theme,
        "default_report_range": settings.default_report_range,
        "top_symptom_limit": settings.top_symptom_limit,
        "remember_last_medication": settings.remember_last_medication,
        "recent_suggestions_first": settings.recent_suggestions_first,
        "default_recall_state": settings.default_recall_state,
        "created_at": settings.created_at,
        "updated_at": settings.updated_at,
        "default_recall_type": settings.default_recall_type,
    }


def get_or_create_user_settings(db: Session, *, user_id: int) -> UserSettings:
    settings = (
        db.query(UserSettings)
        .filter(UserSettings.user_id == user_id)
        .first()
    )

    if settings:
        return settings

    settings = UserSettings(user_id=user_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)

    return settings


def _validate_theme(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    if value not in VALID_THEMES:
        raise ValueError("Invalid theme")

    return value


def _validate_report_range(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    if value not in VALID_REPORT_RANGES:
        raise ValueError("Invalid default_report_range")

    return value


def _validate_top_symptom_limit(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None

    if value not in {5, 10, 15}:
        raise ValueError("Invalid top_symptom_limit")

    return value


def _validate_recall_state(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = value.upper() if value.lower() != "all" else "all"

    if normalized not in VALID_RECALL_STATES:
        raise ValueError("Invalid default_recall_state")

    return normalized

def _validate_recall_type(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None

    normalized = value.lower()

    if normalized in {"medication", "medicine"}:
        normalized = "drug"

    if normalized not in VALID_RECALL_TYPES:
        raise ValueError("Invalid default_recall_type")

    return normalized

def update_user_settings(
    db: Session,
    *,
    user_id: int,
    theme: Optional[str] = None,
    default_report_range: Optional[str] = None,
    top_symptom_limit: Optional[int] = None,
    remember_last_medication: Optional[bool] = None,
    recent_suggestions_first: Optional[bool] = None,
    default_recall_state: Optional[str] = None,
    default_recall_type: Optional[str] = None,
) -> UserSettings:
    settings = get_or_create_user_settings(db, user_id=user_id)

    if theme is not None:
        settings.theme = _validate_theme(theme)

    if default_report_range is not None:
        settings.default_report_range = _validate_report_range(default_report_range)

    if top_symptom_limit is not None:
        settings.top_symptom_limit = _validate_top_symptom_limit(top_symptom_limit)

    if remember_last_medication is not None:
        settings.remember_last_medication = remember_last_medication

    if recent_suggestions_first is not None:
        settings.recent_suggestions_first = recent_suggestions_first

    if default_recall_state is not None:
        settings.default_recall_state = _validate_recall_state(default_recall_state)
    
    if default_recall_type is not None:
        settings.default_recall_type = _validate_recall_type(default_recall_type)

    db.commit()
    db.refresh(settings)

    return settings


def reset_user_settings(db: Session, *, user_id: int) -> UserSettings:
    settings = get_or_create_user_settings(db, user_id=user_id)

    settings.theme = "system"
    settings.default_report_range = "30d"
    settings.top_symptom_limit = 10
    settings.remember_last_medication = False
    settings.recent_suggestions_first = True
    settings.default_recall_state = "all"
    settings.default_recall_type = "all"
    
    db.commit()
    db.refresh(settings)

    return settings