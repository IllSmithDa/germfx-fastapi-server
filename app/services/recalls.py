# app/services/recalls.py

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import os
import requests

from app.models import RecallItem, ContentReaction
from app.util.state_names import STATE_NAMES
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, and_

OPENFDA_BASE = "https://api.fda.gov"
DEFAULT_TIMEOUT = 20
MAX_TOTAL_RECALLS = 520
MAX_NEW_PER_SOURCE = 100


def _safe_get(d: Dict[str, Any], key: str) -> Optional[str]:
    value = d.get(key)
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _today_fda_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _fetch_openfda_json(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    api_key = os.getenv("OPENFDA_API_KEY")
    if api_key:
        params = {**params, "api_key": api_key}

    url = f"{OPENFDA_BASE}{endpoint}"
    response = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)

    '''
    print(
        f"Received response with status {response.status_code} and content length {len(response.content)}"
    )
    print("Final URL:", response.url)
    '''
    if response.status_code == 404:
        print(f"No OpenFDA matches found for {endpoint} with params {params}")
        return {"results": [], "meta": {}}

    if not response.ok:
        print("OpenFDA error body:", response.text)
        response.raise_for_status()

    return response.json()


def _fetch_food_recalls(limit: int = MAX_NEW_PER_SOURCE) -> List[Dict[str, Any]]:
    params = {
        "limit": limit,
        "sort": "report_date:desc",
    }
    data = _fetch_openfda_json("/food/enforcement.json", params)
    return data.get("results", [])


def _fetch_drug_recalls(limit: int = MAX_NEW_PER_SOURCE) -> List[Dict[str, Any]]:
    params = {
        "limit": limit,
        "sort": "report_date:desc",
    }
    data = _fetch_openfda_json("/drug/enforcement.json", params)
    return data.get("results", [])


def _normalize_food_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "food",
        "product_type": "food",
        "classification": _safe_get(item, "classification"),
        "status": _safe_get(item, "status"),
        "recall_date": _safe_get(item, "recall_initiation_date"),
        "report_date": _safe_get(item, "report_date"),
        "title": _safe_get(item, "product_description") or "Food recall",
        "reason": _safe_get(item, "reason_for_recall"),
        "company": _safe_get(item, "recalling_firm"),
        "distribution": _safe_get(item, "distribution_pattern"),
        "recall_number": _safe_get(item, "recall_number"),
        "event_id": _safe_get(item, "event_id"),
        "raw_json": item,
    }


def _normalize_drug_item(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": "drug",
        "product_type": "medication",
        "classification": _safe_get(item, "classification"),
        "status": _safe_get(item, "status"),
        "recall_date": _safe_get(item, "recall_initiation_date"),
        "report_date": _safe_get(item, "report_date"),
        "title": _safe_get(item, "product_description") or "Medication recall",
        "reason": _safe_get(item, "reason_for_recall"),
        "company": _safe_get(item, "recalling_firm"),
        "distribution": _safe_get(item, "distribution_pattern"),
        "recall_number": _safe_get(item, "recall_number"),
        "event_id": _safe_get(item, "event_id"),
        "raw_json": item,
    }


def _recall_exists(db: Session, source: str, recall_number: Optional[str]) -> bool:
    if not recall_number:
        return False

    existing = (
        db.query(RecallItem)
        .filter(
            RecallItem.source == source,
            RecallItem.recall_number == recall_number,
        )
        .first()
    )
    return existing is not None


def _payload_exists(db: Session, payload: Dict[str, Any]) -> bool:
    """
    Check whether one normalized recall payload is already stored.

    recall_number remains the preferred identity. The title/company/date
    fallback mirrors _insert_recall_if_new() for the uncommon case where the
    source does not provide a recall number.
    """
    source = payload["source"]
    recall_number = payload.get("recall_number")

    if recall_number:
        return _recall_exists(db, source, recall_number)

    existing = (
        db.query(RecallItem)
        .filter(
            RecallItem.source == source,
            RecallItem.title == payload["title"],
            RecallItem.company == payload.get("company"),
            RecallItem.recall_date == payload.get("recall_date"),
        )
        .first()
    )
    return existing is not None


def _insert_recall_if_new(db: Session, payload: Dict[str, Any]) -> bool:
    if _payload_exists(db, payload):
        return False

    db.add(RecallItem(**payload))
    return True


def trim_old_recalls(db: Session, max_total: int = MAX_TOTAL_RECALLS) -> int:
    total = db.query(RecallItem).count()
    if total <= max_total:
        return 0

    excess = total - max_total

    oldest = (
        db.query(RecallItem)
        .order_by(
            RecallItem.report_date.asc().nullsfirst(),
            RecallItem.recall_date.asc().nullsfirst(),
            RecallItem.created_at.asc(),
            RecallItem.id.asc(),
        )
        .limit(excess)
        .all()
    )

    oldest_ids = [row.id for row in oldest]

    if oldest_ids:
        (
            db.query(ContentReaction)
            .filter(
                ContentReaction.content_type == "recall",
                ContentReaction.source_item_id.in_(oldest_ids),
            )
            .delete(synchronize_session=False)
        )

    for row in oldest:
        db.delete(row)

    db.commit()
    return excess


def get_latest_stored_report_date(db: Session) -> Optional[str]:
    latest = (
        db.query(RecallItem)
        .filter(RecallItem.report_date.isnot(None))
        .order_by(RecallItem.report_date.desc(), RecallItem.id.desc())
        .first()
    )
    if not latest:
        return None
    return latest.report_date


