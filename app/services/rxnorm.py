from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx


RXNORM_BASE_URL = os.getenv(
    "RXNORM_BASE_URL",
    "https://rxnav.nlm.nih.gov",
).rstrip("/")


@dataclass(frozen=True)
class RxNormCandidate:
    value: str
    reason: str


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def unique_candidates(candidates: list[RxNormCandidate]) -> list[RxNormCandidate]:
    seen: set[str] = set()
    result: list[RxNormCandidate] = []

    for candidate in candidates:
        if not candidate.value:
            continue

        if candidate.value in seen:
            continue

        seen.add(candidate.value)
        result.append(candidate)

    return result


def generate_ndc_candidates(raw_code: str) -> list[RxNormCandidate]:
    """
    Generate possible NDC candidates from a scanned barcode.

    RxNorm getNDCStatus accepts:
    - CMS 11-digit NDC
    - 5-3-2
    - 5-4-1
    - 4-4-2

    Package barcodes may include leading packaging/application digits
    or check digits, so this returns several candidates for testing.
    """
    cleaned = only_digits(raw_code)

    candidates: list[RxNormCandidate] = []

    if raw_code.strip():
        candidates.append(
            RxNormCandidate(
                value=raw_code.strip(),
                reason="raw_input",
            )
        )

    if cleaned:
        candidates.append(
            RxNormCandidate(
                value=cleaned,
                reason="digits_only",
            )
        )

    # Common case: scanned GTIN-14-like value where the middle 11 digits
    # may correspond to the CMS 11-digit NDC derivative.
    if len(cleaned) == 14:
        candidates.extend(
            [
                RxNormCandidate(
                    value=cleaned[1:12],
                    reason="gtin14_remove_first_and_check_digit",
                ),
                RxNormCandidate(
                    value=cleaned[2:13],
                    reason="gtin14_middle_11_digits",
                ),
                RxNormCandidate(
                    value=cleaned[:11],
                    reason="gtin14_first_11_digits",
                ),
                RxNormCandidate(
                    value=cleaned[-12:-1],
                    reason="gtin14_last_11_before_check_digit",
                ),
            ]
        )

    # UPC-A-like values sometimes include one leading system digit and one check digit.
    if len(cleaned) == 12:
        candidates.extend(
            [
                RxNormCandidate(
                    value=cleaned[1:-1],
                    reason="upca_remove_first_and_check_digit_10_digits",
                ),
                RxNormCandidate(
                    value=cleaned[:-1],
                    reason="upca_remove_check_digit_11_digits",
                ),
                RxNormCandidate(
                    value=cleaned[1:],
                    reason="upca_remove_first_digit_11_digits",
                ),
            ]
        )

    # EAN-13-like values.
    if len(cleaned) == 13:
        candidates.extend(
            [
                RxNormCandidate(
                    value=cleaned[1:-1],
                    reason="ean13_remove_first_and_check_digit_11_digits",
                ),
                RxNormCandidate(
                    value=cleaned[:-1],
                    reason="ean13_remove_check_digit_12_digits",
                ),
                RxNormCandidate(
                    value=cleaned[2:-1],
                    reason="ean13_remove_first_two_and_check_digit_10_digits",
                ),
            ]
        )

    # If already 11 digits, add likely dashed forms.
    if len(cleaned) == 11:
        candidates.extend(
            [
                RxNormCandidate(
                    value=f"{cleaned[:5]}-{cleaned[5:9]}-{cleaned[9:]}",
                    reason="11_digit_to_5_4_2",
                ),
                RxNormCandidate(
                    value=f"{cleaned[:5]}-{cleaned[5:8]}-{cleaned[8:]}",
                    reason="11_digit_to_5_3_3_test_candidate",
                ),
                RxNormCandidate(
                    value=f"{cleaned[:4]}-{cleaned[4:8]}-{cleaned[8:]}",
                    reason="11_digit_to_4_4_3_test_candidate",
                ),
            ]
        )

    # If 10 digits, test the three classic NDC segment layouts.
    if len(cleaned) == 10:
        candidates.extend(
            [
                RxNormCandidate(
                    value=f"{cleaned[:5]}-{cleaned[5:8]}-{cleaned[8:]}",
                    reason="10_digit_to_5_3_2",
                ),
                RxNormCandidate(
                    value=f"{cleaned[:5]}-{cleaned[5:9]}-{cleaned[9:]}",
                    reason="10_digit_to_5_4_1",
                ),
                RxNormCandidate(
                    value=f"{cleaned[:4]}-{cleaned[4:8]}-{cleaned[8:]}",
                    reason="10_digit_to_4_4_2",
                ),
            ]
        )

    return unique_candidates(candidates)


