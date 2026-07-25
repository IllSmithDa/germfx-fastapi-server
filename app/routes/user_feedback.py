from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.schemas.user_feedback import AdminFeedbackListOut, AdminFeedbackOut, AdminFeedbackStatusUpdateRequest, FeedbackCategory, FeedbackCreateRequest, FeedbackDeleteOut, FeedbackOut, FeedbackReviewStatus, FeedbackSort, FeedbackUpdateRequest
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models
from app.core.auth import get_authenticated_user
from app.db import get_db
from app.models import UserFeedback


router = APIRouter()
admin_router = APIRouter()

MAX_FEEDBACK_PER_USER = 3


def _iso(value: Any) -> str | None:
    if not value:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


def _clean_message(value: str) -> str:
    # Preserve user paragraphs while normalizing platform-specific line endings.
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    lines = [" ".join(line.split()) for line in text.split("\n")]
    return "\n".join(line for line in lines if line).strip()


def _clean_optional_text(value: str | None, *, max_chars: int) -> str | None:
    if value is None:
        return None

    text = " ".join(str(value or "").split()).strip()

    if not text:
        return None

    return text[:max_chars]


def _feedback_status_value(feedback: UserFeedback) -> str:
    value = getattr(feedback, "status", None)

    if value in {"read", "addressed"}:
        return value

    return "unread"


def _feedback_out(feedback: UserFeedback) -> dict[str, Any]:
    return {
        "id": feedback.id,
        "category": feedback.category,
        "rating": feedback.rating,
        "message": feedback.message,
        "page_url": feedback.page_url,
        "status": _feedback_status_value(feedback),
        "created_at": _iso(feedback.created_at),
        "updated_at": _iso(feedback.updated_at),
    }


def _admin_feedback_out(
    feedback: UserFeedback,
    user: models.User | None = None,
) -> dict[str, Any]:
    item = _feedback_out(feedback)
    item.update(
        {
            "user_id": feedback.user_id,
            "username": getattr(user, "username", None) if user else None,
            "user_agent": getattr(feedback, "user_agent", None),
        }
    )
    return item


def _user_email_is_verified(user: models.User) -> bool:
    """
    Adjust this helper if your User model has one canonical verification field.

    This version supports several common field names so the route fails closed
    unless a known verification value is present.
    """

    for attr in (
        "email_verified_at",
        "verified_at",
        "is_email_verified",
        "email_verified",
        "is_verified",
    ):
        value = getattr(user, attr, None)

        if isinstance(value, bool) and value:
            return True

        if value and not isinstance(value, bool):
            return True

    return False


def require_verified_feedback_user(
    current_user: models.User = Depends(get_authenticated_user),
) -> models.User:
    if not _user_email_is_verified(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Please verify your email before submitting feedback.",
                "code": "EMAIL_VERIFICATION_REQUIRED",
            },
        )

    return current_user


def require_admin_user(
    current_user: models.User = Depends(get_authenticated_user),
) -> models.User:
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Admin access required.",
                "code": "ADMIN_REQUIRED",
            },
        )

    return current_user


def _get_owned_feedback_or_404(
    db: Session,
    *,
    feedback_id: int,
    user_id: int,
) -> UserFeedback:
    feedback = (
        db.query(UserFeedback)
        .filter(
            UserFeedback.id == feedback_id,
            UserFeedback.user_id == user_id,
        )
        .first()
    )

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Feedback not found.",
                "code": "FEEDBACK_NOT_FOUND",
            },
        )

    return feedback


def _get_feedback_or_404(
    db: Session,
    *,
    feedback_id: int,
) -> UserFeedback:
    feedback = db.get(UserFeedback, feedback_id)

    if not feedback:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Feedback not found.",
                "code": "FEEDBACK_NOT_FOUND",
            },
        )

    return feedback


def _reset_feedback_review_status(feedback: UserFeedback) -> None:
    """Whenever a user creates/edits feedback, make it unread for admin review."""

    if hasattr(feedback, "status"):
        feedback.status = "unread"


