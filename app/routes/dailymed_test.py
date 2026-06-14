from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.services.dailymed import (
    dailymed_get_spl_ndcs,
    dailymed_get_spl_packaging,
    dailymed_get_spls_by_ndc,
    resolve_barcode_with_dailymed,
    summarize_spls_response,
)

router = APIRouter(tags=["dailymed-test"])


@router.get("/ndc-spls")
def test_dailymed_ndc_spls(
    ndc: str = Query(..., min_length=1),
    pagesize: int = Query(5, ge=1, le=100),
):
    """
    Direct DailyMed test for one NDC candidate.

    Example:
    GET /api/test/dailymed/ndc-spls?ndc=0378-6015-10
    """
    try:
        raw = dailymed_get_spls_by_ndc(
            ndc,
            pagesize=pagesize,
        )

        return {
            "input": ndc,
            "summary": summarize_spls_response(
                ndc,
                raw,
            ),
            "raw": raw,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DailyMed NDC lookup failed: {exc}",
        ) from exc


@router.get("/barcode-resolve")
def test_dailymed_barcode_resolve(
    barcode: str = Query(..., min_length=1),
    pagesize: int = Query(5, ge=1, le=100),
    enrich_first_match: bool = Query(False),
):
    """
    Test route for scanned package barcodes.

    This generates possible NDC candidates and searches DailyMed
    /spls.json?ndc=<candidate> for each.

    Example:
    GET /api/test/dailymed/barcode-resolve?barcode=00378601510
    """
    try:
      print('test')
      return resolve_barcode_with_dailymed(
          barcode,
          pagesize=pagesize,
          enrich_first_match=enrich_first_match,
      )

    except Exception as exc:
      raise HTTPException(
          status_code=status.HTTP_502_BAD_GATEWAY,
          detail=f"DailyMed barcode resolve failed: {exc}",
      ) from exc


@router.get("/spl/{setid}/ndcs")
def test_dailymed_spl_ndcs(
    setid: str,
):
    """
    Fetch all NDCs for a DailyMed SPL set ID.

    Example:
    GET /api/test/dailymed/spl/{setid}/ndcs
    """
    try:
        return dailymed_get_spl_ndcs(setid)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DailyMed SPL NDC lookup failed: {exc}",
        ) from exc


@router.get("/spl/{setid}/packaging")
def test_dailymed_spl_packaging(
    setid: str,
):
    """
    Fetch package descriptions for a DailyMed SPL set ID.

    Example:
    GET /api/test/dailymed/spl/{setid}/packaging
    """
    try:
        return dailymed_get_spl_packaging(setid)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"DailyMed SPL packaging lookup failed: {exc}",
        ) from exc