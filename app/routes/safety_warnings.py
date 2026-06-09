from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.safety_warnings import extract_safety_warnings_for_detail

router = APIRouter()


@router.get("/extract")
def extract_safety_warnings(
    db: Session = Depends(get_db),
    detail_id: Optional[int] = Query(None),
    drug_index_id: Optional[int] = Query(None),
):
    if not detail_id and not drug_index_id:
        raise HTTPException(
            status_code=400,
            detail="Provide either detail_id or drug_index_id",
        )

    result = extract_safety_warnings_for_detail(
        db,
        detail_id=detail_id,
        drug_index_id=drug_index_id,
    )

    if not result.get("drug_detail_id"):
        raise HTTPException(status_code=404, detail="Drug detail not found")

    return result