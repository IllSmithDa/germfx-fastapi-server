from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import User, UserSubscription


PAID_STATUSES = {"active", "trialing"}
PLUS_PLANS = {"plus", "pro"}


def _as_aware_utc(value):
    if not value:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def user_has_plus(user: User) -> bool:
    sub = getattr(user, "subscription", None)

    if not sub:
        return False

    if getattr(sub, "plan", "free") not in PLUS_PLANS:
        return False

    status = getattr(sub, "status", "free")

    if status in PAID_STATUSES:
        return True

    period_end = _as_aware_utc(getattr(sub, "current_period_end", None))

    if period_end and status in {"canceled"}:
        return period_end > datetime.now(timezone.utc)

    return False


def serialize_user_subscription(user: User) -> dict:
    sub = getattr(user, "subscription", None)

    if not sub:
        return {
            "plan": "free",
            "status": "free",
            "provider": "manual",
            "is_plus": False,
            "is_active_paid": False,
            "current_period_start": None,
            "current_period_end": None,
            "cancel_at_period_end": False,
        }

    is_plus = user_has_plus(user)

    return {
        "plan": getattr(sub, "plan", "free"),
        "status": getattr(sub, "status", "free"),
        "provider": getattr(sub, "provider", "manual"),
        "is_plus": is_plus,
        "is_active_paid": is_plus,
        "current_period_start": (
            sub.current_period_start.isoformat()
            if sub.current_period_start
            else None
        ),
        "current_period_end": (
            sub.current_period_end.isoformat()
            if sub.current_period_end
            else None
        ),
        "cancel_at_period_end": bool(getattr(sub, "cancel_at_period_end", False)),
    }


def upsert_user_subscription(
    db: Session,
    *,
    user_id: int,
    plan: str,
    status: str,
    provider: str,
    provider_customer_id: str | None = None,
    provider_subscription_id: str | None = None,
    provider_transaction_id: str | None = None,
    current_period_start=None,
    current_period_end=None,
    cancel_at_period_end: bool = False,
    granted_by_admin: bool = False,
    notes: str | None = None,
    provider_raw: dict[str, Any] | None = None,
) -> UserSubscription:
    sub = (
        db.query(UserSubscription)
        .filter(UserSubscription.user_id == user_id)
        .first()
    )

    if not sub:
        sub = UserSubscription(user_id=user_id)

    sub.plan = plan
    sub.status = status
    sub.provider = provider

    sub.provider_customer_id = provider_customer_id
    sub.provider_subscription_id = provider_subscription_id
    sub.provider_transaction_id = provider_transaction_id

    sub.current_period_start = current_period_start
    sub.current_period_end = current_period_end
    sub.cancel_at_period_end = cancel_at_period_end

    sub.granted_by_admin = granted_by_admin

    if notes is not None:
        sub.notes = notes

    if provider_raw is not None:
        sub.provider_raw = provider_raw

    db.add(sub)
    db.commit()
    db.refresh(sub)

    return sub