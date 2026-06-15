# routes/auth.py

from app.util.security import (
  hash_password,
  verify_password,
  hash_email,
  canonicalize_email,
  encrypt_email,
  decrypt_email
)
from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie, Request, BackgroundTasks, Header
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import List
from app import models
from app.db import get_db
from app.models import User
from app.schemas.users import ChangePasswordRequest, ChangeUsernameRequest, ChangeEmailRequest, UserOut, UserLogin, UserCreate
from app.core.users import create_user_in_db
from app.core.auth_config import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    ACCESS_TOKEN_SECONDS,
    REFRESH_TOKEN_SECONDS,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
    COOKIE_PATH,
)
from app.core.auth import (
    _extract_bearer_token,
    create_access_token,
    create_refresh_token,
    verify_token,
    verify_user,
    get_authenticated_user
)
from app.scripts.validator import validate_new_password, validate_username, validate_new_email


router = APIRouter()


COOKIE_PATH = "/"  # must match what you used when setting cookies
# REFRESH_PATH = "/auth"  # path where refresh cookie is valid

from app.util.security import decrypt_email, canonicalize_email
from app.email_secure import generate_email_token
from app.emailer import send_email, verification_email_html
import os

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

def _verification_link(token: str) -> str:
    return f"{API_BASE_URL}/api/auth/verify?token={token}"


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
):
    created_user = create_user_in_db(payload, db)

    try:
        decrypted_email = canonicalize_email(decrypt_email(created_user.email_enc))
        token = generate_email_token(created_user.id, decrypted_email)
        link = _verification_link(token)
        html = verification_email_html(link)

        background.add_task(
            send_email,
            decrypted_email,
            "Welcome to SideFX — verify your email",
            html,
        )
    except Exception:
        # You can log this instead of failing registration
        pass

    return created_user


@router.post("/login")
def login_user(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    """
    Authenticate a user by identifier (email or username) + password,
    issue JWTs, and set HttpOnly cookies.
    """
    # verify_user already handles email OR username
    user = verify_user(payload.identifier, payload.password, db)

    if not user.is_email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Please verify your email before logging in.",
                "code": "EMAIL_NOT_VERIFIED",
            },
        )

    if not user.is_active:
        account_status = getattr(user, "account_status", None)

        if account_status == "deactivated":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "This account is deactivated. You can reactivate it.",
                    "code": "ACCOUNT_DEACTIVATED",
                },
            )

        if account_status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "This account has been suspended. Please contact support.",
                    "code": "ACCOUNT_SUSPENDED",
                },
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "This account is inactive.",
                "code": "ACCOUNT_INACTIVE",
            },
        )

    # Create tokens
    access_token = create_access_token({
        "sub": str(user.id),
        "tv": user.token_version
    })
    refresh_token = create_refresh_token({
        "sub": str(user.id),
        "tv": user.token_version,
    })

    # Set HttpOnly cookies
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_SECONDS,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_SECONDS,
        path="/",
    )

    # Keep returning the user object as before
    return {
    "user": {
        "id": user.id,
        "username": user.username,
        "is_active": user.is_active,
        "is_email_verified": user.is_email_verified,
        "account_status": getattr(user, "account_status", None),
        "created_at": user.created_at,
    },
    "access_token": access_token,
    "refresh_token": refresh_token,
    "token_type": "bearer",
}

@router.post("/refresh")
def refresh_access_token(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    authorization: str | None = Header(default=None),
):
    bearer_refresh_token = _extract_bearer_token(authorization)
    token = bearer_refresh_token or refresh_token
    
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token missing")
    
    payload = verify_token(token, token_type="refresh")


    user_id = payload.get("sub")
    if not user_id:
        print("Invalid refresh token: no user_id in payload")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = db.execute(
        select(models.User).where(models.User.id == int(user_id))
    ).scalars().first()

    if not user:
        print(f"User not found for id {user_id} in refresh token")
        raise HTTPException(status_code=401, detail="User not found")

    token_version = payload.get("tv")
    try:
        token_version = int(token_version)
    except (TypeError, ValueError):
        print("Invalid token version in refresh token")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if token_version != user.token_version:
        print("Refresh token revoked")

        raise HTTPException(status_code=401, detail="Refresh token revoked")

    new_access = create_access_token({
        "sub": str(user.id),
        "tv": user.token_version,
    })
    new_refresh = create_refresh_token({
        "sub": str(user.id),
        "tv": user.token_version,
    })

    response.set_cookie(
        key=ACCESS_COOKIE,
        value=new_access,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_SECONDS,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=new_refresh,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_SECONDS,
        path="/",
    )

    return {
        "access_token": new_access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
    }


