# app/util/safety_warnings_parser.py

from __future__ import annotations

import re
from typing import Dict, List, Set, Any

from app.util.safety_warnings_terms import WARNING_TERMS


def _normalize(text: str) -> str:
    text = str(text or "")
    text = text.replace("•", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _join_blocks(blocks: List[str] | None) -> str:
    if not blocks:
        return ""
    return _normalize(" ".join(str(b) for b in blocks if b))


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [_normalize(p) for p in parts if _normalize(p)]


def _find_matches(text: str, phrases: List[str]) -> Set[str]:
    lowered = text.lower()
    found: Set[str] = set()

    for phrase in phrases:
        if phrase.lower() in lowered:
            found.add(phrase)

    return found


def _collect_excerpts(sentences: List[str], phrases: List[str], limit: int = 3) -> List[str]:
    excerpts: List[str] = []
    phrases_lower = [p.lower() for p in phrases]

    for sentence in sentences:
        lowered = sentence.lower()
        if any(p in lowered for p in phrases_lower):
            excerpts.append(sentence)
        if len(excerpts) >= limit:
            break

    return excerpts


def extract_safety_warnings(
    warnings_raw: List[str] | None,
) -> Dict[str, Any]:
    text = _join_blocks(warnings_raw)
    sentences = _split_sentences(text)

    grouped: Dict[str, Dict[str, Any]] = {}
    all_categories: List[str] = []

    for category, phrases in WARNING_TERMS.items():
        matched_terms = sorted(_find_matches(text, phrases))
        if not matched_terms:
            continue

        excerpts = _collect_excerpts(sentences, phrases, limit=3)

        grouped[category] = {
            "title": category.replace("-", " ").title(),
            "matched_terms": matched_terms,
            "excerpts": excerpts,
        }
        all_categories.append(category)

    return {
        "warning_categories": all_categories,
        "warnings_grouped": grouped,
        "warnings_flat": [
            {
                "key": key,
                "title": value["title"],
                "matched_terms": value["matched_terms"],
                "excerpts": value["excerpts"],
            }
            for key, value in grouped.items()
        ],
        "raw_text": text,
    }