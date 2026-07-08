# app/services/email_request_cooldowns.py

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app import models


DEFAULT_EMAIL_COOLDOWN_SECONDS: dict[str, int] = {
    "forgot_password": 60,
    "resend_verification": 60,
    "send_verification": 60,
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def get_email_cooldown_seconds(action_key: str) -> int:
    return DEFAULT_EMAIL_COOLDOWN_SECONDS.get(action_key, 60)


def get_remaining_seconds(
    *,
    last_requested_at: datetime | None,
    cooldown_seconds: int,
) -> int:
    if not last_requested_at:
        return 0

    last_requested_at = make_aware_utc(last_requested_at)
    elapsed_seconds = int((utc_now() - last_requested_at).total_seconds())

    return max(cooldown_seconds - elapsed_seconds, 0)


def get_email_request_cooldown(
    *,
    db: Session,
    action_key: str,
    email_hash: str,
) -> models.EmailRequestCooldown | None:
    return (
        db.query(models.EmailRequestCooldown)
        .filter(
            models.EmailRequestCooldown.action_key == action_key,
            models.EmailRequestCooldown.email_hash == email_hash,
        )
        .first()
    )


def get_email_request_cooldown_status(
    *,
    db: Session,
    action_key: str,
    email_hash: str,
    cooldown_seconds: int | None = None,
) -> dict:
    cooldown_seconds = (
        cooldown_seconds
        if cooldown_seconds is not None
        else get_email_cooldown_seconds(action_key)
    )

    record = get_email_request_cooldown(
        db=db,
        action_key=action_key,
        email_hash=email_hash,
    )

    remaining_seconds = get_remaining_seconds(
        last_requested_at=record.last_requested_at if record else None,
        cooldown_seconds=cooldown_seconds,
    )

    return {
        "action_key": action_key,
        "cooldown_seconds": cooldown_seconds,
        "remaining_seconds": remaining_seconds,
        "allowed": remaining_seconds <= 0,
    }


def is_email_request_allowed(
    *,
    db: Session,
    action_key: str,
    email_hash: str,
    cooldown_seconds: int | None = None,
) -> bool:
    status_data = get_email_request_cooldown_status(
        db=db,
        action_key=action_key,
        email_hash=email_hash,
        cooldown_seconds=cooldown_seconds,
    )

    return bool(status_data["allowed"])


def enforce_email_request_cooldown(
    *,
    db: Session,
    action_key: str,
    email_hash: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
) -> dict:
    status_data = get_email_request_cooldown_status(
        db=db,
        action_key=action_key,
        email_hash=email_hash,
        cooldown_seconds=cooldown_seconds,
    )

    if status_data["allowed"]:
        return status_data

    remaining_seconds = int(status_data["remaining_seconds"])

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "message": message
            or f"Please wait {remaining_seconds} seconds before requesting another email.",
            "code": "EMAIL_REQUEST_COOLDOWN_ACTIVE",
            "action_key": action_key,
            "remaining_seconds": remaining_seconds,
            "cooldown_seconds": int(status_data["cooldown_seconds"]),
        },
        headers={
            "Retry-After": str(remaining_seconds),
        },
    )


def mark_email_request_cooldown(
    *,
    db: Session,
    action_key: str,
    email_hash: str,
    commit: bool = False,
) -> models.EmailRequestCooldown:
    record = get_email_request_cooldown(
        db=db,
        action_key=action_key,
        email_hash=email_hash,
    )

    now = utc_now()

    if record:
        record.last_requested_at = now
    else:
        record = models.EmailRequestCooldown(
            action_key=action_key,
            email_hash=email_hash,
            last_requested_at=now,
        )
        db.add(record)

    if commit:
        db.commit()
        db.refresh(record)

    return record