from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.saved_items import SaveItemRequest
from app.services.saved_items import (
    check_bulk_saved_items_for_user,
    save_item_for_user,
    list_saved_items_for_user,
    delete_saved_item_for_user,
    check_saved_item_for_user,
)
from app.services.usage_limits import enforce_free_usage_limit
from app.core.auth import get_authenticated_user
from app.models import User, UserSavedItem

router = APIRouter(tags=["saved-items"])


@router.post("")
def create_saved_item(
    payload: SaveItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    try:
        user = db.get(User, current_user.id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        # Check duplicate first.
        # If the item is already saved, this should not count as a new save
        # and should not be blocked by the saved-items limit.
        existing_saved_item = (
            db.query(UserSavedItem)
            .filter(
                UserSavedItem.user_id == current_user.id,
                UserSavedItem.content_type == payload.content_type,
                UserSavedItem.source_item_id == payload.source_item_id,
            )
            .first()
        )

        if existing_saved_item:
            return save_item_for_user(
                db,
                user_id=current_user.id,
                content_type=payload.content_type,
                source_item_id=payload.source_item_id,
            )

        current_saved_count = (
            db.query(UserSavedItem)
            .filter(UserSavedItem.user_id == current_user.id)
            .count()
        )

        enforce_free_usage_limit(
            db=db,
            user=user,
            feature_key="saved_items",
            current_count=current_saved_count,
            requested_count=1,
            label="saved items",
        )

        return save_item_for_user(
            db,
            user_id=current_user.id,
            content_type=payload.content_type,
            source_item_id=payload.source_item_id,
        )

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save item: {exc}",
        ) from exc


@router.get("")
def list_saved_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
    content_type: Optional[str] = Query(None),
    query: Optional[str] = Query(None, min_length=1, max_length=100),
    sort: str = Query(
        "newest",
        description="newest | oldest | title_asc | title_desc",
    ),
    limit: int = Query(20, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    try:
        sort = (
            sort
            if sort in {"newest", "oldest", "title_asc", "title_desc"}
            else "newest"
        )

        return list_saved_items_for_user(
            db,
            user_id=current_user.id,
            content_type=content_type,
            query=query,
            sort=sort,
            limit=limit,
            skip=skip,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load saved items: {exc}",
        ) from exc


@router.get("/check")
def check_saved_item(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
    content_type: str = Query(...),
    source_item_id: int = Query(..., gt=0),
):
    try:
        return check_saved_item_for_user(
            db,
            user_id=current_user.id,
            content_type=content_type,
            source_item_id=source_item_id,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check saved item: {exc}",
        ) from exc


@router.delete("/{saved_item_id}")
def remove_saved_item(
    saved_item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    try:
        deleted = delete_saved_item_for_user(
            db,
            user_id=current_user.id,
            saved_item_id=saved_item_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Saved item not found",
            )

        return {"deleted": True, "saved_item_id": saved_item_id}

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete saved item: {exc}",
        ) from exc


@router.get("/check/bulk")
def check_bulk_saved_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
    content_type: str = Query(...),
    ids: str = Query(...),
):
    source_item_ids = [
        int(value)
        for value in ids.split(",")
        if value.strip().isdigit()
    ]

    return check_bulk_saved_items_for_user(
        db,
        user_id=current_user.id,
        content_type=content_type,
        source_item_ids=source_item_ids,
    )