# app/util/side_effects_parser.py

import re
from typing import Dict, List, Set
from app.util.side_effects_terms import SIDE_EFFECT_TERMS, SERIOUS_SIDE_EFFECTS


def _normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[%_/]", " ", text)
    text = re.sub(r"[^a-z0-9\s-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _join_blocks(blocks: List[str]) -> str:
    return " ".join(str(x) for x in (blocks or []) if x)


def _match_terms_in_text(text: str) -> Set[str]:
    normalized = _normalize_text(text)
    found: Set[str] = set()

    for label, variants in SIDE_EFFECT_TERMS.items():
        for variant in variants:
            pattern = rf"\b{re.escape(variant.lower())}\b"
            if re.search(pattern, normalized):
                found.add(label)
                break

    return found


def extract_side_effects_from_text_blocks(blocks: List[str]) -> List[str]:
    """
    Backward-compatible helper:
    combine blocks and return a flat deduped side effects list.
    """
    combined = _join_blocks(blocks)
    return sorted(_match_terms_in_text(combined))


def classify_side_effects(
    adverse_reactions: List[str] | None,
    warnings_raw: List[str] | None,
    boxed_warning: List[str] | None,
) -> Dict[str, List[str]]:
    """
    Search all relevant OpenFDA fields together and classify side effects
    using source-aware rules instead of score thresholds alone.
    """

    adverse_text = _join_blocks(adverse_reactions or [])
    warnings_text = _join_blocks(warnings_raw or [])
    boxed_text = _join_blocks(boxed_warning or [])

    adverse_hits = _match_terms_in_text(adverse_text)
    warnings_hits = _match_terms_in_text(warnings_text)
    boxed_hits = _match_terms_in_text(boxed_text)

    all_terms = adverse_hits | warnings_hits | boxed_hits

    common_or_likely: List[str] = []
    possible: List[str] = []
    serious: List[str] = []

    for term in sorted(all_terms):
        in_adverse = term in adverse_hits
        in_warnings = term in warnings_hits
        in_boxed = term in boxed_hits

        source_count = sum([in_adverse, in_warnings, in_boxed])

        # 1) Serious always wins
        if term in SERIOUS_SIDE_EFFECTS or in_boxed:
            serious.append(term)
            continue

        # 2) Adverse reactions are strongest signal for ordinary/common effects
        if in_adverse and source_count >= 2:
            common_or_likely.append(term)
            continue

        if in_adverse:
            common_or_likely.append(term)
            continue

        # 3) Warnings-only hits should still appear, just as possible
        if in_warnings:
            possible.append(term)
            continue

    return {
        "common_or_likely": common_or_likely,
        "possible": possible,
        "serious": serious,
        "all": common_or_likely + possible + serious,
    }