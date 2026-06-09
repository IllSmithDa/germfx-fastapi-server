# app/services/safety_warnings.py

from __future__ import annotations

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models import DrugDetail, DrugIndex
from app.util.safety_warnings_parser import extract_safety_warnings


def _get_detail_by_ids(
    db: Session,
    *,
    detail_id: Optional[int] = None,
    drug_index_id: Optional[int] = None,
) -> Optional[DrugDetail]:
    detail = None

    if detail_id:
        detail = db.get(DrugDetail, detail_id)

    elif drug_index_id:
        idx = db.get(DrugIndex, drug_index_id)
        if idx:
            latest_id = getattr(idx, "latest_detail_id", None)
            detail = db.get(DrugDetail, latest_id) if latest_id else None

            if not detail:
                detail = (
                    db.query(DrugDetail)
                    .filter(DrugDetail.drug_index_id == idx.id)
                    .order_by(DrugDetail.effective_time.desc().nullslast(), DrugDetail.id.desc())
                    .first()
                )

    return detail


def extract_safety_warnings_for_detail(
    db: Session,
    *,
    detail_id: Optional[int] = None,
    drug_index_id: Optional[int] = None,
) -> Dict[str, Any]:
    detail = _get_detail_by_ids(db, detail_id=detail_id, drug_index_id=drug_index_id)

    if not detail:
        return {
            "drug_detail_id": None,
            "warning_categories": [],
            "warnings_grouped": {},
            "warnings_flat": [],
            "raw_text": "",
            "message": "Drug detail not found",
        }

    parsed = extract_safety_warnings(detail.warnings_raw or [])

    return {
        "drug_detail_id": detail.id,
        **parsed,
        "matched_from_fields": {
            "warnings_raw_count": len(detail.warnings_raw or []),
        },
    }