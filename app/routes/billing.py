from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import billing_config
from app.core.auth import get_authenticated_user
from app.db import get_db
from app.models import BillingWebhookEvent, User, UserSubscription
from app.schemas.billing import BillingCheckoutRequest, BillingCheckoutResponse
from app.services.subscriptions import upsert_user_subscription
from app.util.security import canonicalize_email, decrypt_email


router = APIRouter(tags=["billing"])


def _setting(name: str, default=None):
    return getattr(
        billing_config,
        name,
        default,
    )


def _host_url() -> str:
    """
    Public frontend base URL.

    Local dev:
        HOST_URL=http://localhost:3000

    Production:
        HOST_URL=https://your-domain.com
    """
    return str(_setting("HOST_URL", "http://localhost:3000")).rstrip("/")


def _paddle_checkout_url() -> str:
    """
    Frontend page that Paddle uses to open checkout.

    This should NOT be the FastAPI backend URL.
    This should NOT be the final success page.

    Local dev example:
        PADDLE_CHECKOUT_URL=http://localhost:3000/billing/checkout

    Paddle will return a transaction checkout URL based on this page, usually
    with a transaction parameter appended.
    """
    configured_url = _setting("PADDLE_CHECKOUT_URL")

    if configured_url:
        return str(configured_url).rstrip("/")

    return f"{_host_url()}/billing/checkout"


def _checkout_success_url(provider: str) -> str:
    """
    Final frontend page after successful checkout.

    This is kept separate from _paddle_checkout_url().
    """
    configured_url = _setting("BILLING_SUCCESS_URL")

    if configured_url:
        return str(configured_url)

    return f"{_host_url()}/billing/success?provider={provider}"


def _checkout_cancel_url() -> str:
    """
    Final/frontend page for canceled or abandoned checkout.

    Currently not passed to Paddle in this router, but useful if you wire this
    into the frontend checkout page later.
    """
    configured_url = _setting("BILLING_CANCEL_URL")

    if configured_url:
        return str(configured_url)

    return f"{_host_url()}/pricing"


def _get_user_email(user: User) -> str | None:
    try:
        if user.email_enc:
            return canonicalize_email(decrypt_email(user.email_enc))
    except Exception:
        return None

    return None


def _parse_iso_datetime(value: str | None):
    if not value:
        return None

    try:
        clean_value = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(clean_value)

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _get_price_id_for_plan(plan: str) -> str:
    if plan != "plus":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported billing plan.",
        )

    price_id = _setting("PADDLE_PLUS_PRICE_ID")

    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paddle Plus price ID is not configured.",
        )

    return price_id


def _paddle_base_url() -> str:
    environment = str(_setting("PADDLE_ENVIRONMENT", "sandbox")).lower()

    if environment == "production":
        return "https://api.paddle.com"

    return "https://sandbox-api.paddle.com"


def _resolve_user_id_from_custom_data(data: dict[str, Any]) -> int | None:
    custom_data = data.get("custom_data") or {}
    raw_user_id = custom_data.get("user_id")

    if raw_user_id is None:
        return None

    try:
        return int(raw_user_id)
    except (TypeError, ValueError):
        return None


def _resolve_plan_from_custom_data(data: dict[str, Any]) -> str:
    custom_data = data.get("custom_data") or {}
    plan = custom_data.get("plan")

    if plan in {"plus", "pro"}:
        return plan

    return "plus"


def _map_paddle_subscription_status(status_value: str | None) -> str:
    status_value = (status_value or "").lower()

    if status_value in {"active", "trialing", "past_due", "paused", "canceled"}:
        return status_value

    return "free"


def _extract_billing_period(data: dict[str, Any]):
    period = (
        data.get("current_billing_period")
        or data.get("billing_period")
        or {}
    )

    starts_at = _parse_iso_datetime(period.get("starts_at"))
    ends_at = _parse_iso_datetime(period.get("ends_at"))

    return starts_at, ends_at


def _find_user_id_for_paddle_event(
    db: Session,
    *,
    data: dict[str, Any],
) -> int | None:
    user_id = _resolve_user_id_from_custom_data(data)

    if user_id:
        return user_id

    subscription_id = data.get("id") or data.get("subscription_id")
    transaction_id = data.get("id") or data.get("transaction_id")

    if subscription_id:
        existing = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.provider == "paddle",
                UserSubscription.provider_subscription_id == subscription_id,
            )
            .first()
        )

        if existing:
            return existing.user_id

    if transaction_id:
        existing = (
            db.query(UserSubscription)
            .filter(
                UserSubscription.provider == "paddle",
                UserSubscription.provider_transaction_id == transaction_id,
            )
            .first()
        )

        if existing:
            return existing.user_id

    return None


