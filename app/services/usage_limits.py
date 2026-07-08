# app/services/usage_limits.py

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app.services.subscriptions import serialize_user_subscription


DEFAULT_FREE_LIMITS = {
    "user_medications": 5,
    "symptom_logs": 5,
    "saved_items": 10,
    "pdf_downloads": 5,
}

SUPPORTED_USAGE_FEATURES = set(DEFAULT_FREE_LIMITS.keys())
def user_has_unlimited_usage(user: models.User) -> bool:
    if getattr(user, "role", None) == "admin":
        return True

    try:
        subscription = serialize_user_subscription(user)
        return bool(subscription.get("is_plus"))
    except Exception:
        return False


def get_free_usage_limit(db: Session, feature_key: str) -> int:
    limit_row = (
        db.query(models.UsageLimit)
        .filter(models.UsageLimit.feature_key == feature_key)
        .first()
    )

    if limit_row:
        return int(limit_row.free_limit)

    return DEFAULT_FREE_LIMITS.get(feature_key, 5)


def enforce_free_usage_limit(
    *,
    db: Session,
    user: models.User,
    feature_key: str,
    current_count: int,
    requested_count: int = 1,
    label: str,
) -> None:
    if user_has_unlimited_usage(user):
        return

    free_limit = get_free_usage_limit(db, feature_key)
    next_count = current_count + requested_count

    if next_count <= free_limit:
        return

    remaining = max(free_limit - current_count, 0)

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "message": (
                f"Free accounts can create up to {free_limit} {label}. "
                "Upgrade to SideFX Plus for unlimited access."
            ),
            "code": "FREE_LIMIT_REACHED",
            "feature_key": feature_key,
            "limit": free_limit,
            "current_count": current_count,
            "requested_count": requested_count,
            "remaining": remaining,
            "upgrade_required": True,
        },
    )

def enforce_and_increment_usage_counter(
    *,
    db: Session,
    user: models.User,
    feature_key: str,
    increment_by: int = 1,
    label: str,
) -> dict:
    """
    Use this for actions that do not naturally create a countable row.

    Example:
    - PDF downloads
    - report exports
    - AI summaries
    - generated files

    This increments the counter only for limited/free users.
    Admins and Plus users are treated as unlimited.
    """

    if user_has_unlimited_usage(user):
        return {
            "feature_key": feature_key,
            "unlimited": True,
            "current_count": None,
            "limit": None,
            "remaining": None,
        }

    counter = (
        db.query(models.UserUsageCounter)
        .filter(
            models.UserUsageCounter.user_id == user.id,
            models.UserUsageCounter.feature_key == feature_key,
        )
        .with_for_update()
        .first()
    )

    if not counter:
        counter = models.UserUsageCounter(
            user_id=user.id,
            feature_key=feature_key,
            used_count=0,
        )
        db.add(counter)
        db.flush()

    current_count = int(counter.used_count or 0)
    free_limit = get_free_usage_limit(db, feature_key)
    next_count = current_count + increment_by

    if next_count > free_limit:
        remaining = max(free_limit - current_count, 0)

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": (
                    f"Free accounts can use up to {free_limit} {label}. "
                    "Upgrade to SideFX Plus for unlimited access."
                ),
                "code": "FREE_LIMIT_REACHED",
                "feature_key": feature_key,
                "limit": free_limit,
                "current_count": current_count,
                "requested_count": increment_by,
                "remaining": remaining,
                "upgrade_required": True,
            },
        )

    counter.used_count = next_count
    counter.last_used_at = func.now()

    db.add(counter)
    db.flush()

    return {
        "feature_key": feature_key,
        "unlimited": False,
        "current_count": next_count,
        "limit": free_limit,
        "remaining": max(free_limit - next_count, 0),
    }

def get_user_usage_count(
    *,
    db: Session,
    user_id: int,
    feature_key: str,
) -> int:
    """
    Return the current usage count for a limited feature.

    Row-based features:
    - user_medications: count rows in user_medications
    - symptom_logs: count rows in symptom_logs
    - saved_items: count rows in user_saved_items

    Counter-based features:
    - pdf_downloads: count from user_usage_counters because PDF downloads do not
      naturally create a saved database row.
    """

    if feature_key == "user_medications":
        return (
            db.query(models.UserMedication)
            .filter(models.UserMedication.user_id == user_id)
            .count()
        )

    if feature_key == "symptom_logs":
        return (
            db.query(models.SymptomLog)
            .filter(models.SymptomLog.user_id == user_id)
            .count()
        )

    if feature_key == "saved_items":
        return (
            db.query(models.UserSavedItem)
            .filter(models.UserSavedItem.user_id == user_id)
            .count()
        )

    if feature_key == "pdf_downloads":
        counter = (
            db.query(models.UserUsageCounter)
            .filter(
                models.UserUsageCounter.user_id == user_id,
                models.UserUsageCounter.feature_key == feature_key,
            )
            .first()
        )

        return int(counter.used_count) if counter else 0

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": f"Unsupported usage feature: {feature_key}",
            "code": "UNSUPPORTED_USAGE_FEATURE",
            "feature_key": feature_key,
        },
    )


def get_user_usage_status(
    *,
    db: Session,
    user: models.User,
    feature_key: str,
) -> dict:
    """
    Return usage-limit display data for the current user.

    Important:
    - Free/demo users get should_show=True.
    - Admins and Plus users get should_show=False.
    - The frontend should only render usage-limit notices when should_show is True.
    """

    if feature_key not in SUPPORTED_USAGE_FEATURES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": f"Unsupported usage feature: {feature_key}",
                "code": "UNSUPPORTED_USAGE_FEATURE",
                "feature_key": feature_key,
            },
        )

    if user_has_unlimited_usage(user):
        return {
            "feature_key": feature_key,
            "unlimited": True,
            "should_show": False,
            "current_count": None,
            "limit": None,
            "remaining": None,
            "limit_reached": False,
        }

    current_count = get_user_usage_count(
        db=db,
        user_id=user.id,
        feature_key=feature_key,
    )

    free_limit = get_free_usage_limit(db, feature_key)

    return {
        "feature_key": feature_key,
        "unlimited": False,
        "should_show": True,
        "current_count": current_count,
        "limit": free_limit,
        "remaining": max(free_limit - current_count, 0),
        "limit_reached": current_count >= free_limit,
    }