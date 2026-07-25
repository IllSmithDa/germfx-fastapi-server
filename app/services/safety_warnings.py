# app/services/safety_warnings.py

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models import DrugDetail, DrugIndex
from app.util.safety_warnings_parser import extract_safety_warnings


SafetyWarningPayload = Dict[str, Any]


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
                    .order_by(
                        DrugDetail.effective_time.desc().nullslast(),
                        DrugDetail.id.desc(),
                    )
                    .first()
                )

    return detail


def _empty_payload(
    *,
    drug_detail_id: int | None = None,
    message: str | None = None,
    source: str = "generated",
    warnings_raw_count: int = 0,
) -> SafetyWarningPayload:
    payload: SafetyWarningPayload = {
        "drug_detail_id": drug_detail_id,
        "warning_categories": [],
        "warnings_grouped": {},
        "warnings_flat": [],
        "raw_text": "",
        "safety_warnings_source": source,
        "matched_from_fields": {
            "warnings_raw_count": warnings_raw_count,
        },
    }

    if message:
        payload["message"] = message

    return payload


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    out: list[str] = []
    seen: set[str] = set()

    for item in value:
        text = str(item or "").strip()

        if not text:
            continue

        key = text.lower()

        if key in seen:
            continue

        seen.add(key)
        out.append(text)

    return out