def _parse_paddle_signature_header(header_value: str | None) -> tuple[str, list[str]]:
    if not header_value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Paddle-Signature header.",
        )

    timestamp = None
    signatures: list[str] = []

    for part in header_value.split(";"):
        key, _, value = part.partition("=")

        key = key.strip()
        value = value.strip()

        if key == "ts":
            timestamp = value

        if key == "h1" and value:
            signatures.append(value)

    if not timestamp or not signatures:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle-Signature header.",
        )

    return timestamp, signatures


def _verify_paddle_webhook_signature(
    *,
    raw_body: bytes,
    signature_header: str | None,
):
    secret = _setting("PADDLE_WEBHOOK_SECRET")

    if not secret:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paddle webhook secret is not configured.",
        )

    timestamp, signatures = _parse_paddle_signature_header(signature_header)

    try:
        event_time = int(timestamp)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle webhook timestamp.",
        )

    tolerance = int(_setting("PADDLE_WEBHOOK_TOLERANCE_SECONDS", 300))

    if tolerance > 0:
        age = abs(int(time.time()) - event_time)

        if age > tolerance:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail="Paddle webhook timestamp outside tolerance.",
            )

    signed_payload = timestamp.encode("utf-8") + b":" + raw_body

    expected_signature = hmac.new(
        key=str(secret).encode("utf-8"),
        msg=signed_payload,
        digestmod=hashlib.sha256,
    ).hexdigest()

    signature_matches = any(
        hmac.compare_digest(expected_signature, candidate)
        for candidate in signatures
    )

    if not signature_matches:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Paddle webhook signature.",
        )


def _record_webhook_event(
    db: Session,
    *,
    provider: str,
    event_id: str,
    event_type: str,
    event: dict[str, Any],
) -> bool:
    existing = (
        db.query(BillingWebhookEvent)
        .filter(
            BillingWebhookEvent.provider == provider,
            BillingWebhookEvent.event_id == event_id,
        )
        .first()
    )

    if existing:
        return False

    row = BillingWebhookEvent(
        provider=provider,
        event_id=event_id,
        event_type=event_type,
        raw_json=event,
    )

    db.add(row)

    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


async def _create_paddle_checkout(
    *,
    db: Session,
    user: User,
    plan: str,
) -> BillingCheckoutResponse:
    api_key = _setting("PADDLE_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Paddle API key is not configured.",
        )

    price_id = _get_price_id_for_plan(plan)
    email = _get_user_email(user)

    payload: dict[str, Any] = {
        "items": [
            {
                "price_id": price_id,
                "quantity": 1,
            }
        ],
        "custom_data": {
            "user_id": str(user.id),
            "plan": plan,
            "provider": "paddle",
            "success_url": _checkout_success_url("paddle"),
            "cancel_url": _checkout_cancel_url(),
        },
    
        #"checkout": {
        #    "url": _paddle_checkout_url(),
        #},
    }

    if email:
        payload["customer"] = {
            "email": email,
        }

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{_paddle_base_url()}/transactions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json=payload,
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Unable to create Paddle checkout.",
                "provider_status": response.status_code,
                "provider_response": response.text,
            },
        )

    provider_data = response.json()
    transaction = provider_data.get("data") or {}

    transaction_id = transaction.get("id")
    checkout = transaction.get("checkout") or {}
    checkout_url = checkout.get("url")

    if not checkout_url:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Paddle checkout URL missing from provider response.",
        )

    upsert_user_subscription(
        db,
        user_id=user.id,
        plan=plan,
        status="pending",
        provider="paddle",
        provider_customer_id=transaction.get("customer_id"),
        provider_transaction_id=transaction_id,
        provider_raw=transaction,
        notes="Checkout created; waiting for Paddle webhook confirmation.",
    )

    return BillingCheckoutResponse(
        provider="paddle",
        plan=plan,
        checkout_url=checkout_url,
    )


