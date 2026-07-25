# app/services/openfda_v3.py
from typing import Optional, Dict, Any, Tuple, List
from app.util.normalize_drug_details import _build_payload, _pick_warnings_source, _to_date
from sqlalchemy.orm import Session
from app.models import DrugIndex, DrugDetail
from sqlalchemy.dialects.postgresql import insert
from app.services.llama_text_cleaner import clean_with_llama
from app.services import openfda  # reuse v2 for base extraction
from sqlalchemy.sql import func

OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"

async def initial_drug_detail(
    db: Session,
    *,
    drug_index_id: Optional[int] = None,
    drug_detail_id: Optional[int] = None,
    drug_query: Optional[str] = None,
) -> Tuple[Dict[str, Any], int]:
    """
    Return a base DrugDetail (no LLM cleanup). If not present, fetch from OpenFDA,
    persist as DrugDetail (raw fields only), and link to DrugIndex.

    Supports lookup by either:
      - drug_detail_id (preferred if you already have it)
      - drug_index_id
      - drug_query (fallback)
    """
    index_row: Optional[DrugIndex] = None
    detail: Optional[DrugDetail] = None

    # ----------------------------
    # 1) Resolve by drug_detail_id
    # ----------------------------
    # print("initial_drug_detail called with drug_detail_id:", drug_detail_id, "drug_index_id:", drug_index_id, "drug_query:", drug_query)
    if drug_detail_id:
      detail = db.get(DrugDetail, drug_detail_id)
      if not detail:
          raise ValueError(f"DrugDetail not found: {drug_detail_id}")

      # derive index_row if possible
      if getattr(detail, "drug_index_id", None):
          index_row = db.get(DrugIndex, detail.drug_index_id)

      # If warnings already exist, return immediately
      if detail.warnings_raw and len(detail.warnings_raw) > 0:
          return _build_payload(detail, index_row), detail.id

      # Otherwise retry extraction like your existing logic
      query = detail.query_used or (index_row.name if index_row else None) or drug_query
      if query:
          base_retry = await openfda.get_drug_info(query)
          chosen = _pick_warnings_source(base_retry or {})
          if chosen:
              detail.warnings_raw = chosen
              if base_retry and base_retry.get("adverse_reactions") is not None:
                  detail.adverse_reactions = base_retry.get("adverse_reactions") or detail.adverse_reactions

              detail.upc_codes = (base_retry or {}).get("upc_codes") or detail.upc_codes
              detail.package_ndc = (base_retry or {}).get("package_ndc") or detail.package_ndc
              detail.unii = (base_retry or {}).get("unii") or detail.unii
              detail.rxcui = (base_retry or {}).get("rxcui") or detail.rxcui
              detail.openfda_meta = (base_retry or {}).get("openfda_meta") or detail.openfda_meta
              detail.query_used = query

              db.add(detail)
              db.commit()
              db.refresh(detail)
          return _build_payload(detail, index_row), detail.id

      # No query available, return what we have
      return _build_payload(detail, index_row), detail.id

    # ---------------------------
    # 2) Resolve by drug_index_id
    # ---------------------------
    if drug_index_id:
        index_row = db.get(DrugIndex, drug_index_id)
        # print("initial_drug_detail: found index_row:", index_row)
        if index_row:
            latest_id = getattr(index_row, "latest_detail_id", None)
            # print("initial_drug_detail: looking for detail by latest_detail_id:", latest_id)
            detail = db.get(DrugDetail, latest_id) if latest_id else None

            if not detail:
                detail = (
                    db.query(DrugDetail)
                    .filter(DrugDetail.drug_index_id == index_row.id)
                    .order_by(DrugDetail.effective_time.desc().nullslast(), DrugDetail.id.desc())
                    .first()
                )

            if detail:
                if detail.warnings_raw and len(detail.warnings_raw) > 0:
                    return _build_payload(detail, index_row), detail.id

                # warnings empty → retry extraction
                query = detail.query_used or index_row.name
                if query:
                    base_retry = await openfda.get_drug_info(query)
                    chosen = _pick_warnings_source(base_retry or {})
                    if chosen:
                        detail.warnings_raw = chosen
                        if base_retry and base_retry.get("adverse_reactions") is not None:
                            detail.adverse_reactions = base_retry.get("adverse_reactions") or detail.adverse_reactions
                        detail.openfda_meta = (base_retry or {}).get("openfda_meta") or detail.openfda_meta
                        detail.query_used = query

                        db.add(detail)
                        db.commit()
                        db.refresh(detail)
                    return _build_payload(detail, index_row), detail.id

                return _build_payload(detail, index_row), detail.id

    # ------------------------------------
    # 3) No existing detail → fetch OpenFDA
    # ------------------------------------
    query = drug_query or (index_row.name if index_row else None)
    if not query:
        print("initial_drug_detail: no search term available")
        raise ValueError("initial_drug_detail: missing drug_detail_id, drug_index_id, and drug_query")

    print('initial_drug_detail: fetching from OpenFDA with query:', query)
    base = await openfda.get_drug_info(query)
    
    
    if not base:
        print("initial_drug_detail: OpenFDA returned no results for query:", query)
        raise ValueError("OpenFDA returned no results")

    base = dict(base)
    base["warnings_raw"] = _pick_warnings_source(base)
    
    detail_id = upsert_drug_detail_and_link(
        db,
        {**base, "warnings_key": {}, "warnings_simple": []},
        display_name=query,
        drug_index_id=(index_row.id if index_row else None),
    )

    # if your upsert returns an id, reload for consistent payload building
    detail = db.get(DrugDetail, detail_id)
    if detail and detail.drug_index_id:
        index_row = index_row or db.get(DrugIndex, detail.drug_index_id)

    payload = _build_payload(detail, index_row) if detail else {**base}
    print("initial_drug_detail: returning payload for detail_id:", detail_id)
    return payload, detail_id