def _normalize_warning_item(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None

    key = str(value.get("key") or "").strip()
    title = str(value.get("title") or "").strip()

    if not key or not title:
        return None

    return {
        "key": key,
        "title": title,
        "matched_terms": _string_list(value.get("matched_terms")),
        "excerpts": _string_list(value.get("excerpts")),
    }


def _normalize_warnings_flat(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in value:
        normalized = _normalize_warning_item(item)

        if not normalized:
            continue

        key = normalized["key"].lower()

        if key in seen:
            continue

        seen.add(key)
        out.append(normalized)

    return out


def _normalize_warnings_grouped(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}

    out: dict[str, dict[str, Any]] = {}

    for raw_key, raw_item in value.items():
        key = str(raw_key or "").strip()

        if not key or not isinstance(raw_item, dict):
            continue

        title = str(raw_item.get("title") or key).strip()

        out[key] = {
            "title": title,
            "matched_terms": _string_list(raw_item.get("matched_terms")),
            "excerpts": _string_list(raw_item.get("excerpts")),
        }

    return out


def _normalize_safety_warnings_payload(
    value: Any,
    *,
    drug_detail_id: int,
    source: str,
    warnings_raw_count: int,
) -> SafetyWarningPayload | None:
    if not isinstance(value, dict):
        return None

    warnings_flat = _normalize_warnings_flat(value.get("warnings_flat"))
    warnings_grouped = _normalize_warnings_grouped(value.get("warnings_grouped"))

    # If warnings_grouped is missing but warnings_flat exists, rebuild a grouped
    # dictionary so the shape stays compatible with fetchSafetyWarnings().
    if not warnings_grouped and warnings_flat:
        warnings_grouped = {
            item["key"]: {
                "title": item["title"],
                "matched_terms": item["matched_terms"],
                "excerpts": item["excerpts"],
            }
            for item in warnings_flat
        }

    warning_categories = _string_list(value.get("warning_categories"))

    if not warning_categories and warnings_flat:
        warning_categories = [item["key"] for item in warnings_flat]

    return {
        "drug_detail_id": drug_detail_id,
        "warning_categories": warning_categories,
        "warnings_grouped": warnings_grouped,
        "warnings_flat": warnings_flat,
        "raw_text": str(value.get("raw_text") or ""),
        "safety_warnings_source": source,
        "matched_from_fields": {
            "warnings_raw_count": warnings_raw_count,
            **(
                value.get("matched_from_fields")
                if isinstance(value.get("matched_from_fields"), dict)
                else {}
            ),
        },
    }


def _build_generated_safety_warnings(detail: DrugDetail) -> SafetyWarningPayload:
    warnings_raw = detail.warnings_raw or []
    parsed = extract_safety_warnings(warnings_raw)

    return {
        "drug_detail_id": detail.id,
        **parsed,
        "safety_warnings_source": "generated",
        "matched_from_fields": {
            "warnings_raw_count": len(warnings_raw),
        },
    }


def _build_curated_safety_warnings_payload(
    *,
    detail: DrugDetail,
    warnings_flat: list[dict[str, Any]],
    raw_text: str | None = None,
) -> SafetyWarningPayload:
    """
    Build the persisted JSONB shape for admin-edited safety warnings.

    This shape matches the public safety-warning response so the same UI can
    read curated data without reparsing warnings_raw on every request.
    """
    warnings_grouped = {
        item["key"]: {
            "title": item["title"],
            "matched_terms": item.get("matched_terms") or [],
            "excerpts": item.get("excerpts") or [],
        }
        for item in warnings_flat
    }

    warning_categories = [item["key"] for item in warnings_flat]

    resolved_raw_text = raw_text
    if resolved_raw_text is None:
        resolved_raw_text = "\n\n".join(
            str(excerpt or "").strip()
            for item in warnings_flat
            for excerpt in item.get("excerpts", [])
            if str(excerpt or "").strip()
        )

    return {
        "drug_detail_id": detail.id,
        "warning_categories": warning_categories,
        "warnings_grouped": warnings_grouped,
        "warnings_flat": warnings_flat,
        "raw_text": resolved_raw_text or "",
        "safety_warnings_source": "curated",
        "matched_from_fields": {
            "warnings_raw_count": len(detail.warnings_raw or []),
        },
    }


def _save_generated_safety_warnings_if_empty(
    db: Session,
    *,
    detail: DrugDetail,
    payload: SafetyWarningPayload,
) -> None:
    # Only save generated values when the curated/cache field is empty.
    # Once an admin edits this JSONB field, this service will return the saved
    # curated value and will not overwrite it during normal extraction reads.
    if getattr(detail, "safety_warnings_curated", None):
        return

    detail.safety_warnings_curated = {
        "warning_categories": payload.get("warning_categories") or [],
        "warnings_grouped": payload.get("warnings_grouped") or {},
        "warnings_flat": payload.get("warnings_flat") or [],
        "raw_text": payload.get("raw_text") or "",
        "matched_from_fields": payload.get("matched_from_fields") or {},
    }

    db.add(detail)
    db.commit()
    db.refresh(detail)


def extract_safety_warnings_for_detail(
    db: Session,
    *,
    detail_id: Optional[int] = None,
    drug_index_id: Optional[int] = None,
    force_regenerate: bool = False,
) -> Dict[str, Any]:
    detail = _get_detail_by_ids(
        db,
        detail_id=detail_id,
        drug_index_id=drug_index_id,
    )

    if not detail:
        return _empty_payload(
            message="Drug detail not found",
            source="generated",
        )

    warnings_raw_count = len(detail.warnings_raw or [])

    if not force_regenerate:
        cached_payload = _normalize_safety_warnings_payload(
            getattr(detail, "safety_warnings_curated", None),
            drug_detail_id=detail.id,
            source="curated",
            warnings_raw_count=warnings_raw_count,
        )

        if cached_payload is not None:
            return cached_payload

    generated_payload = _build_generated_safety_warnings(detail)

    if not force_regenerate:
        _save_generated_safety_warnings_if_empty(
            db,
            detail=detail,
            payload=generated_payload,
        )

        cached_payload = _normalize_safety_warnings_payload(
            getattr(detail, "safety_warnings_curated", None),
            drug_detail_id=detail.id,
            source="curated",
            warnings_raw_count=warnings_raw_count,
        )

        if cached_payload is not None:
            return cached_payload

    return generated_payload


def save_curated_safety_warnings_for_detail(
    db: Session,
    *,
    detail: DrugDetail,
    warnings_flat: list[dict[str, Any]],
    raw_text: str | None = None,
) -> SafetyWarningPayload:
    """
    Persist admin-edited structured safety warnings to DrugDetail.safety_warnings_curated.

    This intentionally does not modify warnings_raw. The public extraction helper
    will return this saved JSONB value on future reads.
    """
    payload = _build_curated_safety_warnings_payload(
        detail=detail,
        warnings_flat=warnings_flat,
        raw_text=raw_text,
    )

    detail.safety_warnings_curated = {
        "warning_categories": payload.get("warning_categories") or [],
        "warnings_grouped": payload.get("warnings_grouped") or {},
        "warnings_flat": payload.get("warnings_flat") or [],
        "raw_text": payload.get("raw_text") or "",
        "matched_from_fields": payload.get("matched_from_fields") or {},
    }

    db.add(detail)
    db.commit()
    db.refresh(detail)

    return payload