def _handle_paddle_subscription_event(
    db: Session,
    *,
    event_type: str,
    data: dict[str, Any],
):
    user_id = _find_user_id_for_paddle_event(
        db,
        data=data,
    )

    if not user_id:
        return {
            "handled": False,
            "reason": "user_id_not_found",
        }

    plan = _resolve_plan_from_custom_data(data)

    paddle_status = data.get("status")
    mapped_status = _map_paddle_subscription_status(paddle_status)

    starts_at, ends_at = _extract_billing_period(data)

    subscription_id = data.get("id")
    customer_id = data.get("customer_id")

    cancel_at_period_end = bool(data.get("scheduled_change"))

    if event_type == "subscription.canceled":
        mapped_status = "canceled"

    if event_type == "subscription.past_due":
        mapped_status = "past_due"

    if event_type == "subscription.paused":
        mapped_status = "paused"

    if event_type == "subscription.trialing":
        mapped_status = "trialing"

    if event_type in {"subscription.activated", "subscription.resumed"}:
        mapped_status = "active"

    upsert_user_subscription(
        db,
        user_id=user_id,
        plan=plan,
        status=mapped_status,
        provider="paddle",
        provider_customer_id=customer_id,
        provider_subscription_id=subscription_id,
        current_period_start=starts_at,
        current_period_end=ends_at,
        cancel_at_period_end=cancel_at_period_end,
        provider_raw=data,
        notes=f"Updated from Paddle webhook: {event_type}",
    )

    return {
        "handled": True,
        "user_id": user_id,
        "status": mapped_status,
    }


def _handle_paddle_transaction_event(
    db: Session,
    *,
    event_type: str,
    data: dict[str, Any],
):
    user_id = _find_user_id_for_paddle_event(
        db,
        data=data,
    )

    if not user_id:
        return {
            "handled": False,
            "reason": "user_id_not_found",
        }

    plan = _resolve_plan_from_custom_data(data)

    transaction_id = data.get("id")
    subscription_id = data.get("subscription_id")
    customer_id = data.get("customer_id")

    # Do not mark fully active from transaction.paid alone.
    # Use subscription events or transaction.completed for entitlement confirmation.
    if event_type == "transaction.payment_failed":
        status_value = "past_due"
    elif event_type == "transaction.completed":
        status_value = "active"
    else:
        status_value = "pending"

    upsert_user_subscription(
        db,
        user_id=user_id,
        plan=plan,
        status=status_value,
        provider="paddle",
        provider_customer_id=customer_id,
        provider_subscription_id=subscription_id,
        provider_transaction_id=transaction_id,
        provider_raw=data,
        notes=f"Updated from Paddle webhook: {event_type}",
    )

    return {
        "handled": True,
        "user_id": user_id,
        "status": status_value,
    }


@router.post(
    "/checkout",
    response_model=BillingCheckoutResponse,
)
async def create_checkout(
    payload: BillingCheckoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    provider = (payload.provider or _setting("BILLING_PROVIDER", "paddle")).lower()

    if provider != "paddle":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Paddle checkout is implemented right now.",
        )

    return await _create_paddle_checkout(
        db=db,
        user=current_user,
        plan=payload.plan,
    )


@router.post("/webhook/paddle")
async def paddle_webhook(
    request: Request,
    db: Session = Depends(get_db),
):
    raw_body = await request.body()

    _verify_paddle_webhook_signature(
        raw_body=raw_body,
        signature_header=request.headers.get("Paddle-Signature"),
    )

    try:
        event = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle webhook JSON.",
        )

    event_id = event.get("event_id")
    event_type = event.get("event_type")
    data = event.get("data") or {}

    if not event_id or not event_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Paddle webhook payload.",
        )

    should_process = _record_webhook_event(
        db,
        provider="paddle",
        event_id=event_id,
        event_type=event_type,
        event=event,
    )

    if not should_process:
        return {
            "received": True,
            "duplicate": True,
        }

    if event_type.startswith("subscription."):
        result = _handle_paddle_subscription_event(
            db,
            event_type=event_type,
            data=data,
        )

        return {
            "received": True,
            "duplicate": False,
            **result,
        }

    if event_type.startswith("transaction."):
        result = _handle_paddle_transaction_event(
            db,
            event_type=event_type,
            data=data,
        )

        return {
            "received": True,
            "duplicate": False,
            **result,
        }

    return {
        "received": True,
        "duplicate": False,
        "handled": False,
        "reason": "event_type_ignored",
        "event_type": event_type,
    }