def _get_latest_report_date_from_payloads(payloads: List[Dict[str, Any]]) -> Optional[str]:
    dates = [p.get("report_date") for p in payloads if p.get("report_date")]
    if not dates:
        return None
    return max(dates)


def should_sync_recalls(db: Session, max_new_per_source: int = MAX_NEW_PER_SOURCE) -> bool:
    """
    Return True when the latest openFDA windows contain at least one recall
    that is not already stored.

    Do not use report_date as a hard cursor. Multiple recalls can share the
    same report_date, and an endpoint can expose additional records without
    advancing its newest date.
    """
    food_raw = _fetch_food_recalls(limit=max_new_per_source)
    drug_raw = _fetch_drug_recalls(limit=max_new_per_source)

    normalized_food = [_normalize_food_item(item) for item in food_raw]
    normalized_drug = [_normalize_drug_item(item) for item in drug_raw]

    return any(
        not _payload_exists(db, payload)
        for payload in [*normalized_food, *normalized_drug]
    )


def sync_recalls(
    db: Session,
    *,
    max_new_per_source: int = MAX_NEW_PER_SOURCE,
    max_total: int = MAX_TOTAL_RECALLS,
) -> Dict[str, Any]:
    sync_date = _today_fda_date()

    print(
        f"Syncing recalls for day {sync_date} "
        f"(checking up to {max_new_per_source} per source, max total {max_total})"
    )

    food_raw = _fetch_food_recalls(limit=max_new_per_source)
    drug_raw = _fetch_drug_recalls(limit=max_new_per_source)

    normalized_food = [_normalize_food_item(item) for item in food_raw]
    normalized_drug = [_normalize_drug_item(item) for item in drug_raw]

    latest_stored_report_date = get_latest_stored_report_date(db)
    latest_source_report_date = _get_latest_report_date_from_payloads(
        [*normalized_food, *normalized_drug]
    )

    inserted = 0

    # Always inspect the fetched window. report_date is useful diagnostic
    # metadata, but it is not a safe unique synchronization cursor.
    for payload in [*normalized_food, *normalized_drug]:
        if _insert_recall_if_new(db, payload):
            inserted += 1

    db.commit()

    trimmed = trim_old_recalls(db, max_total=max_total)
    total_after = db.query(RecallItem).count()

    return {
        "sync_date": sync_date,
        "food_fetched": len(food_raw),
        "drug_fetched": len(drug_raw),
        "inserted": inserted,
        "trimmed": trimmed,
        "total_after": total_after,
        "latest_stored_report_date": latest_stored_report_date,
        "latest_source_report_date": latest_source_report_date,
        "did_sync": inserted > 0,
        "checked_sources": True,
    }


def get_recalls_from_db(
    db: Session,
    *,
    limit: int = 20,
    skip: int = 0,
    source: Optional[str] = None,
    query: Optional[str] = None,
    state: Optional[str] = None,
    sort: str = "latest",
) -> Dict[str, Any]:
    sort = sort if sort in {"latest", "popular", "oldest"} else "latest"

    reaction_count = func.count(ContentReaction.id).label("reaction_count")

    db_query = (
        db.query(RecallItem, reaction_count)
        .outerjoin(
            ContentReaction,
            and_(
                ContentReaction.content_type == "recall",
                ContentReaction.source_item_id == RecallItem.id,
            ),
        )
        .group_by(RecallItem.id)
    )

    count_query = db.query(func.count(RecallItem.id))

    if source:
        db_query = db_query.filter(RecallItem.source == source)
        count_query = count_query.filter(RecallItem.source == source)

    if query and query.strip():
        like_query = f"%{query.strip()}%"
        search_filter = or_(
            RecallItem.title.ilike(like_query),
            RecallItem.reason.ilike(like_query),
            RecallItem.company.ilike(like_query),
            RecallItem.distribution.ilike(like_query),
        )

        db_query = db_query.filter(search_filter)
        count_query = count_query.filter(search_filter)

    if state and state.lower() != "all":
        state_code = state.upper()
        state_name = STATE_NAMES.get(state_code)

        if state_name:
            state_filter = or_(
                RecallItem.distribution.ilike(state_code),
                RecallItem.distribution.ilike(f"{state_code},%"),
                RecallItem.distribution.ilike(f"%, {state_code},%"),
                RecallItem.distribution.ilike(f"%, {state_code}"),
                RecallItem.distribution.ilike(f"%{state_name}%"),
                RecallItem.distribution.ilike("%nationwide%"),
                RecallItem.distribution.ilike("%United States%"),
            )

            db_query = db_query.filter(state_filter)
            count_query = count_query.filter(state_filter)

    total = count_query.scalar() or 0

    if sort == "popular":
        db_query = db_query.order_by(
            reaction_count.desc(),
            RecallItem.report_date.desc().nullslast(),
            RecallItem.recall_date.desc().nullslast(),
            RecallItem.id.desc(),
        )
    elif sort == "oldest":
        db_query = db_query.order_by(
            RecallItem.report_date.asc().nullsfirst(),
            RecallItem.recall_date.asc().nullsfirst(),
            RecallItem.id.asc(),
        )
    else:
        db_query = db_query.order_by(
            RecallItem.report_date.desc().nullslast(),
            RecallItem.recall_date.desc().nullslast(),
            RecallItem.id.desc(),
        )

    rows = db_query.offset(skip).limit(limit).all()

    items = []
    for recall, count in rows:
        setattr(recall, "reaction_count", int(count or 0))
        items.append(recall)

    return {
        "items": items,
        "count": len(items),
        "total": total,
        "limit": limit,
        "skip": skip,
        "sort": sort,
    }