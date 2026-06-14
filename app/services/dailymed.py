from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


DAILYMED_BASE_URL = os.getenv(
    "DAILYMED_BASE_URL",
    "https://dailymed.nlm.nih.gov/dailymed/services/v2",
).rstrip("/")


@dataclass(frozen=True)
class DailyMedCandidate:
    value: str
    reason: str


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def unique_candidates(
    candidates: list[DailyMedCandidate],
) -> list[DailyMedCandidate]:
    seen: set[str] = set()
    result: list[DailyMedCandidate] = []

    for candidate in candidates:
        value = candidate.value.strip()

        if not value or value in seen:
            continue

        seen.add(value)
        result.append(
            DailyMedCandidate(
                value=value,
                reason=candidate.reason,
            )
        )

    return result


def eleven_digit_ndc_to_possible_ten_digit_formats(
    ndc11: str,
) -> list[DailyMedCandidate]:
    """
    Converts an 11-digit CMS-style NDC into possible 10-digit
    FDA-style dashed formats.

    11-digit form is usually 5-4-2.
    Original 10-digit NDC may have been:
    - 4-4-2, with labeler padded to 5 digits
    - 5-3-2, with product padded to 4 digits
    - 5-4-1, with package padded to 2 digits
    """
    if len(ndc11) != 11 or not ndc11.isdigit():
        return []

    labeler_5 = ndc11[:5]
    product_4 = ndc11[5:9]
    package_2 = ndc11[9:11]

    candidates: list[DailyMedCandidate] = [
        DailyMedCandidate(
            value=f"{labeler_5}-{product_4}-{package_2}",
            reason="11_digit_as_5_4_2",
        )
    ]

    # Possible original 4-4-2: padded labeler segment.
    if labeler_5.startswith("0"):
        candidates.append(
            DailyMedCandidate(
                value=f"{labeler_5[1:]}-{product_4}-{package_2}",
                reason="11_digit_to_possible_4_4_2",
            )
        )

    # Possible original 5-3-2: padded product segment.
    if product_4.startswith("0"):
        candidates.append(
            DailyMedCandidate(
                value=f"{labeler_5}-{product_4[1:]}-{package_2}",
                reason="11_digit_to_possible_5_3_2",
            )
        )

    # Possible original 5-4-1: padded package segment.
    if package_2.startswith("0"):
        candidates.append(
            DailyMedCandidate(
                value=f"{labeler_5}-{product_4}-{package_2[1:]}",
                reason="11_digit_to_possible_5_4_1",
            )
        )

    return candidates


def ten_digit_ndc_to_dashed_formats(
    ndc10: str,
) -> list[DailyMedCandidate]:
    if len(ndc10) != 10 or not ndc10.isdigit():
        return []

    return [
        DailyMedCandidate(
            value=f"{ndc10[:4]}-{ndc10[4:8]}-{ndc10[8:]}",
            reason="10_digit_to_4_4_2",
        ),
        DailyMedCandidate(
            value=f"{ndc10[:5]}-{ndc10[5:8]}-{ndc10[8:]}",
            reason="10_digit_to_5_3_2",
        ),
        DailyMedCandidate(
            value=f"{ndc10[:5]}-{ndc10[5:9]}-{ndc10[9:]}",
            reason="10_digit_to_5_4_1",
        ),
    ]


