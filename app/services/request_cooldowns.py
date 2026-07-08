# app/services/request_cooldowns.py

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Literal

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models


CooldownSubjectType = Literal[
    "user",
    "email",
    "identifier",
    "ip",
    "anonymous",
]


DEFAULT_COOLDOWN_SECONDS: dict[str, int] = {
    # Public/auth-related actions
    "forgot_password": 60,
    "resend_verification": 60,
    "send_verification": 60,
    "login": 5,

    # Authenticated account-setting actions
    "change_email": 300,
    "change_username": 300,
    "change_password": 300,

    # App actions
    "pdf_download": 10,
}


def get_default_cooldown_seconds(action_key: str) -> int:
    return DEFAULT_COOLDOWN_SECONDS.get(action_key, 60)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def format_remaining_seconds(seconds: int) -> str:
    safe_seconds = max(0, int(seconds))

    if safe_seconds < 60:
        return f"{safe_seconds} seconds"

    minutes = safe_seconds // 60
    remaining_seconds = safe_seconds % 60

    if remaining_seconds == 0:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"

    return (
        f"{minutes} minute{'s' if minutes != 1 else ''} "
        f"and {remaining_seconds} seconds"
    )


def get_cooldown_hash_secret() -> str:
    """
    Do not store raw emails, IPs, usernames, identifiers, or user IDs in
    request_cooldowns.

    Prefer REQUEST_COOLDOWN_HASH_SECRET in production. The fallbacks keep local
    development from breaking.
    """

    return (
        os.getenv("REQUEST_COOLDOWN_HASH_SECRET")
        or os.getenv("SECRET_KEY")
        or os.getenv("JWT_SECRET_KEY")
        or "sidefx-local-dev-cooldown-secret"
    )


def hash_subject_key(subject_key: str | int) -> str:
    normalized = str(subject_key).strip().lower()
    secret = get_cooldown_hash_secret().encode("utf-8")

    return hmac.new(
        secret,
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def get_client_ip(request: Request) -> str | None:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()

    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    if request.client:
        return request.client.host

    return None


def seconds_until_allowed(
    *,
    last_attempt_at: datetime | None,
    cooldown_seconds: int,
) -> int:
    if not last_attempt_at:
        return 0

    last_attempt_at = make_aware_utc(last_attempt_at)
    elapsed_seconds = int((utc_now() - last_attempt_at).total_seconds())

    return max(int(cooldown_seconds) - elapsed_seconds, 0)


def get_request_cooldown_record(
    *,
    db: Session,
    action_key: str,
    subject_type: CooldownSubjectType,
    subject_key: str | int,
) -> models.RequestCooldown | None:
    subject_key_hash = hash_subject_key(subject_key)

    return (
        db.query(models.RequestCooldown)
        .filter(
            models.RequestCooldown.action_key == action_key,
            models.RequestCooldown.subject_type == subject_type,
            models.RequestCooldown.subject_key_hash == subject_key_hash,
        )
        .first()
    )


def get_request_cooldown_status(
    *,
    db: Session,
    action_key: str,
    subject_type: CooldownSubjectType,
    subject_key: str | int,
    cooldown_seconds: int | None = None,
) -> dict:
    resolved_cooldown_seconds = (
        int(cooldown_seconds)
        if cooldown_seconds is not None
        else get_default_cooldown_seconds(action_key)
    )

    record = get_request_cooldown_record(
        db=db,
        action_key=action_key,
        subject_type=subject_type,
        subject_key=subject_key,
    )

    remaining_seconds = seconds_until_allowed(
        last_attempt_at=record.last_attempt_at if record else None,
        cooldown_seconds=resolved_cooldown_seconds,
    )

    return {
        "action_key": action_key,
        "subject_type": subject_type,
        "cooldown_seconds": resolved_cooldown_seconds,
        "remaining_seconds": remaining_seconds,
        "allowed": remaining_seconds <= 0,
    }


def enforce_request_cooldown(
    *,
    db: Session,
    action_key: str,
    subject_type: CooldownSubjectType,
    subject_key: str | int,
    cooldown_seconds: int | None = None,
    message: str | None = None,
) -> dict:
    status_data = get_request_cooldown_status(
        db=db,
        action_key=action_key,
        subject_type=subject_type,
        subject_key=subject_key,
        cooldown_seconds=cooldown_seconds,
    )

    if status_data["allowed"]:
        return status_data

    remaining_seconds = int(status_data["remaining_seconds"])
    formatted_remaining = format_remaining_seconds(remaining_seconds)

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail={
            "message": message
            or f"Please wait {formatted_remaining} before trying again.",
            "code": "REQUEST_COOLDOWN_ACTIVE",
            "action_key": action_key,
            "subject_type": subject_type,
            "remaining_seconds": remaining_seconds,
            "cooldown_seconds": int(status_data["cooldown_seconds"]),
        },
        headers={
            "Retry-After": str(remaining_seconds),
        },
    )


def mark_request_cooldown(
    *,
    db: Session,
    action_key: str,
    subject_type: CooldownSubjectType,
    subject_key: str | int,
    commit: bool = False,
) -> models.RequestCooldown:
    subject_key_hash = hash_subject_key(subject_key)

    record = (
        db.query(models.RequestCooldown)
        .filter(
            models.RequestCooldown.action_key == action_key,
            models.RequestCooldown.subject_type == subject_type,
            models.RequestCooldown.subject_key_hash == subject_key_hash,
        )
        .first()
    )

    now = utc_now()

    if record:
        record.last_attempt_at = now
    else:
        record = models.RequestCooldown(
            action_key=action_key,
            subject_type=subject_type,
            subject_key_hash=subject_key_hash,
            last_attempt_at=now,
        )
        db.add(record)

    if commit:
        db.commit()
        db.refresh(record)

    return record


