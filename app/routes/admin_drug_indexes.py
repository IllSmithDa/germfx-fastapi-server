from __future__ import annotations

import math
from typing import Any, Dict, Literal, Optional

from app.schemas.admin import DrugIndexCodeUpdateRequest
from app.services.drug_index import upsert_drug_index
from app.services.openfda import search_drug_names
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DrugIndex, User
from app.routes.admin_users import require_admin
from datetime import datetime, timedelta, timezone

router = APIRouter(tags=["admin-drug-indexes"])


DrugIndexKind = Literal["brand", "generic", "substance"]
DrugIndexSort = Literal[
    "updated_desc",
    "updated_asc",
    "created_desc",
    "created_asc",
    "name_asc",
    "name_desc",
]


def _clean_code(value: Any) -> str | None:
    code = str(value or "").strip()

    if not code:
        return None

    return code


def _digits_only(value: Any) -> str | None:
    digits = "".join(
        ch for ch in str(value or "")
        if ch.isdigit()
    )

    return digits or None


def _code_variants(value: Any) -> list[str]:
    raw = _clean_code(value)
    digits = _digits_only(value)

    values: list[str] = []

    if raw:
        values.append(raw)

    if digits and digits != raw:
        values.append(digits)

    return values


def _clean_code_list(values: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()

    for value in values or []:
        for code in _code_variants(value):
            if code in seen:
                continue

            seen.add(code)
            out.append(code)

    return out


def _remove_codes(
    existing: list[str] | None,
    remove_values: list[str],
) -> list[str] | None:
    remove_set = set()

    for value in remove_values:
        remove_set.update(_code_variants(value))

    kept = [
        code
        for code in existing or []
        if code not in remove_set
    ]

    return kept or None


def _merge_codes(
    existing: list[str] | None,
    incoming: list[str],
) -> list[str] | None:
    merged: list[str] = []
    seen: set[str] = set()

    for value in (existing or []) + incoming:
        for code in _code_variants(value):
            if code in seen:
                continue

            seen.add(code)
            merged.append(code)

    return merged or None


def _find_upc_conflict(
    db: Session,
    drug_index_id: int,
    upc_codes: list[str],
) -> DrugIndex | None:
    for code in upc_codes:
        existing = (
            db.query(DrugIndex)
            .filter(
                DrugIndex.id != drug_index_id,
                DrugIndex.upc_codes.any(code),
            )
            .first()
        )

        if existing:
            return existing

    return None

def _array_has_values(column):
    return and_(
        column.isnot(None),
        func.cardinality(column) > 0,
    )


def _array_missing_values(column):
    return or_(
        column.is_(None),
        func.cardinality(column) == 0,
    )


def _serialize_drug_index(row: DrugIndex) -> Dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "normalized_name": row.normalized_name,
        "kind": row.kind,
        "manufacturer": row.manufacturer,
        "source": row.source,
        "ndc_codes": row.ndc_codes or [],
        "upc_codes": row.upc_codes or [],
        "latest_detail_id": row.latest_detail_id,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _sort_clause(sort: DrugIndexSort):
    if sort == "updated_asc":
        return (
            DrugIndex.updated_at.asc().nullslast(),
            DrugIndex.id.asc(),
        )

    if sort == "created_desc":
        return (
            DrugIndex.created_at.desc().nullslast(),
            DrugIndex.id.desc(),
        )

    if sort == "created_asc":
        return (
            DrugIndex.created_at.asc().nullslast(),
            DrugIndex.id.asc(),
        )

    if sort == "name_asc":
        return (
            DrugIndex.name.asc(),
            DrugIndex.id.asc(),
        )

    if sort == "name_desc":
        return (
            DrugIndex.name.desc(),
            DrugIndex.id.desc(),
        )

    return (
        DrugIndex.updated_at.desc().nullslast(),
        DrugIndex.id.desc(),
    )

def _as_aware_utc(value):
    if not value:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def _iso_or_none(value):
    aware = _as_aware_utc(value)

    if not aware:
        return None

    return aware.isoformat()


def _build_query_freshness_filters(
    *,
    query: str | None,
    kind: DrugIndexKind | None,
    source: str | None,
    manufacturer: str | None,
):
    """
    These filters define the local data group used to decide whether
    OpenFDA sync is fresh enough.

    Do not include has_upc/has_ndc here because those are curation filters,
    not search freshness filters.
    """
    filters = []

    if query:
        normalized_query = query.lower()

        filters.append(
            or_(
                DrugIndex.name.ilike(f"%{query}%"),
                DrugIndex.normalized_name.ilike(f"%{normalized_query}%"),
                DrugIndex.manufacturer.ilike(f"%{query}%"),
            )
        )

    if kind:
        filters.append(DrugIndex.kind == kind)

    if source:
        filters.append(DrugIndex.source == source.strip())

    if manufacturer:
        filters.append(
            DrugIndex.manufacturer.ilike(f"%{manufacturer.strip()}%")
        )

    return filters


def _get_youngest_updated_at(
    db: Session,
    filters,
):
    if not filters:
        return None

    where_clause = and_(*filters)

    return db.execute(
        select(func.max(DrugIndex.updated_at)).where(where_clause)
    ).scalar_one_or_none()


def _should_sync_openfda(
    youngest_updated_at,
    *,
    stale_after_days: int,
) -> bool:
    if not youngest_updated_at:
        return True

    youngest = _as_aware_utc(youngest_updated_at)

    if not youngest:
        return True

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=stale_after_days)

    return youngest <= cutoff


