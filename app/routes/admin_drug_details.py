import re
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models
from app.core.auth import get_authenticated_user
from app.db import get_db
from app.models import DrugDetail, DrugIndex
from app.services.drug_details import resync_drug_detail_by_id
from app.services.safety_warnings import (
    extract_safety_warnings_for_detail,
    save_curated_safety_warnings_for_detail,
)
from app.util.normalize_drug_details import _build_payload


router = APIRouter()


class AdminDrugDetailOut(BaseModel):
    id: int
    drug_index_id: int | None = None
    index_name: str | None = None
    index_kind: str | None = None
    index_latest_detail_id: int | None = None
    latest_for_index: bool = False

    name: str | None = None
    normalized_name: str | None = None
    source: str | None = None
    query_used: str | None = None
    effective_time: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

    brand_names: list[str] = Field(default_factory=list)
    generic_names: list[str] = Field(default_factory=list)
    manufacturer_names: list[str] = Field(default_factory=list)

    warnings_count: int = 0
    warnings_simple_count: int = 0
    side_effects_count: int = 0
    indications_count: int = 0
    adverse_reactions_count: int = 0
    interactions_count: int = 0
    dosage_count: int = 0

    has_warnings: bool = False
    has_clean_fields: bool = False


class AdminDrugDetailListOut(BaseModel):
    items: list[AdminDrugDetailOut]
    total: int
    page: int
    page_size: int
    has_next: bool


class AdminDrugDetailEditableFieldsOut(BaseModel):
    purpose_or_indications: list[str] = Field(default_factory=list)
    dosage_and_administration: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    warnings_simple: list[str] = Field(default_factory=list)


class AdminDrugDetailReadOut(BaseModel):
    detail: AdminDrugDetailOut
    payload: dict[str, Any]
    editable_fields: AdminDrugDetailEditableFieldsOut
    safety_warnings: dict[str, Any] = Field(default_factory=dict)


class AdminDrugDetailResyncOut(BaseModel):
    message: str
    drug_detail_id: int
    requested_detail_id: int
    updated_by_user_id: int
    make_latest: bool
    reset_clean_fields: bool
    payload: dict[str, Any]
    editable_fields: AdminDrugDetailEditableFieldsOut
    safety_warnings: dict[str, Any] = Field(default_factory=dict)


class AdminDrugDetailCuratedFieldsUpdateRequest(BaseModel):
    purpose_or_indications: list[str] = Field(default_factory=list)
    dosage_and_administration: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    warnings_simple: list[str] = Field(default_factory=list)


class AdminSafetyWarningItem(BaseModel):
    key: str | None = Field(default=None, max_length=120)
    title: str = Field(default="", max_length=200)
    matched_terms: list[str] = Field(default_factory=list)
    excerpts: list[str] = Field(default_factory=list)


class AdminDrugDetailSafetyWarningsUpdateRequest(BaseModel):
    warnings_flat: list[AdminSafetyWarningItem] = Field(default_factory=list)
    raw_text: str | None = Field(default=None, max_length=20000)


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


def _safe_len(value: Any) -> int:
    if isinstance(value, list):
        return len(value)

    if isinstance(value, dict):
        return len(value)

    if isinstance(value, str):
        return 1 if value.strip() else 0

    return 0


def _iso(value: Any) -> str | None:
    if not value:
        return None

    if hasattr(value, "isoformat"):
        return value.isoformat()

    return str(value)


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


