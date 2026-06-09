import re
from typing import List

def normalize_scanned_code_input(value: str) -> str:
    return re.sub(r"[^0-9-]", "", (value or "").strip())

def generate_ndc10_candidates(raw: str) -> List[str]:
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 10:
        return []

    return [
        f"{digits[:4]}-{digits[4:8]}-{digits[8:10]}",  # 4-4-2
        f"{digits[:5]}-{digits[5:8]}-{digits[8:10]}",  # 5-3-2
        f"{digits[:5]}-{digits[5:9]}-{digits[9:10]}",  # 5-4-1
    ]

def ndc10_to_ndc11(ndc10: str) -> str | None:
    parts = ndc10.split("-")
    if len(parts) != 3:
        return None

    a, b, c = parts

    if len(a) == 4 and len(b) == 4 and len(c) == 2:
        return f"0{a}{b}{c}"      # 4-4-2 -> 5-4-2
    if len(a) == 5 and len(b) == 3 and len(c) == 2:
        return f"{a}0{b}{c}"      # 5-3-2 -> 5-4-2
    if len(a) == 5 and len(b) == 4 and len(c) == 1:
        return f"{a}{b}0{c}"      # 5-4-1 -> 5-4-2

    return None

def build_code_lookup_candidates(raw_code: str) -> List[str]:
    raw = normalize_scanned_code_input(raw_code)

    candidates: List[str] = []
    seen = set()

    def add(value: str | None):
        if value and value not in seen:
            seen.add(value)
            candidates.append(value)

    add(raw)

    digits = re.sub(r"\D", "", raw)

    # plain digits
    add(digits)

    # already-hyphenated NDC
    if raw.count("-") == 2:
        add(raw)
        add(ndc10_to_ndc11(raw))

    # 10-digit NDC typed without hyphens
    if len(digits) == 10:
        for ndc10 in generate_ndc10_candidates(digits):
            add(ndc10)
            add(ndc10_to_ndc11(ndc10))

    return candidates