def enforce_and_mark_request_cooldown(
    *,
    db: Session,
    action_key: str,
    subject_type: CooldownSubjectType,
    subject_key: str | int,
    cooldown_seconds: int | None = None,
    message: str | None = None,
    commit: bool = False,
) -> dict:
    status_data = enforce_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type=subject_type,
        subject_key=subject_key,
        cooldown_seconds=cooldown_seconds,
        message=message,
    )

    mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type=subject_type,
        subject_key=subject_key,
        commit=commit,
    )

    return status_data


# ─────────────────────────────────────────────────────────────
# User helpers
# ─────────────────────────────────────────────────────────────

def get_user_cooldown_status(
    *,
    db: Session,
    user_id: int,
    action_key: str,
    cooldown_seconds: int | None = None,
) -> dict:
    return get_request_cooldown_status(
        db=db,
        action_key=action_key,
        subject_type="user",
        subject_key=user_id,
        cooldown_seconds=cooldown_seconds,
    )


def enforce_user_cooldown(
    *,
    db: Session,
    user_id: int,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
) -> dict:
    """
    Check a user cooldown without marking a new attempt.
    Useful when you want to validate first, then mark only after success.
    """

    return enforce_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="user",
        subject_key=user_id,
        cooldown_seconds=cooldown_seconds,
        message=message,
    )


def mark_user_cooldown(
    *,
    db: Session,
    user_id: int,
    action_key: str,
    commit: bool = False,
) -> models.RequestCooldown:
    return mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="user",
        subject_key=user_id,
        commit=commit,
    )


def enforce_and_mark_user_cooldown(
    *,
    db: Session,
    user_id: int,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
    commit: bool = False,
) -> dict:
    return enforce_and_mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="user",
        subject_key=user_id,
        cooldown_seconds=cooldown_seconds,
        message=message,
        commit=commit,
    )


# ─────────────────────────────────────────────────────────────
# IP helpers
# ─────────────────────────────────────────────────────────────

def get_ip_cooldown_status(
    *,
    db: Session,
    request: Request,
    action_key: str,
    cooldown_seconds: int | None = None,
) -> dict:
    ip = get_client_ip(request) or "unknown"

    return get_request_cooldown_status(
        db=db,
        action_key=action_key,
        subject_type="ip",
        subject_key=ip,
        cooldown_seconds=cooldown_seconds,
    )


def enforce_ip_cooldown(
    *,
    db: Session,
    request: Request,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
) -> dict:
    ip = get_client_ip(request) or "unknown"

    return enforce_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="ip",
        subject_key=ip,
        cooldown_seconds=cooldown_seconds,
        message=message,
    )


def mark_ip_cooldown(
    *,
    db: Session,
    request: Request,
    action_key: str,
    commit: bool = False,
) -> models.RequestCooldown:
    ip = get_client_ip(request) or "unknown"

    return mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="ip",
        subject_key=ip,
        commit=commit,
    )


def enforce_and_mark_ip_cooldown(
    *,
    db: Session,
    request: Request,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
    commit: bool = False,
) -> dict:
    ip = get_client_ip(request) or "unknown"

    return enforce_and_mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="ip",
        subject_key=ip,
        cooldown_seconds=cooldown_seconds,
        message=message,
        commit=commit,
    )


# ─────────────────────────────────────────────────────────────
# Email / identifier helpers
# ─────────────────────────────────────────────────────────────

def get_email_cooldown_status(
    *,
    db: Session,
    email_hash: str,
    action_key: str,
    cooldown_seconds: int | None = None,
) -> dict:
    return get_request_cooldown_status(
        db=db,
        action_key=action_key,
        subject_type="email",
        subject_key=email_hash,
        cooldown_seconds=cooldown_seconds,
    )


def enforce_email_cooldown(
    *,
    db: Session,
    email_hash: str,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
) -> dict:
    return enforce_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="email",
        subject_key=email_hash,
        cooldown_seconds=cooldown_seconds,
        message=message,
    )


def mark_email_cooldown(
    *,
    db: Session,
    email_hash: str,
    action_key: str,
    commit: bool = False,
) -> models.RequestCooldown:
    return mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="email",
        subject_key=email_hash,
        commit=commit,
    )


def enforce_and_mark_email_cooldown(
    *,
    db: Session,
    email_hash: str,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
    commit: bool = False,
) -> dict:
    return enforce_and_mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="email",
        subject_key=email_hash,
        cooldown_seconds=cooldown_seconds,
        message=message,
        commit=commit,
    )


def get_identifier_cooldown_status(
    *,
    db: Session,
    identifier: str,
    action_key: str,
    cooldown_seconds: int | None = None,
) -> dict:
    return get_request_cooldown_status(
        db=db,
        action_key=action_key,
        subject_type="identifier",
        subject_key=identifier,
        cooldown_seconds=cooldown_seconds,
    )


def enforce_and_mark_identifier_cooldown(
    *,
    db: Session,
    identifier: str,
    action_key: str,
    cooldown_seconds: int | None = None,
    message: str | None = None,
    commit: bool = False,
) -> dict:
    return enforce_and_mark_request_cooldown(
        db=db,
        action_key=action_key,
        subject_type="identifier",
        subject_key=identifier,
        cooldown_seconds=cooldown_seconds,
        message=message,
        commit=commit,
    )