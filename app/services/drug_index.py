from typing import List, Dict, Any
from app.util.search_suggestions import _best_suggestion
from sqlalchemy import select, func, or_, cast, Text, literal, text
from app.util.search_rank_query import build_search_rank
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sqlalchemy.exc import ProgrammingError
from app.models import DrugIndex
from app.services.openfda import search_drug_names

MAX_DRUG_INDEX_NAME_LEN = 300
MAX_MANUFACTURER_LEN = 300


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _looks_like_ingredient_soup(name: str) -> bool:
    # Optional noise filter for giant comma-separated ingredient lists
    return name.count(",") >= 5

def _clean_code(value: Any) -> str | None:
    code = str(value or "").strip()

    if not code:
        return None

    return code

def _digits_only(value: Any) -> str | None:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())

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


def _clean_code_list(values: Any) -> list[str]:
    if not values:
        return []

    if not isinstance(values, list):
        values = [values]

    out: list[str] = []
    seen: set[str] = set()

    for value in values:
        for code in _code_variants(value):
            if code in seen:
                continue

            seen.add(code)
            out.append(code)

    return out

def _merge_unique_codes(
    existing: list[str] | None,
    incoming: list[str] | None,
) -> list[str] | None:
    merged: list[str] = []
    seen: set[str] = set()

    for value in (existing or []) + (incoming or []):
        for code in _code_variants(value):
            if code in seen:
                continue

            seen.add(code)
            merged.append(code)

    return merged or None

def upsert_drug_index(db: Session, items: List[Dict[str, Any]]) -> None:
    """
    items: [{name, type, manufacturer, score?, upc_codes?, ndc_codes?}]
    """
    for it in items:
        name = (it.get("name") or "").strip()

        if not name:
            continue

        norm = _norm(name)
        manufacturer = (it.get("manufacturer") or "").strip() or None

        # Skip entries that are too long or clearly poor search candidates.
        if len(name) > MAX_DRUG_INDEX_NAME_LEN or len(norm) > MAX_DRUG_INDEX_NAME_LEN:
            continue

        if manufacturer and len(manufacturer) > MAX_MANUFACTURER_LEN:
            manufacturer = manufacturer[:MAX_MANUFACTURER_LEN]

        if _looks_like_ingredient_soup(name):
            continue

        kind = (it.get("type") or "brand").lower()

        incoming_upc_codes = _clean_code_list(
            it.get("upc_codes") or it.get("upc") or []
        )

        incoming_ndc_codes = _clean_code_list(
            it.get("ndc_codes") or it.get("ndc") or []
        )

        existing = db.execute(
            select(DrugIndex).where(
                DrugIndex.normalized_name == norm,
                DrugIndex.kind == kind,
            )
        ).scalar_one_or_none()

        if existing:
            if manufacturer and not existing.manufacturer:
                existing.manufacturer = manufacturer

            existing.upc_codes = _merge_unique_codes(
                existing.upc_codes,
                incoming_upc_codes,
            )

            existing.ndc_codes = _merge_unique_codes(
                existing.ndc_codes,
                incoming_ndc_codes,
            )

            existing.updated_at = func.now()
            continue

        db.add(
            DrugIndex(
                name=name,
                normalized_name=norm,
                kind=kind,
                manufacturer=manufacturer,
                source="openfda",
                upc_codes=incoming_upc_codes or None,
                ndc_codes=incoming_ndc_codes or None,
            )
        )

    db.commit()


def _rows_to_results(rows) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        di, score = row[0], (row[1] if len(row) > 1 else None)
        out.append(
            {
                "id": di.id,
                "name": di.name,
                "kind": di.kind,
                "manufacturer": di.manufacturer,
                "score": float(score) if score is not None else None,
            }
        )
    return out


def _merge_unique_results(
    primary: List[Dict[str, Any]],
    secondary: List[Dict[str, Any]],
    limit: int,
) -> List[Dict[str, Any]]:
    seen: set[int] = set()
    merged: List[Dict[str, Any]] = []

    for item in primary + secondary:
        item_id = item["id"]
        if item_id in seen:
            continue
        seen.add(item_id)
        merged.append(item)
        if len(merged) >= limit:
            break

    return merged


def _fallback_stmt(query: str, normalized_query: str, limit: int):
    rank = build_search_rank(DrugIndex, query, normalized_query)

    return (
        select(
            DrugIndex,
            rank.label("score"),
        )
        .where(
            or_(
                DrugIndex.name.ilike(f"%{query}%"),
                DrugIndex.normalized_name.ilike(f"%{normalized_query}%"),
            )
        )
        .order_by(
            rank.desc(),
            func.length(DrugIndex.name).asc(),
            DrugIndex.name.asc(),
        )
        .limit(limit)
    )


def _trgm_stmt(query: str, normalized_query: str, limit: int):
    name_sim = func.similarity(
        cast(DrugIndex.name, Text),
        literal(query, type_=Text()),
    )
    norm_sim = func.similarity(
        cast(DrugIndex.normalized_name, Text),
        literal(normalized_query, type_=Text()),
    )
    best_sim = func.greatest(name_sim, norm_sim)

    rank = build_search_rank(DrugIndex, query, normalized_query)
    total_score = rank + (best_sim * 20)

    return (
        select(
            DrugIndex,
            total_score.label("score"),
        )
        .where(
            or_(
                DrugIndex.name.ilike(f"%{query}%"),
                DrugIndex.normalized_name.ilike(f"%{normalized_query}%"),
                best_sim > 0.25,  # Adjust this threshold as needed for relevance default is 0.25
            )
        )
        .order_by(
            total_score.desc(),
            func.length(DrugIndex.name).asc(),
            DrugIndex.name.asc(),
        )
        .limit(limit)
    )


def search_local(db: Session, q: str, limit: int = 25) -> Dict[str, Any]:
    query = q.strip()
    if not query:
        return {
            "items": [],
            "used_fuzzy": False,
            "did_you_mean": None,
        }

    normalized_query = _norm(query)

    strict_rows = db.execute(
        _fallback_stmt(query, normalized_query, limit)
    ).all()
    strict_results = _rows_to_results(strict_rows)

    if len(strict_results) >= min(5, limit):
        return {
            "items": strict_results,
            "used_fuzzy": False,
            "did_you_mean": None,
        }

    try:
        has_trgm = bool(
            db.execute(
                text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
            ).scalar()
        )
    except Exception as e:
        print("pg_trgm check failed:", e)
        has_trgm = False

    if not has_trgm:
        return {
            "items": strict_results,
            "used_fuzzy": False,
            "did_you_mean": None,
        }

    try:
        fuzzy_rows = db.execute(
            _trgm_stmt(query, normalized_query, limit)
        ).all()
        fuzzy_results = _rows_to_results(fuzzy_rows)

        merged = _merge_unique_results(strict_results, fuzzy_results, limit)

        return {
            "items": merged,
            "used_fuzzy": len(fuzzy_results) > 0 and len(strict_results) < min(5, limit),
            "did_you_mean": _best_suggestion(strict_results, fuzzy_results, query),
        }
    except ProgrammingError:
        return {
            "items": strict_results,
            "used_fuzzy": False,
            "did_you_mean": None,
        }


async def search_drugs_db_first(
    db: Session,
    q: str,
    limit: int = 25,
) -> Dict[str, Any]:
    local = search_local(db, q, limit)
    if len(local["items"]) >= min(5, limit):
        return local

    remote = await search_drug_names(q, limit=100)
    if remote:
        upsert_drug_index(db, remote)

    return search_local(db, q, limit)