# Create and/or update DrugDetail and link to DrugIndex if provided
def upsert_drug_detail_and_link(
    db: Session,
    payload: Dict[str, Any],
    *,
    display_name: str,
    drug_index_id: Optional[int],
) -> int:
    norm = (display_name or "").strip().lower()
    eff = _to_date(payload.get("effective_time"))

    stmt = insert(DrugDetail).values(
        drug_index_id=drug_index_id,
        name=display_name,
        normalized_name=norm,
        brand_names=payload.get("brand_names"),
        generic_names=payload.get("generic_names"),
        manufacturer_names=payload.get("manufacturer_names"),
        route=payload.get("route"),
        product_type=payload.get("product_type"),
        purpose_or_indications=payload.get("purpose_or_indications"),
        dosage_and_administration=payload.get("dosage_and_administration"),
        adverse_reactions=payload.get("adverse_reactions"),
        drug_interactions=payload.get("drug_interactions"),
        boxed_warning=payload.get("boxed_warning"),
        warnings_key=payload.get("warnings_key"),
        warnings_raw=payload.get("warnings_raw"),
        warnings_simple=payload.get("warnings_simple"),
        upc_codes=payload.get("upc_codes") or payload.get("upc"),
        package_ndc=payload.get("package_ndc"),
        unii=payload.get("unii"),
        rxcui=payload.get("rxcui"),
        openfda_meta=payload.get("openfda_meta"),
        source=payload.get("source") or "openfda.label",
        query_used=payload.get("query_used"),
        symptoms_table=payload.get("symptoms_table"),
        effective_time=eff,
    ).on_conflict_do_update(
        constraint="uq_drugindex_eff_source",
        set_={
            "brand_names": insert(DrugDetail).excluded.brand_names,
            "generic_names": insert(DrugDetail).excluded.generic_names,
            "manufacturer_names": insert(DrugDetail).excluded.manufacturer_names,
            "route": insert(DrugDetail).excluded.route,
            "product_type": insert(DrugDetail).excluded.product_type,
            "purpose_or_indications": insert(DrugDetail).excluded.purpose_or_indications,
            "dosage_and_administration": insert(DrugDetail).excluded.dosage_and_administration,
            "adverse_reactions": insert(DrugDetail).excluded.adverse_reactions,
            "drug_interactions": insert(DrugDetail).excluded.drug_interactions,
            "boxed_warning": insert(DrugDetail).excluded.boxed_warning,
            "warnings_key": insert(DrugDetail).excluded.warnings_key,
            "warnings_raw": insert(DrugDetail).excluded.warnings_raw,
            "warnings_simple": insert(DrugDetail).excluded.warnings_simple,
            "upc_codes": insert(DrugDetail).excluded.upc_codes,
            "package_ndc": insert(DrugDetail).excluded.package_ndc,
            "unii": insert(DrugDetail).excluded.unii,
            "rxcui": insert(DrugDetail).excluded.rxcui,
            "openfda_meta": insert(DrugDetail).excluded.openfda_meta,
            "query_used": insert(DrugDetail).excluded.query_used,
            "drug_index_id": insert(DrugDetail).excluded.drug_index_id,
            "symptoms_table": insert(DrugDetail).excluded.symptoms_table,
            "updated_at": func.now(),
        },
    ).returning(DrugDetail.id)

    detail_id = db.execute(stmt).scalar_one()

    if drug_index_id:
        db.query(DrugIndex).filter(DrugIndex.id == drug_index_id).update(
            {"latest_detail_id": detail_id}
        )

    db.commit()
    return detail_id