def get_ndc_status_from_rxnorm(
    ndc: str,
    *,
    history: int = 1,
    altpkg: int = 1,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    url = f"{RXNORM_BASE_URL}/REST/ndcstatus.json"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            url,
            params={
                "ndc": ndc,
                "history": str(history),
                "altpkg": str(altpkg),
            },
            headers={
                "Accept": "application/json",
            },
        )

    response.raise_for_status()
    return response.json()


def extract_ndc_status_payload(data: dict[str, Any]) -> dict[str, Any] | None:
    status = data.get("ndcStatus")

    if isinstance(status, dict):
        return status

    return None


def is_useful_rxnorm_status(status: dict[str, Any] | None) -> bool:
    if not status:
        return False

    ndc_status = str(status.get("status") or "").upper()

    # ACTIVE, OBSOLETE, and ALIEN can all still be useful for testing/name discovery.
    # UNKNOWN is usually not useful.
    if ndc_status in {"ACTIVE", "OBSOLETE", "ALIEN"}:
        return True

    if status.get("rxcui") or status.get("conceptName"):
        return True

    return False


def summarize_ndc_status(status: dict[str, Any] | None) -> dict[str, Any]:
    if not status:
        return {
            "found": False,
            "status": "NO_STATUS",
            "rxcui": None,
            "concept_name": None,
            "concept_status": None,
            "ndc11": None,
            "active": None,
            "rxnorm_ndc": None,
            "alt_ndc": None,
            "sources": [],
        }

    source_list = status.get("sourceList") or {}
    source_names = source_list.get("sourceName") if isinstance(source_list, dict) else []

    if isinstance(source_names, str):
        source_names = [source_names]

    if not isinstance(source_names, list):
        source_names = []

    return {
        "found": is_useful_rxnorm_status(status),
        "status": status.get("status"),
        "rxcui": status.get("rxcui"),
        "concept_name": status.get("conceptName"),
        "concept_status": status.get("conceptStatus"),
        "ndc11": status.get("ndc11"),
        "active": status.get("active"),
        "rxnorm_ndc": status.get("rxnormNdc"),
        "alt_ndc": status.get("altNdc"),
        "sources": source_names,
    }


def resolve_barcode_with_rxnorm(
    barcode: str,
    *,
    history: int = 1,
    altpkg: int = 1,
) -> dict[str, Any]:
    candidates = generate_ndc_candidates(barcode)

    attempts: list[dict[str, Any]] = []
    best_match: dict[str, Any] | None = None

    for candidate in candidates:
        try:
            raw = get_ndc_status_from_rxnorm(
                candidate.value,
                history=history,
                altpkg=altpkg,
            )

            status_payload = extract_ndc_status_payload(raw)
            summary = summarize_ndc_status(status_payload)

            attempt = {
                "candidate": candidate.value,
                "reason": candidate.reason,
                "ok": True,
                "summary": summary,
                "raw_ndc_status": status_payload,
            }

            attempts.append(attempt)

            if best_match is None and summary["found"]:
                best_match = attempt

        except httpx.HTTPStatusError as exc:
            attempts.append(
                {
                    "candidate": candidate.value,
                    "reason": candidate.reason,
                    "ok": False,
                    "error": f"RxNorm returned HTTP {exc.response.status_code}",
                }
            )

        except httpx.RequestError as exc:
            attempts.append(
                {
                    "candidate": candidate.value,
                    "reason": candidate.reason,
                    "ok": False,
                    "error": f"RxNorm request failed: {exc}",
                }
            )

    return {
        "input": barcode,
        "normalized_digits": only_digits(barcode),
        "matched": best_match is not None,
        "best_match": best_match,
        "attempt_count": len(attempts),
        "attempts": attempts,
    }