@router.get("/me")
def me(current_user: models.User = Depends(get_authenticated_user)):
    email = None

    try:
        if current_user.email_enc:
            email = canonicalize_email(decrypt_email(current_user.email_enc))
    except Exception:
        email = None

    # print("returning user role: ", current_user.role)
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": email,
        "is_active": current_user.is_active,
        "is_email_verified": current_user.is_email_verified,
        "account_status": getattr(current_user, "account_status", None),
        "created_at": current_user.created_at,
        "role": current_user.role
    }

@router.get("/", response_model=List[UserOut])
def get_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    print("Logout requested. Clearing cookies.")
    refresh_token = request.cookies.get(REFRESH_COOKIE)

    if refresh_token:
        try:
            payload = verify_token(refresh_token, token_type="refresh")
            user_id = payload.get("sub")

            if user_id:
                user = db.execute(
                    select(models.User).where(models.User.id == int(user_id))
                ).scalars().first()

                if user:
                    user.token_version += 1
                    db.commit()

        except Exception:
            # Expired/invalid refresh token should not prevent logout
            pass

    response.delete_cookie(
        key=ACCESS_COOKIE,
        path=COOKIE_PATH,
    )
    response.delete_cookie(
        key=REFRESH_COOKIE,
        path=COOKIE_PATH,
    )
    return

@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    payload: ChangePasswordRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    # Verify current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Backend password policy
    password_error = validate_new_password(payload.new_password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    # Update password hash
    current_user.password_hash = hash_password(payload.new_password)

    # Invalidate old refresh sessions
    current_user.token_version += 1

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    # Optional but recommended: clear cookies so user logs in again
    response.delete_cookie(key=ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH)

    return {"message": "Password changed successfully. Please log in again."}


@router.post("/change-username", response_model=UserOut, status_code=status.HTTP_200_OK)
def change_username(
    payload: ChangeUsernameRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    new_username = payload.new_username.strip()

    username_error = validate_username(new_username)
    if username_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=username_error,
        )

    if new_username.lower() == current_user.username.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New username must be different from your current username",
        )

    existing_user = db.execute(
        select(models.User).where(func.lower(models.User.username) == new_username.lower())
    ).scalars().first()
    # print("existing user check: ", existing_user)

    if existing_user and existing_user.id != current_user.id:
        # print("username already taken")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already taken",
        )

    current_user.username = new_username
    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    return current_user

@router.post("/change-email", status_code=status.HTTP_200_OK)
def change_email(
    payload: ChangeEmailRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_authenticated_user),
):
    new_email = canonicalize_email(payload.new_email)

    # Confirm current password
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    # Backend email validation
    email_error = validate_new_email(new_email)
    if email_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=email_error,
        )

    # Compare against current email
    try:
        current_email = canonicalize_email(decrypt_email(current_user.email_enc))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to verify current email",
        )

    if current_email == new_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New email must be different from your current email",
        )

    # Check uniqueness by deterministic hash
    new_email_hash = hash_email(new_email)

    existing_user = db.execute(
        select(models.User).where(models.User.email_hash == new_email_hash)
    ).scalars().first()

    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already in use",
        )

    # Update encrypted + hashed email
    current_user.email_hash = new_email_hash
    current_user.email_enc = encrypt_email(new_email)

    # Invalidate existing sessions
    current_user.token_version += 1

    db.add(current_user)
    db.commit()
    db.refresh(current_user)

    # Force fresh login
    response.delete_cookie(key=ACCESS_COOKIE, path=COOKIE_PATH)
    response.delete_cookie(key=REFRESH_COOKIE, path=COOKIE_PATH)

    return {"message": "Email changed successfully. Please log in again."}