def generate_dailymed_ndc_candidates(
    raw_code: str,
) -> list[DailyMedCandidate]:
    """
    Generate possible NDC candidates from a package barcode.

    This is intentionally generous because package barcodes may be:
    - raw NDC
    - NDC with dashes
    - UPC-A-like
    - EAN-13-like
    - GTIN-14-like
    - NDC plus check digit / leading packaging digit
    """
    raw = (raw_code or "").strip()
    digits = only_digits(raw)

    candidates: list[DailyMedCandidate] = []

    if raw:
        candidates.append(
            DailyMedCandidate(
                value=raw,
                reason="raw_input",
            )
        )

    if digits:
        candidates.append(
            DailyMedCandidate(
                value=digits,
                reason="digits_only",
            )
        )

    if len(digits) == 10:
        candidates.extend(
            ten_digit_ndc_to_dashed_formats(digits)
        )

    if len(digits) == 11:
        candidates.extend(
            eleven_digit_ndc_to_possible_ten_digit_formats(digits)
        )

    if len(digits) == 12:
        # UPC-A possibilities.
        no_check = digits[:-1]
        no_first = digits[1:]
        middle_10 = digits[1:-1]

        candidates.append(
            DailyMedCandidate(
                value=no_check,
                reason="upca_remove_check_digit_11_digits",
            )
        )
        candidates.extend(
            eleven_digit_ndc_to_possible_ten_digit_formats(no_check)
        )

        candidates.append(
            DailyMedCandidate(
                value=no_first,
                reason="upca_remove_first_digit_11_digits",
            )
        )
        candidates.extend(
            eleven_digit_ndc_to_possible_ten_digit_formats(no_first)
        )

        candidates.append(
            DailyMedCandidate(
                value=middle_10,
                reason="upca_remove_first_and_check_digit_10_digits",
            )
        )
        candidates.extend(
            ten_digit_ndc_to_dashed_formats(middle_10)
        )

    if len(digits) == 13:
        # EAN-13 possibilities.
        no_check = digits[:-1]
        no_first = digits[1:]
        middle_11 = digits[1:-1]
        middle_10 = digits[2:-1]

        candidates.append(
            DailyMedCandidate(
                value=no_check,
                reason="ean13_remove_check_digit_12_digits",
            )
        )

        candidates.append(
            DailyMedCandidate(
                value=no_first,
                reason="ean13_remove_first_digit_12_digits",
            )
        )

        candidates.append(
            DailyMedCandidate(
                value=middle_11,
                reason="ean13_remove_first_and_check_digit_11_digits",
            )
        )
        candidates.extend(
            eleven_digit_ndc_to_possible_ten_digit_formats(middle_11)
        )

        candidates.append(
            DailyMedCandidate(
                value=middle_10,
                reason="ean13_remove_first_two_and_check_digit_10_digits",
            )
        )
        candidates.extend(
            ten_digit_ndc_to_dashed_formats(middle_10)
        )

    if len(digits) == 14:
        # GTIN-14 possibilities.
        no_check = digits[:-1]
        no_first = digits[1:]
        middle_12 = digits[1:-1]
        middle_11 = digits[2:-1]

        candidates.append(
            DailyMedCandidate(
                value=no_check,
                reason="gtin14_remove_check_digit_13_digits",
            )
        )

        candidates.append(
            DailyMedCandidate(
                value=no_first,
                reason="gtin14_remove_first_digit_13_digits",
            )
        )

        candidates.append(
            DailyMedCandidate(
                value=middle_12,
                reason="gtin14_remove_first_and_check_digit_12_digits",
            )
        )

        candidates.append(
            DailyMedCandidate(
                value=middle_11,
                reason="gtin14_remove_first_two_and_check_digit_11_digits",
            )
        )
        candidates.extend(
            eleven_digit_ndc_to_possible_ten_digit_formats(middle_11)
        )

    return unique_candidates(candidates)


def dailymed_get_spls_by_ndc(
    ndc: str,
    *,
    pagesize: int = 5,
    page: int = 1,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """
    Calls DailyMed:
    GET /spls.json?ndc=<ndc>&pagesize=<pagesize>&page=<page>
    """
    url = f"{DAILYMED_BASE_URL}/spls.json"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            url,
            params={
                "ndc": ndc,
                "pagesize": str(pagesize),
                "page": str(page),
            },
            headers={
                "Accept": "application/json",
            },
        )

    response.raise_for_status()
    return response.json()


def dailymed_get_spl_ndcs(
    setid: str,
    *,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """
    Calls DailyMed:
    GET /spls/{setid}/ndcs.json
    """
    url = f"{DAILYMED_BASE_URL}/spls/{setid}/ndcs.json"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            url,
            headers={
                "Accept": "application/json",
            },
        )

    response.raise_for_status()
    return response.json()