def _apply_admin_feedback_status(
    feedback: UserFeedback,
    *,
    next_status: FeedbackReviewStatus,
) -> None:
    if not hasattr(feedback, "status"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Feedback status is not available. Add the status column and run the migration first.",
                "code": "FEEDBACK_STATUS_FIELD_MISSING",
            },
        )

    feedback.status = next_status
    feedback.updated_at = datetime.now(timezone.utc)


# 1. User Submit Feedback
@router.post("", response_model=FeedbackOut, status_code=status.HTTP_201_CREATED)
def submit_feedback(
    payload: FeedbackCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_verified_feedback_user),
):
    message = _clean_message(payload.message)

    if len(message) < 3:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Feedback message is too short.",
                "code": "FEEDBACK_TOO_SHORT",
            },
        )

    existing_feedback = (
        db.query(UserFeedback)
        .filter(UserFeedback.user_id == current_user.id)
        .order_by(UserFeedback.created_at.asc(), UserFeedback.id.asc())
        .with_for_update()
        .all()
    )

    now = datetime.now(timezone.utc)
    page_url = _clean_optional_text(payload.page_url, max_chars=500)
    user_agent = _clean_optional_text(request.headers.get("user-agent"), max_chars=500)

    if len(existing_feedback) >= MAX_FEEDBACK_PER_USER:
        feedback = existing_feedback[0]
        feedback.category = payload.category
        feedback.rating = payload.rating
        feedback.message = message
        feedback.page_url = page_url
        feedback.user_agent = user_agent
        feedback.created_at = now
        feedback.updated_at = now
        _reset_feedback_review_status(feedback)
    else:
        feedback = UserFeedback(
            user_id=current_user.id,
            category=payload.category,
            rating=payload.rating,
            message=message,
            page_url=page_url,
            user_agent=user_agent,
        )
        _reset_feedback_review_status(feedback)
        db.add(feedback)

    db.flush()

    # Defensive cleanup in case older bugs or concurrent requests ever created
    # more than MAX_FEEDBACK_PER_USER rows for this user.
    extra_feedback = (
        db.query(UserFeedback)
        .filter(UserFeedback.user_id == current_user.id)
        .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
        .offset(MAX_FEEDBACK_PER_USER)
        .all()
    )

    for old_feedback in extra_feedback:
        db.delete(old_feedback)

    db.commit()
    db.refresh(feedback)

    return _feedback_out(feedback)