def _touch_matching_drug_indexes(
    db: Session,
    filters,
) -> int:
    """
    Touch matching local rows after an OpenFDA sync attempt.

    This prevents the same admin search from repeatedly syncing OpenFDA
    within the freshness window, even if OpenFDA returned no new changes.
    """
    if not filters:
        return 0

    where_clause = and_(*filters)

    touched_count = (
        db.query(DrugIndex)
        .filter(where_clause)
        .update(
            {
                DrugIndex.updated_at: func.now(),
            },
            synchronize_session=False,
        )
    )

    db.commit()

    return int(touched_count or 0)

@router.get("/drug-indexes")
async def list_admin_drug_indexes(
    q: Optional[str] = Query(None, max_length=120),
    kind: Optional[DrugIndexKind] = Query(None),
    source: Optional[str] = Query(None, max_length=80),
    manufacturer: Optional[str] = Query(None, max_length=120),

    has_upc: Optional[bool] = Query(None),
    has_ndc: Optional[bool] = Query(None),
    has_latest_detail: Optional[bool] = Query(None),

    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),

    sort: DrugIndexSort = Query("updated_desc"),

    # Admin-specific sync behavior.
    # If q is provided, this route will attempt OpenFDA sync before local query.
    sync_openfda: bool = Query(True),
    openfda_limit: int = Query(100, ge=1, le=100),
    sync_stale_after_days: int = Query(1, ge=1, le=30),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin-only paginated DrugIndex browser.

    Final mounted route:
    GET /api/admin/drug-indexes

    Admin behavior:
    - If q is provided and sync_openfda=true, search OpenFDA first.
    - Upsert any returned index rows.
    - Then query local DrugIndex rows using the requested filters.
    """
    query = q.strip() if q else None

    freshness_filters = _build_query_freshness_filters(
        query=query,
        kind=kind,
        source=source,
        manufacturer=manufacturer,
    )

    youngest_updated_at = _get_youngest_updated_at(
        db,
        freshness_filters,
    )

    should_sync = (
        bool(query)
        and sync_openfda
        and _should_sync_openfda(
            youngest_updated_at,
            stale_after_days=sync_stale_after_days,
        )
    )

    openfda_sync = {
        "requested": bool(query and sync_openfda),
        "attempted": False,
        "skipped": bool(query and sync_openfda and not should_sync),
        "skip_reason": (
            "fresh_local_data"
            if query and sync_openfda and not should_sync
            else None
        ),
        "query": query,
        "remote_count": 0,
        "upserted": False,
        "touched_local_count": 0,
        "youngest_updated_at": _iso_or_none(youngest_updated_at),
        "sync_stale_after_days": sync_stale_after_days,
    }

    if should_sync:
        openfda_sync["attempted"] = True

        remote_items = await search_drug_names(
            query,
            limit=openfda_limit,
        )

        openfda_sync["remote_count"] = len(remote_items)

        if remote_items:
            upsert_drug_index(
                db,
                remote_items,
            )

            openfda_sync["upserted"] = True

        # Rebuild freshness filters after upsert so newly inserted rows
        # can also be included in the touch operation.
        freshness_filters = _build_query_freshness_filters(
            query=query,
            kind=kind,
            source=source,
            manufacturer=manufacturer,
        )

        touched_count = _touch_matching_drug_indexes(
            db,
            freshness_filters,
        )

        openfda_sync["touched_local_count"] = touched_count

        youngest_updated_at = _get_youngest_updated_at(
            db,
            freshness_filters,
        )

        openfda_sync["youngest_updated_at"] = _iso_or_none(
            youngest_updated_at
        )

    filters = []
    if query:
      normalized_query = query.lower()
      filters.append(
          or_(
              DrugIndex.name.ilike(f"%{query}%"),
              DrugIndex.normalized_name.ilike(f"%{normalized_query}%"),
              DrugIndex.manufacturer.ilike(f"%{query}%"),
          )
      )
    if kind:
      filters.append(DrugIndex.kind == kind)

    if source:
      filters.append(DrugIndex.source == source.strip())

    if manufacturer:
      filters.append(
          DrugIndex.manufacturer.ilike(f"%{manufacturer.strip()}%")
      )

    if has_upc is True:
      filters.append(_array_has_values(DrugIndex.upc_codes))
    elif has_upc is False:
      filters.append(_array_missing_values(DrugIndex.upc_codes))

    if has_ndc is True:
      filters.append(_array_has_values(DrugIndex.ndc_codes))
    elif has_ndc is False:
      filters.append(_array_missing_values(DrugIndex.ndc_codes))

    if has_latest_detail is True:
      filters.append(DrugIndex.latest_detail_id.isnot(None))
    elif has_latest_detail is False:
      filters.append(DrugIndex.latest_detail_id.is_(None))

    where_clause = and_(*filters) if filters else None

    count_stmt = select(func.count(DrugIndex.id))

    if where_clause is not None:
      count_stmt = count_stmt.where(where_clause)

    total = int(db.execute(count_stmt).scalar() or 0)

    offset = (page - 1) * page_size

    stmt = select(DrugIndex)

    if where_clause is not None:
      stmt = stmt.where(where_clause)

    stmt = (
      stmt
      .order_by(*_sort_clause(sort))
      .offset(offset)
      .limit(page_size)
    )

    rows = db.execute(stmt).scalars().all()

    total_pages = math.ceil(total / page_size) if total else 0

    return {
      "items": [
          _serialize_drug_index(row)
          for row in rows
      ],
      "pagination": {
          "page": page,
          "page_size": page_size,
          "total": total,
          "total_pages": total_pages,
          "has_next": page < total_pages,
          "has_prev": page > 1,
      },
      "filters": {
          "q": q,
          "kind": kind,
          "source": source,
          "manufacturer": manufacturer,
          "has_upc": has_upc,
          "has_ndc": has_ndc,
          "has_latest_detail": has_latest_detail,
          "sort": sort,
          "sync_openfda": sync_openfda,
          "openfda_limit": openfda_limit,
          "sync_stale_after_days": sync_stale_after_days,
      },
      "openfda_sync": openfda_sync,
    }

@router.patch("/drug-indexes/{drug_index_id}/codes")
def update_admin_drug_index_codes(
    drug_index_id: int,
    payload: DrugIndexCodeUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """
    Admin-only route for adding/removing curated UPC/NDC codes.

    Final mounted route:
    PATCH /api/admin/drug-indexes/{drug_index_id}/codes
    """
    row = db.get(
        DrugIndex,
        drug_index_id,
    )
    print("row test: ", row)
    if not row:
        raise HTTPException(
            status_code=404,
            detail="Drug index not found.",
        )

    add_upc_codes = _clean_code_list(
        payload.add_upc_codes
    )

    add_ndc_codes = _clean_code_list(
        payload.add_ndc_codes
    )

    remove_upc_codes = _clean_code_list(
        payload.remove_upc_codes
    )

    remove_ndc_codes = _clean_code_list(
        payload.remove_ndc_codes
    )

    if add_upc_codes:
        conflict = _find_upc_conflict(
            db,
            drug_index_id,
            add_upc_codes,
        )

        if conflict:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"UPC code already belongs to "
                    f"{conflict.name}."
                ),
            )

    row.upc_codes = _remove_codes(
        row.upc_codes,
        remove_upc_codes,
    )

    row.ndc_codes = _remove_codes(
        row.ndc_codes,
        remove_ndc_codes,
    )

    row.upc_codes = _merge_codes(
        row.upc_codes,
        add_upc_codes,
    )

    row.ndc_codes = _merge_codes(
        row.ndc_codes,
        add_ndc_codes,
    )

    db.add(row)
    db.commit()
    db.refresh(row)

    return _serialize_drug_index(row)