def dailymed_get_spl_packaging(
    setid: str,
    *,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    """
    Calls DailyMed:
    GET /spls/{setid}/packaging.json
    """
    url = f"{DAILYMED_BASE_URL}/spls/{setid}/packaging.json"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            url,
            headers={
                "Accept": "application/json",
            },
        )

    response.raise_for_status()
    return response.json()


def extract_spl_items(
    data: dict[str, Any],
) -> list[dict[str, Any]]:
    items = data.get("data")

    if isinstance(items, list):
        return [
            item
            for item in items
            if isinstance(item, dict)
        ]

    # Defensive fallback in case the response shape changes.
    spl = data.get("spl")

    if isinstance(spl, list):
        return [
            item
            for item in spl
            if isinstance(item, dict)
        ]

    if isinstance(spl, dict):
        return [spl]

    return []


def extract_metadata(
    data: dict[str, Any],
) -> dict[str, Any]:
    metadata = data.get("metadata")

    if isinstance(metadata, dict):
        return metadata

    return {}


def summarize_spl_item(
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "setid": item.get("setid"),
        "spl_version": item.get("spl_version"),
        "title": item.get("title"),
        "published_date": item.get("published_date"),
    }


def summarize_spls_response(
    ndc: str,
    data: dict[str, Any],
) -> dict[str, Any]:
    items = extract_spl_items(data)
    metadata = extract_metadata(data)

    return {
        "ndc": ndc,
        "found": len(items) > 0,
        "total_elements": metadata.get("total_elements"),
        "current_page": metadata.get("current_page"),
        "items": [
            summarize_spl_item(item)
            for item in items
        ],
    }


def resolve_barcode_with_dailymed(
    barcode: str,
    *,
    pagesize: int = 5,
    enrich_first_match: bool = False,
) -> dict[str, Any]:
    candidates = generate_dailymed_ndc_candidates(barcode)

    attempts: list[dict[str, Any]] = []
    best_match: dict[str, Any] | None = None

    for candidate in candidates:
        try:
            raw = dailymed_get_spls_by_ndc(
                candidate.value,
                pagesize=pagesize,
            )

            summary = summarize_spls_response(
                candidate.value,
                raw,
            )

            attempt: dict[str, Any] = {
                "candidate": candidate.value,
                "reason": candidate.reason,
                "ok": True,
                "summary": summary,
                "raw": raw,
            }

            if best_match is None and summary["found"]:
                best_match = attempt

            attempts.append(attempt)

        except httpx.HTTPStatusError as exc:
            attempts.append(
                {
                    "candidate": candidate.value,
                    "reason": candidate.reason,
                    "ok": False,
                    "error": f"DailyMed returned HTTP {exc.response.status_code}",
                }
            )

        except httpx.RequestError as exc:
            attempts.append(
                {
                    "candidate": candidate.value,
                    "reason": candidate.reason,
                    "ok": False,
                    "error": f"DailyMed request failed: {exc}",
                }
            )

    enrichment: dict[str, Any] | None = None

    if enrich_first_match and best_match:
        first_item = (
            best_match
            .get("summary", {})
            .get("items", [])
        )

        if first_item:
            setid = first_item[0].get("setid")

            if setid:
                enrichment = {
                    "setid": setid,
                    "ndcs": None,
                    "packaging": None,
                    "errors": [],
                }

                try:
                    enrichment["ndcs"] = dailymed_get_spl_ndcs(setid)
                except Exception as exc:
                    enrichment["errors"].append(
                        f"Failed to fetch SPL NDCs: {exc}"
                    )

                try:
                    enrichment["packaging"] = dailymed_get_spl_packaging(setid)
                except Exception as exc:
                    enrichment["errors"].append(
                        f"Failed to fetch SPL packaging: {exc}"
                    )

    return {
        "input": barcode,
        "normalized_digits": only_digits(barcode),
        "matched": best_match is not None,
        "best_match": best_match,
        "enrichment": enrichment,
        "attempt_count": len(attempts),
        "attempts": attempts,
    }