# 2. Admin Review Feedback
@admin_router.get("", response_model=AdminFeedbackListOut)
def list_admin_feedback(
    query: str | None = Query(default=None, max_length=160),
    category: FeedbackCategory | None = Query(default=None),
    status_filter: FeedbackReviewStatus | None = Query(default=None, alias="status"),
    rating: int | None = Query(default=None, ge=1, le=5),
    user_id: int | None = Query(default=None, ge=1),
    sort: FeedbackSort = Query(default="created_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    feedback_query = (
        db.query(UserFeedback, models.User)
        .outerjoin(models.User, models.User.id == UserFeedback.user_id)
    )

    if category:
        feedback_query = feedback_query.filter(UserFeedback.category == category)

    if status_filter:
        if not hasattr(UserFeedback, "status"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Feedback status filtering is not available until the status column is added.",
                    "code": "FEEDBACK_STATUS_FIELDS_MISSING",
                },
            )

        if status_filter == "unread":
            feedback_query = feedback_query.filter(
                or_(
                    UserFeedback.status == "unread",
                    UserFeedback.status.is_(None),
                )
            )
        else:
            feedback_query = feedback_query.filter(UserFeedback.status == status_filter)

    if rating is not None:
        feedback_query = feedback_query.filter(UserFeedback.rating == rating)

    if user_id is not None:
        feedback_query = feedback_query.filter(UserFeedback.user_id == user_id)

    if query:
        search = f"%{query.strip().lower()}%"
        feedback_query = feedback_query.filter(
            or_(
                func.lower(UserFeedback.message).like(search),
                func.lower(UserFeedback.category).like(search),
                func.lower(UserFeedback.page_url).like(search),
                func.lower(models.User.username).like(search),
            )
        )

    total = feedback_query.count()

    if sort == "created_asc":
        feedback_query = feedback_query.order_by(
            UserFeedback.created_at.asc().nullslast(),
            UserFeedback.id.asc(),
        )
    elif sort == "updated_desc":
        feedback_query = feedback_query.order_by(
            UserFeedback.updated_at.desc().nullslast(),
            UserFeedback.id.desc(),
        )
    elif sort == "rating_desc":
        feedback_query = feedback_query.order_by(
            UserFeedback.rating.desc().nullslast(),
            UserFeedback.created_at.desc().nullslast(),
            UserFeedback.id.desc(),
        )
    elif sort == "rating_asc":
        feedback_query = feedback_query.order_by(
            UserFeedback.rating.asc().nullslast(),
            UserFeedback.created_at.desc().nullslast(),
            UserFeedback.id.desc(),
        )
    else:
        feedback_query = feedback_query.order_by(
            UserFeedback.created_at.desc().nullslast(),
            UserFeedback.id.desc(),
        )

    offset = (page - 1) * page_size
    rows = feedback_query.offset(offset).limit(page_size).all()

    return {
        "items": [
            _admin_feedback_out(feedback, user)
            for feedback, user in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": offset + len(rows) < total,
    }


@admin_router.delete("/{feedback_id}", response_model=FeedbackDeleteOut)
def delete_admin_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    feedback = _get_feedback_or_404(db, feedback_id=feedback_id)

    db.delete(feedback)
    db.commit()

    return {
        "deleted": True,
        "feedback_id": feedback_id,
    }


@admin_router.patch("/{feedback_id}/status", response_model=AdminFeedbackOut)
def update_admin_feedback_status(
    feedback_id: int,
    payload: AdminFeedbackStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    row = (
        db.query(UserFeedback, models.User)
        .outerjoin(models.User, models.User.id == UserFeedback.user_id)
        .filter(UserFeedback.id == feedback_id)
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Feedback not found.",
                "code": "FEEDBACK_NOT_FOUND",
            },
        )

    feedback, user = row
    _apply_admin_feedback_status(feedback, next_status=payload.status)

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return _admin_feedback_out(feedback, user)


# 3. User See Feedback
@router.get("/me", response_model=list[FeedbackOut])
def list_my_feedback(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_verified_feedback_user),
):
    feedback = (
        db.query(UserFeedback)
        .filter(UserFeedback.user_id == current_user.id)
        .order_by(UserFeedback.created_at.desc(), UserFeedback.id.desc())
        .limit(MAX_FEEDBACK_PER_USER)
        .all()
    )

    return [_feedback_out(item) for item in feedback]


# 4. Delete Feedback
@router.delete("/{feedback_id}", response_model=FeedbackDeleteOut)
def delete_feedback(
    feedback_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_verified_feedback_user),
):
    feedback = _get_owned_feedback_or_404(
        db,
        feedback_id=feedback_id,
        user_id=current_user.id,
    )

    db.delete(feedback)
    db.commit()

    return {
        "deleted": True,
        "feedback_id": feedback_id,
    }


# 5. Edit Feedback
@router.patch("/{feedback_id}", response_model=FeedbackOut)
def update_feedback(
    feedback_id: int,
    payload: FeedbackUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_verified_feedback_user),
):
    feedback = _get_owned_feedback_or_404(
        db,
        feedback_id=feedback_id,
        user_id=current_user.id,
    )

    user_changed_content = False

    if payload.category is not None:
        feedback.category = payload.category
        user_changed_content = True

    if payload.rating is not None:
        feedback.rating = payload.rating
        user_changed_content = True

    if payload.message is not None:
        message = _clean_message(payload.message)

        if len(message) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={
                    "message": "Feedback message is too short.",
                    "code": "FEEDBACK_TOO_SHORT",
                },
            )

        feedback.message = message
        user_changed_content = True

    if payload.page_url is not None:
        feedback.page_url = _clean_optional_text(payload.page_url, max_chars=500)
        user_changed_content = True

    feedback.user_agent = _clean_optional_text(
        request.headers.get("user-agent"),
        max_chars=500,
    )
    feedback.updated_at = datetime.now(timezone.utc)

    if user_changed_content:
        _reset_feedback_review_status(feedback)

    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return _feedback_out(feedback)