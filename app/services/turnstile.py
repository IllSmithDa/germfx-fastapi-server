# app/services/turnstile.py

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import HTTPException, Request, status


TURNSTILE_SITEVERIFY_URL = (
    "https://challenges.cloudflare.com/turnstile/v0/siteverify"
)


def is_turnstile_enabled() -> bool:
    return os.getenv("TURNSTILE_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


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


def verify_turnstile_token(
    *,
    token: str | None,
    request: Request,
    action: str | None = None,
) -> dict[str, Any]:
    """
    Verify a Cloudflare Turnstile token before allowing a protected action.

    Intended actions:
    - register
    - login
    - forgot_password
    - resend_verification
    """

    if not is_turnstile_enabled():
        return {
            "success": True,
            "skipped": True,
            "action": action,
        }

    token = (token or "").strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Turnstile verification is required.",
                "code": "TURNSTILE_TOKEN_REQUIRED",
            },
        )

    if len(token) > 2048:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Turnstile token is too long.",
                "code": "TURNSTILE_TOKEN_TOO_LONG",
            },
        )

    secret_key = os.getenv("TURNSTILE_SECRET_KEY", "").strip()

    if not secret_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "message": "Turnstile secret key is not configured.",
                "code": "TURNSTILE_SECRET_MISSING",
            },
        )

    payload: dict[str, str] = {
        "secret": secret_key,
        "response": token,
        "idempotency_key": str(uuid.uuid4()),
    }

    remote_ip = get_client_ip(request)
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                TURNSTILE_SITEVERIFY_URL,
                data=payload,
                headers={
                    "Accept": "application/json",
                },
            )

        data = response.json()

    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Turnstile verification timed out. Please try again.",
                "code": "TURNSTILE_TIMEOUT",
            },
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Unable to verify Turnstile token. Please try again.",
                "code": "TURNSTILE_VERIFY_FAILED",
            },
        ) from exc

    if not data.get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Turnstile verification failed. Please try again.",
                "code": "TURNSTILE_INVALID",
                "turnstile_error_codes": data.get("error-codes", []),
            },
        )

    return data