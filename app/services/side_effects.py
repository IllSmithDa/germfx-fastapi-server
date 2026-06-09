# app/services/side_effects.py

from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from app.models import DrugDetail, DrugIndex
from app.util.side_effects_parser import classify_side_effects
from app.util.side_effect_descriptions import SIDE_EFFECT_DESCRIPTIONS


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


def _describe_side_effects(items: List[str]) -> List[Dict[str, str]]:
    described: List[Dict[str, str]] = []

    for item in items or []:
        described.append({
            "name": item,
            "description": SIDE_EFFECT_DESCRIPTIONS.get(
                item,
                "A reported reaction mentioned in the drug label."
            ),
        })

    return described


def _build_described_classified(classified: Dict[str, List[str]]) -> Dict[str, List[Dict[str, str]]]:
    return {
        "common_or_likely": _describe_side_effects(classified.get("common_or_likely", [])),
        "possible": _describe_side_effects(classified.get("possible", [])),
        "serious": _describe_side_effects(classified.get("serious", [])),
        "all": _describe_side_effects(classified.get("all", [])),
    }


def extract_and_save_side_effects_for_detail(
    db: Session,
    *,
    detail_id: Optional[int] = None,
    drug_index_id: Optional[int] = None,
) -> Dict[str, Any]:
    detail = _get_detail_by_ids(db, detail_id=detail_id, drug_index_id=drug_index_id)

    if not detail:
        empty_classified = {
            "common_or_likely": [],
            "possible": [],
            "serious": [],
            "all": [],
        }
        return {
            "side_effects": [],
            "classified": empty_classified,
            "classified_described": {
                "common_or_likely": [],
                "possible": [],
                "serious": [],
                "all": [],
            },
            "drug_detail_id": None,
            "message": "Drug detail not found",
        }

    classified = classify_side_effects(
        adverse_reactions=detail.adverse_reactions or [],
        warnings_raw=detail.warnings_raw or [],
        boxed_warning=detail.boxed_warning or [],
    )

    classified_described = _build_described_classified(classified)

    detail.side_effects = classified["all"]
    db.add(detail)
    db.commit()
    db.refresh(detail)

    return {
        "side_effects": detail.side_effects or [],
        "classified": classified,
        "classified_described": classified_described,
        "drug_detail_id": detail.id,
        "matched_from_fields": {
            "adverse_reactions_count": len(detail.adverse_reactions or []),
            "warnings_raw_count": len(detail.warnings_raw or []),
            "boxed_warning_count": len(detail.boxed_warning or []),
        },
    }