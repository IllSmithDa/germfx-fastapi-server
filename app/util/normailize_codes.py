import re
from typing import Any


def strip_code(value: str) -> str:
    return (
        str(value or "")
        .replace(" ", "")
        .replace("\t", "")
        .replace("\n", "")
        .replace("(", "")
        .replace(")", "")
        .strip()
    )


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", str(value or ""))


def unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        clean = str(value or "").strip()

        if not clean or clean in seen:
            continue

        seen.add(clean)
        result.append(clean)

    return result


def get_ndc10_candidates(digits: str) -> list[str]:
    if len(digits) != 10:
        return []

    return [
        # 4-4-2
        f"{digits[0:4]}-{digits[4:8]}-{digits[8:10]}",

        # 5-3-2
        f"{digits[0:5]}-{digits[5:8]}-{digits[8:10]}",

        # 5-4-1
        f"{digits[0:5]}-{digits[5:9]}-{digits[9:10]}",

        # Extra format based on your stored example:
        # 5166052601 -> 51660-52-601
        f"{digits[0:5]}-{digits[5:7]}-{digits[7:10]}",
    ]


def get_ndc11_candidates(digits: str) -> list[str]:
    if len(digits) != 11:
        return []

    return [
        # 5-4-2
        f"{digits[0:5]}-{digits[5:9]}-{digits[9:11]}",

        # fallback groupings
        f"{digits[0:5]}-{digits[5:8]}-{digits[8:11]}",
        f"{digits[0:4]}-{digits[4:8]}-{digits[8:11]}",
    ]


def get_upc_candidates(digits: str) -> list[str]:
    candidates: list[str] = []

    if len(digits) == 12:
        candidates.append(digits)

        if digits.startswith("0"):
            candidates.append(digits[1:])

    if len(digits) == 13:
        candidates.append(digits)

        if digits.startswith("0"):
            candidates.append(digits[1:])

    return candidates


def get_inner_upc_medication_candidates(digits: str) -> list[str]:
    candidates: list[str] = []

    # UPC-A style:
    # 3 51660 52601 1
    # full scanned: 351660526011
    # inner 10:     5166052601
    if len(digits) == 12:
        inner10 = digits[1:11]

        candidates.append(inner10)
        candidates.extend(get_ndc10_candidates(inner10))

    # EAN-13 style:
    # Try removing first and last digit to get inner 11.
    # Try removing first 2 and last 1 to get inner 10.
    if len(digits) == 13:
        without_first = digits[1:]
        inner11 = digits[1:12]
        inner10 = digits[2:12]

        candidates.append(without_first)

        candidates.append(inner11)
        candidates.extend(get_ndc11_candidates(inner11))

        candidates.append(inner10)
        candidates.extend(get_ndc10_candidates(inner10))

    return candidates


def build_code_lookup_candidates(value: Any) -> list[str]:
    stripped = strip_code(str(value or ""))
    digits = only_digits(stripped)

    candidates = [
        stripped,
        digits,

        # UPC/EAN candidates as scanned.
        *get_upc_candidates(digits),

        # Medication-specific extraction from UPC/EAN.
        *get_inner_upc_medication_candidates(digits),

        # Direct NDC-style candidates.
        *get_ndc10_candidates(digits),
        *get_ndc11_candidates(digits),
    ]

    
    return unique(candidates)