# openfda.pyfrom app.services.drug_details import upsert_drug_detail_and_link
from app.services.drug_details import upsert_drug_detail_and_link
from app.services.drug_index import upsert_drug_index
from typing import Optional, Dict, Any, Tuple
from app.services.openfda import get_drug_info_by_code
from app.util.normailize_codes import build_code_lookup_candidates
from app.util.normalize_drug_details import _build_payload, _pick_warnings_source
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.models import DrugIndex, DrugDetail



def _pick_display_name_from_payload(payload: Dict[str, Any], fallback: str) -> str:
    for key in ("brand_names", "generic_names"):
        values = payload.get(key) or []
        if isinstance(values, list) and values:
            first = str(values[0]).strip()
            if first:
                return first
    return fallback


def _pick_index_kind_from_payload(payload: Dict[str, Any]) -> str:
    brand_names = payload.get("brand_names") or []
    generic_names = payload.get("generic_names") or []

    if brand_names:
        return "brand"
    if generic_names:
        return "generic"
    return "substance"


async def get_or_create_drug_detail_by_code(
    db: Session,
    *,
    code: str,
) -> Tuple[Dict[str, Any], int]:
    raw_code = (code or "").strip()
    if not raw_code:
        raise ValueError("Missing code")

    # -------------------------
    # 1) Try local DB first
    # -------------------------

    candidates = build_code_lookup_candidates(raw_code)
    detail = (
    db.query(DrugDetail)
      .filter(
          or_(
              *[DrugDetail.upc_codes.any(c) for c in candidates],
              *[DrugDetail.package_ndc.any(c) for c in candidates],
              *[DrugDetail.rxcui.any(c) for c in candidates],
              *[DrugDetail.unii.any(c) for c in candidates],
          )
      )
      .order_by(DrugDetail.effective_time.desc().nullslast(), DrugDetail.id.desc())
      .first()
    )

    if detail:
        index_row: Optional[DrugIndex] = None
        if detail.drug_index_id:
            index_row = db.get(DrugIndex, detail.drug_index_id)
        return _build_payload(detail, index_row), detail.id

    # -------------------------
    # 2) Try OpenFDA
    # -------------------------
    base = await get_drug_info_by_code(raw_code)
    if not base:
        raise ValueError("No drug found for scanned code")

    base = dict(base)
    base["warnings_raw"] = _pick_warnings_source(base)

    display_name = _pick_display_name_from_payload(base, raw_code)
    kind = _pick_index_kind_from_payload(base)
    manufacturer = None
    manufacturer_names = base.get("manufacturer_names") or []
    if manufacturer_names:
        manufacturer = str(manufacturer_names[0]).strip()

    # -------------------------
    # 3) Ensure DrugIndex exists
    # -------------------------
    upsert_drug_index(
        db,
        [
            {
                "name": display_name,
                "type": kind,
                "manufacturer": manufacturer,
                "raw": base,
            }
        ],
    )

    norm_name = display_name.strip().lower()
    index_row = (
        db.query(DrugIndex)
        .filter(
            DrugIndex.normalized_name == norm_name,
            DrugIndex.kind == kind,
        )
        .first()
    )

    detail_id = upsert_drug_detail_and_link(
        db,
        {**base, "warnings_key": {}, "warnings_simple": []},
        display_name=display_name,
        drug_index_id=(index_row.id if index_row else None),
    )

    detail = db.get(DrugDetail, detail_id)
    if detail and detail.drug_index_id and not index_row:
        index_row = db.get(DrugIndex, detail.drug_index_id)

    payload = _build_payload(detail, index_row) if detail else {**base}
    return payload, detail_id