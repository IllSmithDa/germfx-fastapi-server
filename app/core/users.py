from fastapi import APIRouter, HTTPException, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app import models
from app.util.security import (
  hash_email,
  encrypt_email,
  hash_password,
  canonicalize_email,
)

from app.scripts.validator import (
    validate_new_email,
    validate_new_password,
    validate_username
)
from app.schemas.users import UserCreate

def create_user_in_db(payload: UserCreate, db: Session) -> models.User:
    username = payload.username.strip()
    email = canonicalize_email(payload.email)
    password = payload.password

    # 1. Backend validation
    username_error = validate_username(username)
    if username_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=username_error,
        )

    password_error = validate_new_password(password)
    if password_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=password_error,
        )

    # 2. Normalize + secure email fields
    email_hash = hash_email(email)
    email_enc = encrypt_email(email)

    # 3. Check uniqueness
    existing = db.execute(
        select(models.User).where(
            (func.lower(models.User.username) == username.lower())
            | (models.User.email_hash == email_hash)
        )
    ).scalars().first()

    if existing:
        if existing.username.lower() == username.lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

        if existing.email_hash == email_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use",
            )

    # 4. Hash password
    pwd_hash = hash_password(password)

    # 5. Create user
    user = models.User(
        username=username,
        email_hash=email_hash,
        email_enc=email_enc,
        password_hash=pwd_hash,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user

