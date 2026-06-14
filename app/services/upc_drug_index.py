from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from sqlalchemy import or_, case
from sqlalchemy.orm import Session

from app.models import DrugIndex
from app.services.drug_index import upsert_drug_index
from app.services.openfda import search_drug_index_items_by_code
from app.util.normailize_codes import build_code_lookup_candidates


DEFAULT_STALE_AFTER_DAYS = 90


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: datetime | None) -> datetime | None:
    if value is None:
        return None

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value


def _is_stale_drug_index(
    row: DrugIndex,
    *,
    stale_after_days: int,
) -> bool:
    """
    Only OpenFDA-backed index rows are considered stale.

    Admin/manual rows should not be automatically resynced because they are
    curated and should remain the source of truth.
    """
    if row.source != "openfda":
        return False

    updated_at = _normalize_datetime(row.updated_at)

    if updated_at is None:
        return True

    stale_before = _utc_now() - timedelta(days=stale_after_days)

    return updated_at < stale_before


def _serialize_drug_index(
    row: DrugIndex,
    *,
    stale_after_days: int,
) -> Dict[str, Any]:
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
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "is_stale": _is_stale_drug_index(
            row,
            stale_after_days=stale_after_days,
        ),
    }


def _query_drug_indexes_by_code_candidates(
    db: Session,
    candidates: list[str],
    *,
    limit: int,
) -> list[DrugIndex]:
    if not candidates:
        return []

    filters = []

    for candidate in candidates:
        filters.append(DrugIndex.upc_codes.any(candidate))
        filters.append(DrugIndex.ndc_codes.any(candidate))

    if not filters:
        return []

    kind_priority = case(
        (DrugIndex.kind == "brand", 0),
        (DrugIndex.kind == "generic", 1),
        (DrugIndex.kind == "substance", 2),
        else_=3,
    )
    
    return (
        db.query(DrugIndex)
        .filter(or_(*filters))
        .order_by(
            kind_priority.asc(),
            DrugIndex.updated_at.desc().nullslast(),
            DrugIndex.id.desc(),
        )
        .limit(limit)
        .all()
    )


async def resolve_drug_index_by_code(
    db: Session,
    *,
    code: str,
    limit: int = 25,
    stale_after_days: int = DEFAULT_STALE_AFTER_DAYS,
    force_resync: bool = False,
) -> Dict[str, Any]:
    """
    Resolve a UPC/NDC scan against DrugIndex first.

    Flow:
    1. Normalize scanned code into lookup candidates.
    2. Search DrugIndex.upc_codes and DrugIndex.ndc_codes.
    3. If local rows exist and are fresh, return them.
    4. If none exist, or OpenFDA rows are stale, search OpenFDA.
    5. Upsert matching OpenFDA results into DrugIndex.
    6. Re-query DrugIndex and return matches to the client.

    This intentionally does not search or create DrugDetail.
    """
    raw_code = (code or "").strip()

    if not raw_code:
        raise ValueError("Missing code")

    candidates = build_code_lookup_candidates(raw_code)
    '''
    print(
    "OpenFDA code lookup candidates:",
    {
        "raw_code": raw_code,
        "lookup_candidates": candidates,
    },
    )
    '''
    local_rows = _query_drug_indexes_by_code_candidates(
        db,
        candidates,
        limit=limit,
    )

    stale_local_rows = [
        row
        for row in local_rows
        if _is_stale_drug_index(
            row,
            stale_after_days=stale_after_days,
        )
    ]

    should_resync = (
        force_resync
        or not local_rows
        or len(stale_local_rows) > 0
    )

    remote_count = 0
    resynced = False
    remote_items: List[Dict[str, Any]] = []

    if should_resync:
        remote_items = await search_drug_index_items_by_code(
            raw_code,
            limit=100,
        )

        remote_count = len(remote_items)

        if remote_items:
            upsert_drug_index(
                db,
                remote_items,
            )

            resynced = True

            local_rows = _query_drug_indexes_by_code_candidates(
                db,
                candidates,
                limit=limit,
            )

            # Safety fallback:
            # If OpenFDA returned items and they were upserted, but the code-array
            # re-query still misses, return the newly created/updated index rows
            # by their normalized name/kind.
            if not local_rows:
                fallback_filters = []

                for item in remote_items:
                    name = str(item.get("name") or "").strip()
                    kind = str(item.get("type") or "brand").strip().lower()

                    if not name:
                        continue

                    fallback_filters.append(
                        (
                            DrugIndex.normalized_name == name.lower()
                        )
                        & (
                            DrugIndex.kind == kind
                        )
                    )

                if fallback_filters:
                    local_rows = (
                        db.query(DrugIndex)
                        .filter(or_(*fallback_filters))
                        .order_by(
                            DrugIndex.updated_at.desc().nullslast(),
                            DrugIndex.id.desc(),
                        )
                        .limit(limit)
                        .all()
                    )

    serialized_items = [
        _serialize_drug_index(
            row,
            stale_after_days=stale_after_days,
        )
        for row in local_rows
    ]

    return {
        "input": raw_code,
        "lookup_candidates": candidates,
        "matched": len(serialized_items) > 0,
        "count": len(serialized_items),
        "items": serialized_items,
        "resync": {
            "attempted": should_resync,
            "forced": force_resync,
            "resynced": resynced,
            "remote_count": remote_count,
            "stale_after_days": stale_after_days,
            "stale_local_count": len(stale_local_rows),
        },
    }