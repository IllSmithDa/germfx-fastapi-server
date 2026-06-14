from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.services.brave_barcode_search import search_barcode_with_brave


router = APIRouter(tags=["brave-barcode-search-test"])


@router.get("/barcode-search")
def test_brave_barcode_search(
    barcode: str = Query(..., min_length=1),
    count: int = Query(5, ge=1, le=10),
    exact: bool = Query(True),
    country: str = Query("us", min_length=2, max_length=2),
    search_lang: str = Query("en", min_length=2, max_length=5),
    prefer_domain_first: bool = Query(True),
    fallback_to_general: bool = Query(True),
):
    try:
        return search_barcode_with_brave(
            barcode,
            count=count,
            exact=exact,
            country=country,
            search_lang=search_lang,
            prefer_domain_first=prefer_domain_first,
            fallback_to_general=fallback_to_general,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Brave barcode search failed: {exc}",
        ) from exc