from __future__ import annotations

from app.services.rx_norm_lookup import resolve_name_to_rxnorm_ndcs
from fastapi import APIRouter, HTTPException, Query, status

from app.services.rxnorm import (
    get_ndc_status_from_rxnorm,
    resolve_barcode_with_rxnorm,
    summarize_ndc_status,
    extract_ndc_status_payload,
)

router = APIRouter(tags=["rxnorm"])


@router.get("/ndc-status")
def test_rxnorm_ndc_status(
    ndc: str = Query(..., min_length=1),
    history: int = Query(1, ge=0, le=1),
    altpkg: int = Query(1, ge=0, le=1),
):
    """
    Direct test of RxNorm getNDCStatus for one exact NDC candidate.

    Example:
    GET /api/test/rxnorm/ndc-status?ndc=00071015723&altpkg=1&history=1
    """
    try:
        raw = get_ndc_status_from_rxnorm(
            ndc,
            history=history,
            altpkg=altpkg,
        )

        status_payload = extract_ndc_status_payload(raw)

        return {
            "input": ndc,
            "summary": summarize_ndc_status(status_payload),
            "raw": raw,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RxNorm lookup failed: {exc}",
        ) from exc


@router.get("/barcode-resolve")
def test_rxnorm_barcode_resolve(
    barcode: str = Query(..., min_length=1),
    history: int = Query(1, ge=0, le=1),
    altpkg: int = Query(1, ge=0, le=1),
):
    """
    Test route for scanned package barcodes.

    This generates multiple possible NDC candidates and calls RxNorm
    getNDCStatus for each candidate.

    Example:
    GET /api/test/rxnorm/barcode-resolve?barcode=00364666854
    """
    try:
        return resolve_barcode_with_rxnorm(
            barcode,
            history=history,
            altpkg=altpkg,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RxNorm barcode resolve failed: {exc}",
        ) from exc

@router.get("/name-to-ndcs")
def test_rxnorm_name_to_ndcs(
    name: str = Query(..., min_length=1),
    search: int = Query(2, ge=0, le=9),
    allsrc: int = Query(0, ge=0, le=1),
    include_approximate: bool = Query(True),
    include_historical: bool = Query(True),
    history: int = Query(2, ge=0, le=2),
    max_candidates: int = Query(12, ge=1, le=25),
    max_approximate_entries: int = Query(12, ge=1, le=100),
):
    """
    Reverse lookup test:
    drug/brand/generic name -> RxCUIs -> active/historical NDCs.

    Examples:
    GET /api/rxnorm/name-to-ndcs?name=Lipitor
    GET /api/rxnorm/name-to-ndcs?name=atorvastatin%2020%20mg%20tablet
    GET /api/rxnorm/name-to-ndcs?name=Tylenol&include_historical=true
    """
    try:
        return resolve_name_to_rxnorm_ndcs(
            name,
            search=search,
            allsrc=allsrc,
            include_approximate=include_approximate,
            include_historical=include_historical,
            history=history,
            max_candidates=max_candidates,
            max_approximate_entries=max_approximate_entries,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"RxNorm name-to-NDC lookup failed: {exc}",
        ) from exc