def _first_string_value(value: Any) -> Optional[str]:
    if isinstance(value, list):
        for item in value:
            text = str(item or "").strip()
            if text:
                return text
        return None

    text = str(value or "").strip()
    return text or None


def _resolve_resync_query(
    *,
    detail: DrugDetail,
    index_row: Optional[DrugIndex],
    override_query: Optional[str] = None,
) -> str:
    candidates = [
        override_query,
        detail.query_used,
        detail.name,
        detail.normalized_name,
        index_row.name if index_row else None,
        index_row.normalized_name if index_row else None,
        _first_string_value(detail.brand_names),
        _first_string_value(detail.generic_names),
    ]

    for candidate in candidates:
        value = str(candidate or "").strip()
        if value:
            return value

    raise ValueError("Unable to determine a drug query for resync.")


async def resync_drug_detail_by_id(
    db: Session,
    *,
    drug_detail_id: int,
    drug_query: Optional[str] = None,
    make_latest: bool = True,
    reset_clean_fields: bool = True,
) -> Tuple[Dict[str, Any], int]:
    """
    Force-resync an existing DrugDetail row.

    This intentionally bypasses the normal initial_drug_detail early-return path.
    It always refetches OpenFDA data and updates the selected DrugDetail row.
    """

    detail = db.get(DrugDetail, drug_detail_id)

    if not detail:
        raise ValueError(f"DrugDetail not found: {drug_detail_id}")

    index_row: Optional[DrugIndex] = None

    if getattr(detail, "drug_index_id", None):
        index_row = db.get(DrugIndex, detail.drug_index_id)

    query = _resolve_resync_query(
        detail=detail,
        index_row=index_row,
        override_query=drug_query,
    )

    base = await openfda.get_drug_info(query)

    if not base:
        raise ValueError(f"OpenFDA returned no results for query: {query}")

    base = dict(base)
    base["warnings_raw"] = _pick_warnings_source(base)

    next_source = base.get("source") or detail.source or "openfda.label"
    next_effective_time = _to_date(base.get("effective_time"))

    if next_effective_time and detail.drug_index_id:
        duplicate = (
            db.query(DrugDetail)
            .filter(
                DrugDetail.id != detail.id,
                DrugDetail.drug_index_id == detail.drug_index_id,
                DrugDetail.effective_time == next_effective_time,
                DrugDetail.source == next_source,
            )
            .first()
        )

        if duplicate:
            raise ValueError(
                "Resync would conflict with another DrugDetail row that has "
                f"the same drug_index_id, effective_time, and source. "
                f"Conflicting detail_id: {duplicate.id}"
            )

    display_name = detail.name or query

    detail.name = display_name
    detail.normalized_name = (display_name or "").strip().lower()

    detail.brand_names = base.get("brand_names") or []
    detail.generic_names = base.get("generic_names") or []
    detail.manufacturer_names = base.get("manufacturer_names") or []
    detail.route = base.get("route") or []
    detail.product_type = base.get("product_type") or []

    detail.purpose_or_indications = base.get("purpose_or_indications") or []
    detail.dosage_and_administration = base.get("dosage_and_administration") or []
    detail.adverse_reactions = base.get("adverse_reactions") or []
    detail.drug_interactions = base.get("drug_interactions") or []
    detail.boxed_warning = base.get("boxed_warning") or []

    detail.warnings_raw = base.get("warnings_raw") or []
    detail.symptoms_table = base.get("symptoms_table") or []

    detail.upc_codes = base.get("upc_codes") or []
    detail.package_ndc = base.get("package_ndc") or []
    detail.unii = base.get("unii") or []
    detail.rxcui = base.get("rxcui") or []

    detail.openfda_meta = base.get("openfda_meta") or {}
    detail.source = next_source
    detail.query_used = query

    if next_effective_time:
        detail.effective_time = next_effective_time

    if reset_clean_fields:
        detail.warnings_key = {}
        detail.warnings_simple = []
        detail.side_effects = []
        detail.stop_using_warnings = []

    if make_latest and index_row:
        index_row.latest_detail_id = detail.id
        db.add(index_row)

    db.add(detail)
    db.commit()
    db.refresh(detail)

    if detail.drug_index_id and not index_row:
        index_row = db.get(DrugIndex, detail.drug_index_id)

    return _build_payload(detail, index_row), detail.id