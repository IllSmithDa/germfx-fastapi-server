from app.services.upc_drug_details import get_or_create_drug_detail_by_code
from app.services.upc_drug_index import resolve_drug_index_by_code
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db import get_db
from app.schemas.medication import MedicationCreate, MedicationOut
from app.schemas.drug_detail import DrugDetailWarnings
from typing import List, Dict, Any, Optional
from app.services.drug_details import  initial_drug_detail, clean_warnings_for_detail
from app.services.openfda import get_drug_info
from app.services.drug_index import search_drugs_db_first
router = APIRouter()

# Search for medications using external OpenFDA API
@router.get("/drug-search")
async def adverse_search(drug: str):
    data = await get_drug_info(drug=drug)
    if not data:
        raise HTTPException(status_code=404, detail="No label found")
    return data



@router.get("/drug-list-search")
async def search_medications(
    q: str = Query(..., min_length=1, max_length=100),
    
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    page: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
):
    resolved_offset = offset

    if page is not None:
        resolved_offset = (page - 1) * limit

    return await search_drugs_db_first(
        db,
        q,
        limit=limit,
        offset=resolved_offset,
    )


# --- NEW: base detail endpoint (no llama, just raw OpenFDA + persistence) ---
@router.get("/drug-detail-base")
async def drug_info_base(
    db: Session = Depends(get_db),
    index_id: Optional[int] = Query(None, description="DrugIndex ID (preferred)"),
    detail_id: Optional[int] = Query(None, description="DrugDetail ID (fallback)"),
    drug: Optional[str] = Query(None, description="Fallback search term"),
):
    # print("drug_info_base called with index_id:", index_id, "detail_id:", detail_id, "drug:", drug)

    try:
        # ✅ Option A behavior:
        # - if detail_id is provided, initial_drug_detail should support it
        # - else use index_id
        payload, resolved_detail_id = await initial_drug_detail(
            db,
            drug_index_id=index_id,
            drug_detail_id=detail_id,   # <-- you’ll add this param in initial_drug_detail
            drug_query=drug,
        )
        return payload
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# --- NEW: get current warnings (may be empty) ---
@router.get("/drug-warnings", response_model=DrugDetailWarnings)
def get_drug_warnings(
    db: Session = Depends(get_db),
    detail_id: Optional[int] = Query(None),
    drug_index_id: Optional[int] = Query(None),
):
    from app.models import DrugDetail, DrugIndex
    detail = None
    if detail_id:
        detail = db.query(DrugDetail).get(detail_id)
    elif drug_index_id:
        idx = db.query(DrugIndex).get(drug_index_id)
        if idx:
            latest_id = getattr(idx, "latest_detail_id", None)
            detail = db.query(DrugDetail).get(latest_id) if latest_id else None
            if not detail:
                detail = (
                    db.query(DrugDetail)
                    .filter(DrugDetail.drug_index_id == idx.id)
                    .order_by(DrugDetail.effective_time.desc().nullslast(), DrugDetail.id.desc())
                    .first()
                )
    if not detail:
        raise HTTPException(status_code=404, detail="Drug detail not found")
    print('drug index id:', detail.drug_index_id)
    return {
        "warnings_key": detail.warnings_key or {},
        "warnings_simple": detail.warnings_simple or [],
        "drug_detail_id": detail.id,
        "side_effects": detail.side_effects or [],
    }

# --- NEW: trigger llama cleanup now (idempotent) ---
@router.get("/drug-warnings/clean")
async def post_clean_drug_warnings(
    db: Session = Depends(get_db),
    detail_id: Optional[int] = Query(None),
    drug_index_id: Optional[int] = Query(None),
):
    print("post_clean_drug_warnings called with detail_id:", detail_id, "drug_index_id:", drug_index_id)
    cleaned = await clean_warnings_for_detail(db, drug_detail_id=detail_id, drug_index_id=drug_index_id)
    return cleaned

# keep your v3 / search endpoints as-is...

@router.get("/drug-detail-by-code")
async def drug_info_by_code(
    code: str = Query(..., min_length=4, max_length=80, description="UPC, package NDC, RxCUI, or UNII"),
    db: Session = Depends(get_db),
):
    try:
        payload, resolved_detail_id = await get_or_create_drug_detail_by_code(
            db,
            code=code,
        )
        return payload
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@router.get("/drug-index-by-code")
async def drug_index_by_code(
    code: str = Query(
        ...,
        min_length=4,
        max_length=25,
        description="UPC, package NDC, or product NDC",
    ),
    limit: int = Query(25, ge=1, le=100),
    stale_after_days: int = Query(90, ge=1, le=365),
    force_resync: bool = Query(False),
    db: Session = Depends(get_db),
):
    """
    Scan-code lookup that resolves against DrugIndex, not DrugDetail.

    This is intended for barcode scanner results where the client wants
    possible DrugIndex matches, not a full saved DrugDetail payload.
    """
    try:
        return await resolve_drug_index_by_code(
            db,
            code=code,
            limit=limit,
            stale_after_days=stale_after_days,
            force_resync=force_resync,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )