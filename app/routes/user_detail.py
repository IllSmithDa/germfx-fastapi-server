from fastapi import HTTPException, Depends, Cookie, APIRouter
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db import get_db
from app import models
from app.schemas.users import UserDetailOut
from app.core.auth import verify_token
from app.util.security import decrypt_email

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
ACCESS_MAX_AGE = 60 * 60             # 1 hour
REFRESH_MAX_AGE = 30 * 24 * 60 * 60   # 30 days
COOKIE_SECURE = True                 # set False in local HTTP dev if needed
COOKIE_SAMESITE = "lax"              # "lax" works for most app flows

router = APIRouter()


@router.get("/user-detail", response_model=UserDetailOut)
def userDetail(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    db: Session = Depends(get_db),
):
    print("Access token from cookie:", access_token)
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(access_token, token_type="access")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.execute(
        select(models.User).where(models.User.id == int(user_id))
    ).scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Decrypt email for display (if present)
    email = decrypt_email(user.email_enc) if user.email_enc else None

    return {
        "id": str(user.id),
        "username": user.username,
        "email": email,
    }
