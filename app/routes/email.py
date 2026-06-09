# app/routes/email.py
from datetime import datetime, timedelta, timezone
import os
from fastapi.responses import RedirectResponse
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from app.db import get_db
from app import models
from app.util.security import (
    canonicalize_email,
    decrypt_email,
    hash_email,
    hash_password,
)
from app.email_secure import (
    generate_email_token,
    verify_email_token,
    generate_password_reset_token,
    verify_password_reset_token,
)
from app.emailer import (
    send_email,
    verification_email_html,
    password_reset_email_html,  # ✅ moved to emailer
)
from app.schemas.users import ForgotPasswordRequest, ResetPasswordRequest
from app.schemas.email import ResendVerificationRequest
from app.scripts.validator import validate_new_password

router = APIRouter()

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")
RESEND_MIN_INTERVAL = int(os.getenv("RESEND_MIN_INTERVAL", "60"))


def _verification_link(token: str) -> str:
    return f"{API_BASE_URL}/api/auth/verify?token={token}"


def _password_reset_link(token: str) -> str:
    return f"{APP_BASE_URL}/reset-password?token={token}"


# ─────────────────────────────────────────────────────────────
# EMAIL VERIFICATION
# ─────────────────────────────────────────────────────────────

@router.post("/send-verification", status_code=status.HTTP_204_NO_CONTENT)
def send_verification_email(
    user_id: int,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    if user.email_verification_sent_at:
        delta = datetime.now(timezone.utc) - user.email_verification_sent_at
        if delta < timedelta(seconds=RESEND_MIN_INTERVAL):
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting another email",
            )

    try:
        decrypted_email = canonicalize_email(decrypt_email(user.email_enc))
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read user email")

    token = generate_email_token(user.id, decrypted_email)
    link = _verification_link(token)

    db.execute(
        update(models.User)
        .where(models.User.id == user.id)
        .values(email_verification_sent_at=datetime.now(timezone.utc))
    )
    db.commit()

    html = verification_email_html(link)
    background.add_task(send_email, decrypted_email, "Verify your email", html)


@router.get("/verify")
def verify_email(token: str = Query(...), db: Session = Depends(get_db)):
    try:
        data = verify_email_token(token)
    except ValueError as e:
        return RedirectResponse(
            url=f"{APP_BASE_URL}/verify-email/error?reason={str(e)}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    user = db.execute(
        select(models.User).where(models.User.id == data["uid"])
    ).scalars().first()

    if not user:
        return RedirectResponse(
            url=f"{APP_BASE_URL}/verify-email/error?reason=User not found",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    try:
        current_email = canonicalize_email(decrypt_email(user.email_enc))
    except Exception:
        return RedirectResponse(
            url=f"{APP_BASE_URL}/verify-email/error?reason=Unable to verify account email",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if current_email != canonicalize_email(data["email"]):
        return RedirectResponse(
            url=f"{APP_BASE_URL}/verify-email/error?reason=Token/email mismatch",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if user.is_email_verified:
        return RedirectResponse(
            url=f"{APP_BASE_URL}/verify-email/already-verified",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    db.execute(
        update(models.User)
        .where(models.User.id == user.id)
        .values(is_email_verified=True)
    )
    db.commit()

    return RedirectResponse(
        url=f"{APP_BASE_URL}/verify-email/success",
        status_code=status.HTTP_303_SEE_OTHER,
    )


# ─────────────────────────────────────────────────────────────
# FORGOT PASSWORD
# ─────────────────────────────────────────────────────────────

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(
    payload: ForgotPasswordRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):  
    print("trigger 1")
    email = canonicalize_email(payload.email)
    email_hash = hash_email(email)

    user = db.execute(
        select(models.User).where(models.User.email_hash == email_hash)
    ).scalars().first()

    generic_response = {
        "detail": "If an account exists for that email, a reset link has been sent."
    }

    if not user:
        return generic_response

    if getattr(user, "password_reset_sent_at", None):
        delta = datetime.now(timezone.utc) - user.password_reset_sent_at
        if delta < timedelta(seconds=RESEND_MIN_INTERVAL):
            return generic_response

    try:
        decrypted_email = canonicalize_email(decrypt_email(user.email_enc))
    except Exception:
        return generic_response

    token = generate_password_reset_token(user.id, decrypted_email)
    link = _password_reset_link(token)

    # Optional throttle tracking
    if hasattr(user, "password_reset_sent_at"):
        db.execute(
            update(models.User)
            .where(models.User.id == user.id)
            .values(password_reset_sent_at=datetime.now(timezone.utc))
        )
        db.commit()

    html = password_reset_email_html(link)
    background.add_task(send_email, decrypted_email, "Reset your password", html)

    return generic_response


# ─────────────────────────────────────────────────────────────
# RESET PASSWORD
# ─────────────────────────────────────────────────────────────

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    try:
        data = verify_password_reset_token(payload.token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    password_error = validate_new_password(payload.new_password)
    if password_error:
        raise HTTPException(status_code=400, detail=password_error)

    user = db.execute(
        select(models.User).where(models.User.id == data["uid"])
    ).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        current_email = canonicalize_email(decrypt_email(user.email_enc))
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to verify account email")

    if current_email != canonicalize_email(data["email"]):
        raise HTTPException(status_code=400, detail="Token/email mismatch")

    user.password_hash = hash_password(payload.new_password)

    # 🔥 IMPORTANT: revoke all sessions
    if hasattr(user, "token_version"):
        user.token_version += 1

    db.add(user)
    db.commit()
    
    return {"detail": "Password reset successfully. Please log in again."}


@router.post("/resend", status_code=status.HTTP_204_NO_CONTENT)
def resend_verification(
    payload: ResendVerificationRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    normalized_email = canonicalize_email(payload.email)
    email_hash = hash_email(normalized_email)

    user = db.execute(
        select(models.User).where(models.User.email_hash == email_hash)
    ).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.is_email_verified:
        raise HTTPException(status_code=400, detail="Email already verified")

    if user.email_verification_sent_at:
        delta = datetime.now(timezone.utc) - user.email_verification_sent_at
        if delta < timedelta(seconds=RESEND_MIN_INTERVAL):
            raise HTTPException(
                status_code=429,
                detail="Please wait before requesting another email",
            )

    try:
        decrypted_email = canonicalize_email(decrypt_email(user.email_enc))
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to read user email")

    token = generate_email_token(user.id, decrypted_email)
    link = _verification_link(token)

    db.execute(
        update(models.User)
        .where(models.User.id == user.id)
        .values(email_verification_sent_at=datetime.now(timezone.utc))
    )
    db.commit()

    html = verification_email_html(link)
    background.add_task(send_email, decrypted_email, "Verify your email", html)
    return

