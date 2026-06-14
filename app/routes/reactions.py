from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db import get_db
from app.core.auth import get_authenticated_user, get_optional_user
from app.models import User
from app.services.reactions import (
    get_reaction_summary,
    get_bulk_reaction_summaries,
    remove_reaction,
    toggle_reaction,
)


router = APIRouter(tags=["reactions"])


class ToggleReactionRequest(BaseModel):
    content_type: str
    source_item_id: int
    reaction_type: str


@router.post("/toggle")
def toggle_content_reaction(
    payload: ToggleReactionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    try:
        return toggle_reaction(
            db,
            user_id=current_user.id,
            content_type=payload.content_type,
            source_item_id=payload.source_item_id,
            reaction_type=payload.reaction_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update reaction: {exc}",
        ) from exc


@router.get("/summary")
def read_reaction_summary(
    content_type: str = Query(...),
    source_item_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    try:
        return get_reaction_summary(
            db,
            user_id=current_user.id,
            content_type=content_type,
            source_item_id=source_item_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/summary/bulk")
def read_bulk_reaction_summaries(
    content_type: str = Query(...),
    ids: str = Query(...),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        source_item_ids = [
            int(value)
            for value in ids.split(",")
            if value.strip().isdigit()
        ]

        return get_bulk_reaction_summaries(
            db,
            user_id=current_user.id if current_user else None,
            content_type=content_type,
            source_item_ids=source_item_ids,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete("")
def delete_content_reaction(
    content_type: str = Query(...),
    source_item_id: int = Query(..., gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_authenticated_user),
):
    try:
        return remove_reaction(
            db,
            user_id=current_user.id,
            content_type=content_type,
            source_item_id=source_item_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc