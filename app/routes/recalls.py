# app/routes/recalls.py

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.recalls import (
    get_recalls_from_db,
    should_sync_recalls,
    sync_recalls,
)

router = APIRouter(tags=["recalls"])


@router.get("")
def list_recalls(
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    source: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    sort: str = Query("latest"),
    sync_if_needed: bool = Query(True),
):
    try:
        if sync_if_needed and should_sync_recalls(db):
            sync_recalls(db)

        return get_recalls_from_db(
            db,
            limit=limit,
            skip=skip,
            source=source,
            query=query,
            state=state,
            sort=sort,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load recalls: {exc}",
        ) from exc
    
@router.post("/sync")
def run_recall_sync(
    db: Session = Depends(get_db),
):
    try:
        return sync_recalls(db)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync recalls: {exc}",
        ) from exc