# app/services/external_enrichment.py
from __future__ import annotations

from typing import Optional


def clean_display_name(name: str | None) -> str | None:
    if not name:
        return None
    return " ".join(name.strip().split())


def build_plain_summary(
    source_type: str,
    reason: str | None = None,
    classification: str | None = None,
) -> str:
    if source_type == "recall":
        if reason and classification:
            return f"FDA recall notice ({classification}) related to: {reason}"
        if reason:
            return f"FDA recall notice related to: {reason}"
        return "FDA recall notice."

    if source_type == "label_update":
        return "FDA label-related update."

    if source_type == "approval":
        return "FDA drug approval or regulatory update."

    return "Official drug-related update."


def build_medlineplus_search_url(name: str | None) -> str | None:
    if not name:
        return None
    from urllib.parse import quote_plus
    return f"https://medlineplus.gov/druginfo/meds-search.html?query={quote_plus(name)}"


def build_dailymed_search_url(name: str | None) -> str | None:
    if not name:
        return None
    from urllib.parse import quote_plus
    return f"https://dailymed.nlm.nih.gov/dailymed/search.cfm?query={quote_plus(name)}"