def _clean_string_list(
    value: Any,
    *,
    max_items: int = 200,
    max_chars: int = 2000,
) -> list[str]:
    if not isinstance(value, list):
        return []

    out: list[str] = []
    seen: set[str] = set()

    for item in value:
        text = str(item or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        text = " ".join(text.split())

        if not text:
            continue

        if len(text) > max_chars:
            text = text[:max_chars].strip()

        key = text.lower()

        if key in seen:
            continue

        seen.add(key)
        out.append(text)

        if len(out) >= max_items:
            break

    return out


def _editable_fields_out(detail: DrugDetail) -> dict[str, list[str]]:
    return {
        "purpose_or_indications": _string_list(
            getattr(detail, "purpose_or_indications", None)
        ),
        "dosage_and_administration": _string_list(
            getattr(detail, "dosage_and_administration", None)
        ),
        "side_effects": _string_list(getattr(detail, "side_effects", None)),
        "warnings_simple": _string_list(getattr(detail, "warnings_simple", None)),
    }


def _slugify_warning_key(value: str, fallback: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return key or fallback


def _clean_safety_warning_items(
    items: list[AdminSafetyWarningItem],
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    used_keys: set[str] = set()

    for index, item in enumerate(items or []):
        title = str(item.title or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        title = " ".join(title.split())

        matched_terms = _clean_string_list(
            item.matched_terms,
            max_items=30,
            max_chars=120,
        )
        excerpts = _clean_string_list(
            item.excerpts,
            max_items=40,
            max_chars=2000,
        )

        # Do not save completely empty cards.
        if not title and not matched_terms and not excerpts:
            continue

        if not title:
            title = f"Warning {index + 1}"

        base_key = _slugify_warning_key(
            str(item.key or title),
            fallback=f"warning_{index + 1}",
        )

        key = base_key
        suffix = 2

        while key in used_keys:
            key = f"{base_key}_{suffix}"
            suffix += 1

        used_keys.add(key)

        cleaned.append(
            {
                "key": key,
                "title": title,
                "matched_terms": matched_terms,
                "excerpts": excerpts,
            }
        )

    return cleaned


def _admin_safety_warnings_out(
    db: Session,
    *,
    detail_id: int,
) -> dict[str, Any]:
    """
    Return the same structured safety-warning shape used by the public
    drug detail page. This is separate from warnings_simple, which is the
    editable curated string list.
    """
    result = extract_safety_warnings_for_detail(
        db,
        detail_id=detail_id,
    )

    return {
        "drug_detail_id": result.get("drug_detail_id"),
        "warning_categories": result.get("warning_categories") or [],
        "warnings_grouped": result.get("warnings_grouped") or {},
        "warnings_flat": result.get("warnings_flat") or [],
        "raw_text": result.get("raw_text") or "",
        "safety_warnings_source": result.get("safety_warnings_source") or "curated",
        "matched_from_fields": result.get("matched_from_fields") or {},
        "message": result.get("message"),
    }


def _admin_payload_out(
    detail: DrugDetail,
    index_row: DrugIndex | None = None,
) -> dict[str, Any]:
    """
    Build the admin detail payload from the saved DrugDetail row.

    The regular public drug page gets side effects and warning highlights from
    database-backed extraction routes. The admin detail endpoint should expose
    those same saved database fields directly instead of relying only on the
    base OpenFDA payload builder.
    """
    base_payload = _build_payload(detail, index_row) or {}
    payload = dict(base_payload)

    payload.update(
        {
            "drug_detail_id": detail.id,
            "drug_index_id": getattr(detail, "drug_index_id", None),
            "purpose_or_indications": _string_list(
                getattr(detail, "purpose_or_indications", None)
            ),
            "dosage_and_administration": _string_list(
                getattr(detail, "dosage_and_administration", None)
            ),
            "side_effects": _string_list(getattr(detail, "side_effects", None)),
            "warnings_simple": _string_list(getattr(detail, "warnings_simple", None)),
            "warnings_raw": _string_list(getattr(detail, "warnings_raw", None)),
            "warnings_key": getattr(detail, "warnings_key", None) or {},
            "stop_using_warnings": _string_list(
                getattr(detail, "stop_using_warnings", None)
            ),
            "adverse_reactions": _string_list(
                getattr(detail, "adverse_reactions", None)
            ),
            "drug_interactions": _string_list(
                getattr(detail, "drug_interactions", None)
            ),
            "boxed_warning": _string_list(getattr(detail, "boxed_warning", None)),
            "symptoms_table": _string_list(getattr(detail, "symptoms_table", None)),
            "safety_warnings_curated": getattr(
                detail,
                "safety_warnings_curated",
                None,
            ),
        }
    )

    return payload


def _admin_drug_detail_out(
    detail: DrugDetail,
    index_row: DrugIndex | None = None,
) -> dict[str, Any]:
    warnings_count = _safe_len(getattr(detail, "warnings_raw", None))
    warnings_simple_count = _safe_len(getattr(detail, "warnings_simple", None))
    side_effects_count = _safe_len(getattr(detail, "side_effects", None))

    index_latest_detail_id = (
        getattr(index_row, "latest_detail_id", None) if index_row else None
    )

    return {
        "id": detail.id,
        "drug_index_id": getattr(detail, "drug_index_id", None),
        "index_name": getattr(index_row, "name", None) if index_row else None,
        "index_kind": getattr(index_row, "kind", None) if index_row else None,
        "index_latest_detail_id": index_latest_detail_id,
        "latest_for_index": bool(index_latest_detail_id == detail.id),
        "name": getattr(detail, "name", None),
        "normalized_name": getattr(detail, "normalized_name", None),
        "source": getattr(detail, "source", None),
        "query_used": getattr(detail, "query_used", None),
        "effective_time": _iso(getattr(detail, "effective_time", None)),
        "created_at": _iso(getattr(detail, "created_at", None)),
        "updated_at": _iso(getattr(detail, "updated_at", None)),
        "brand_names": _string_list(getattr(detail, "brand_names", None)),
        "generic_names": _string_list(getattr(detail, "generic_names", None)),
        "manufacturer_names": _string_list(
            getattr(detail, "manufacturer_names", None)
        ),
        "warnings_count": warnings_count,
        "warnings_simple_count": warnings_simple_count,
        "side_effects_count": side_effects_count,
        "indications_count": _safe_len(getattr(detail, "purpose_or_indications", None)),
        "adverse_reactions_count": _safe_len(getattr(detail, "adverse_reactions", None)),
        "interactions_count": _safe_len(getattr(detail, "drug_interactions", None)),
        "dosage_count": _safe_len(getattr(detail, "dosage_and_administration", None)),
        "has_warnings": warnings_count > 0,
        "has_clean_fields": warnings_simple_count > 0 or side_effects_count > 0,
    }


def _admin_detail_read_response(
    db: Session,
    detail: DrugDetail,
    index_row: DrugIndex | None = None,
) -> dict[str, Any]:
    """
    Shared admin read response builder.

    Important: this must build the response directly. Do not call
    _admin_detail_read_response() from inside itself.
    """
    return {
        "detail": _admin_drug_detail_out(detail, index_row),
        "payload": _admin_payload_out(detail, index_row),
        "editable_fields": _editable_fields_out(detail),
        "safety_warnings": _admin_safety_warnings_out(db, detail_id=detail.id),
    }


def _matches_optional_boolean_filter(
    *,
    value: bool,
    expected: bool | None,
) -> bool:
    if expected is None:
        return True

    return value is expected


def _get_admin_detail_row(
    db: Session,
    detail_id: int,
) -> tuple[DrugDetail, DrugIndex | None]:
    row = (
        db.query(DrugDetail, DrugIndex)
        .outerjoin(DrugIndex, DrugIndex.id == DrugDetail.drug_index_id)
        .filter(DrugDetail.id == detail_id)
        .first()
    )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "message": "Drug detail not found.",
                "code": "DRUG_DETAIL_NOT_FOUND",
            },
        )

    detail, index_row = row
    return detail, index_row


@router.get(
    "/drug-details",
    response_model=AdminDrugDetailListOut,
)
def list_admin_drug_details(
    query: str | None = Query(default=None, max_length=120),
    has_warnings: bool | None = Query(default=None),
    has_clean_fields: bool | None = Query(default=None),
    source: str | None = Query(default=None, max_length=80),
    sort: Literal["updated_desc", "created_desc", "name_asc"] = Query(
        default="updated_desc",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    details_query = (
        db.query(DrugDetail, DrugIndex)
        .outerjoin(DrugIndex, DrugIndex.id == DrugDetail.drug_index_id)
    )

    if query:
        search_value = query.strip()
        search_like = f"%{search_value.lower()}%"

        conditions = [
            func.lower(DrugDetail.name).like(search_like),
            func.lower(DrugDetail.normalized_name).like(search_like),
            func.lower(DrugDetail.query_used).like(search_like),
            func.lower(DrugIndex.name).like(search_like),
            func.lower(DrugIndex.normalized_name).like(search_like),
        ]

        if search_value.isdigit():
            numeric_id = int(search_value)
            conditions.extend(
                [
                    DrugDetail.id == numeric_id,
                    DrugDetail.drug_index_id == numeric_id,
                    DrugIndex.id == numeric_id,
                ]
            )

        details_query = details_query.filter(or_(*conditions))

    if source:
        details_query = details_query.filter(DrugDetail.source == source.strip())

    if sort == "name_asc":
        details_query = details_query.order_by(
            func.lower(DrugDetail.name).asc(),
            DrugDetail.id.desc(),
        )
    elif sort == "created_desc":
        details_query = details_query.order_by(
            DrugDetail.created_at.desc().nullslast(),
            DrugDetail.id.desc(),
        )
    else:
        details_query = details_query.order_by(
            DrugDetail.updated_at.desc().nullslast(),
            DrugDetail.id.desc(),
        )

    # These count filters are applied in Python so the route works whether
    # list-like fields are PostgreSQL ARRAY, JSON, or JSONB columns.
    all_items = [
        _admin_drug_detail_out(detail, index_row)
        for detail, index_row in details_query.all()
    ]

    filtered_items = [
        item
        for item in all_items
        if _matches_optional_boolean_filter(
            value=bool(item["has_warnings"]),
            expected=has_warnings,
        )
        and _matches_optional_boolean_filter(
            value=bool(item["has_clean_fields"]),
            expected=has_clean_fields,
        )
    ]

    total = len(filtered_items)
    offset = (page - 1) * page_size
    items = filtered_items[offset : offset + page_size]

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": offset + len(items) < total,
    }


@router.get(
    "/drug-details/{detail_id}",
    response_model=AdminDrugDetailReadOut,
)
def get_admin_drug_detail(
    detail_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    detail, index_row = _get_admin_detail_row(db, detail_id)
    return _admin_detail_read_response(db, detail, index_row)


@router.post(
    "/drug-details/{detail_id}/resync",
    response_model=AdminDrugDetailResyncOut,
)
async def force_resync_admin_drug_detail(
    detail_id: int,
    drug: Optional[str] = Query(
        None,
        description="Optional override search term for the OpenFDA resync.",
    ),
    make_latest: bool = Query(
        True,
        description="If true, set this detail as the DrugIndex latest_detail_id.",
    ),
    reset_clean_fields: bool = Query(
        True,
        description="If true, clear generated cleaner fields after raw OpenFDA resync.",
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    try:
        payload, resolved_detail_id = await resync_drug_detail_by_id(
            db,
            drug_detail_id=detail_id,
            drug_query=drug,
            make_latest=make_latest,
            reset_clean_fields=reset_clean_fields,
        )

        row = (
            db.query(DrugDetail, DrugIndex)
            .outerjoin(DrugIndex, DrugIndex.id == DrugDetail.drug_index_id)
            .filter(DrugDetail.id == resolved_detail_id)
            .first()
        )

        if row:
            detail, index_row = row
            response_payload = _admin_payload_out(detail, index_row)
            editable_fields = _editable_fields_out(detail)
        else:
            response_payload = payload
            editable_fields = {
                "purpose_or_indications": [],
                "dosage_and_administration": [],
                "side_effects": [],
                "warnings_simple": [],
            }

        return {
            "message": "Drug detail resynced successfully.",
            "drug_detail_id": resolved_detail_id,
            "requested_detail_id": detail_id,
            "updated_by_user_id": current_user.id,
            "make_latest": make_latest,
            "reset_clean_fields": reset_clean_fields,
            "payload": response_payload,
            "editable_fields": editable_fields,
            "safety_warnings": _admin_safety_warnings_out(
                db,
                detail_id=resolved_detail_id,
            ),
        }

    except ValueError as exc:
        message = str(exc)

        status_code_value = (
            status.HTTP_404_NOT_FOUND
            if "not found" in message.lower() or "no results" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )

        raise HTTPException(
            status_code=status_code_value,
            detail={
                "message": message,
                "code": "DRUG_DETAIL_RESYNC_FAILED",
            },
        )

    except Exception as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "message": str(exc),
                "code": "DRUG_DETAIL_RESYNC_FAILED",
            },
        )


@router.patch(
    "/drug-details/{detail_id}/curated-fields",
    response_model=AdminDrugDetailReadOut,
)
def update_admin_drug_detail_curated_fields(
    detail_id: int,
    payload: AdminDrugDetailCuratedFieldsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    detail, index_row = _get_admin_detail_row(db, detail_id)

    detail.purpose_or_indications = _clean_string_list(payload.purpose_or_indications)
    detail.dosage_and_administration = _clean_string_list(
        payload.dosage_and_administration
    )
    detail.side_effects = _clean_string_list(payload.side_effects)
    detail.warnings_simple = _clean_string_list(payload.warnings_simple)

    db.add(detail)
    db.commit()
    db.refresh(detail)

    if getattr(detail, "drug_index_id", None):
        index_row = db.get(DrugIndex, detail.drug_index_id)

    return _admin_detail_read_response(db, detail, index_row)


@router.patch(
    "/drug-details/{detail_id}/safety-warnings",
    response_model=AdminDrugDetailReadOut,
)
def update_admin_drug_detail_safety_warnings(
    detail_id: int,
    payload: AdminDrugDetailSafetyWarningsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_admin_user),
):
    detail, index_row = _get_admin_detail_row(db, detail_id)

    cleaned_warnings_flat = _clean_safety_warning_items(payload.warnings_flat)
    save_curated_safety_warnings_for_detail(
        db,
        detail=detail,
        warnings_flat=cleaned_warnings_flat,
        raw_text=payload.raw_text,
    )

    db.refresh(detail)

    if getattr(detail, "drug_index_id", None):
        index_row = db.get(DrugIndex, detail.drug_index_id)

    return _admin_detail_read_response(db, detail, index_row)