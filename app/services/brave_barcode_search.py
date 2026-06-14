from __future__ import annotations

import os
import re
from typing import Any

import httpx


BRAVE_SEARCH_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")

BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

PREFERRED_BARCODE_DOMAINS = [
    "barcodespider.com",
    "otcsuperstore,com",
    "shoprite.com",
    "target.com"
]


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def require_brave_config() -> None:
    if not BRAVE_SEARCH_API_KEY:
        raise RuntimeError("Missing BRAVE_SEARCH_API_KEY")


def normalize_brave_result(item: dict[str, Any]) -> dict[str, Any]:
    profile = item.get("profile")

    if not isinstance(profile, dict):
        profile = {}

    return {
        "title": item.get("title"),
        "url": item.get("url"),
        "description": item.get("description"),
        "display_url": item.get("display_url"),
        "age": item.get("age"),
        "language": item.get("language"),
        "family_friendly": item.get("family_friendly"),
        "source_name": profile.get("name"),
        "source_long_name": profile.get("long_name"),
        "source_url": profile.get("url"),
    }


def clean_possible_product_name(value: str, barcode: str) -> str | None:
    cleaned = value.strip()

    if not cleaned:
        return None

    barcode_digits = only_digits(barcode)

    for delimiter in [
        " - ",
        " | ",
        " – ",
        " — ",
        " at ",
        " : ",
    ]:
        if delimiter in cleaned:
            cleaned = cleaned.split(delimiter)[0].strip()

    cleaned = cleaned.strip(" .:-|")

    lowered = cleaned.lower()

    noisy_terms = [
        "upc",
        "barcode",
        "bar code",
        "product details",
        "price",
        "buy",
        "shopping",
        "walmart",
        "amazon",
        "target",
        "ebay",
        "instacart",
        barcode_digits,
    ]

    if len(cleaned) < 3:
        return None

    if lowered in noisy_terms:
        return None

    if barcode_digits and cleaned == barcode_digits:
        return None

    return cleaned


def is_preferred_source(
    result: dict[str, Any],
    preferred_domains: list[str],
) -> bool:
    url_parts = [
        result.get("url"),
        result.get("display_url"),
        result.get("source_url"),
    ]

    combined = " ".join(
        str(part).lower()
        for part in url_parts
        if part
    )

    return any(
        domain.lower() in combined
        for domain in preferred_domains
    )


def guess_product_names_from_results(
    results: list[dict[str, Any]],
    barcode: str,
    *,
    preferred_domains: list[str] | None = None,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    preferred_domains = preferred_domains or []

    for index, result in enumerate(results):
        source_texts = [
            result.get("title"),
            result.get("description"),
        ]

        preferred_source = is_preferred_source(
            result,
            preferred_domains,
        )

        for source_text in source_texts:
            if not isinstance(source_text, str):
                continue

            cleaned = clean_possible_product_name(
                source_text,
                barcode,
            )

            if not cleaned:
                continue

            if cleaned in seen:
                continue

            seen.add(cleaned)

            confidence = "high" if preferred_source else "medium" if index <= 2 else "low"

            candidates.append(
                {
                    "name": cleaned,
                    "source_result_index": index,
                    "source": result.get("source_name"),
                    "url": result.get("url"),
                    "preferred_source": preferred_source,
                    "confidence": confidence,
                }
            )

            break

    return candidates[:5]


def build_brave_barcode_queries(
    normalized_digits: str,
    *,
    exact: bool,
    preferred_domains: list[str],
) -> list[dict[str, Any]]:
    base_query = f'"{normalized_digits}"' if exact else normalized_digits

    queries: list[dict[str, Any]] = []

    for domain in preferred_domains:
        queries.append(
            {
                "label": f"preferred_domain:{domain}",
                "query": f"{base_query} site:{domain}",
                "preferred_domain": domain,
                "preferred": True,
            }
        )

    queries.append(
        {
            "label": "general_web",
            "query": base_query,
            "preferred_domain": None,
            "preferred": False,
        }
    )

    return queries


def run_brave_web_search(
    query: str,
    *,
    count: int,
    country: str,
    search_lang: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    require_brave_config()

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            BRAVE_WEB_SEARCH_URL,
            params={
                "q": query,
                "count": str(max(1, min(count, 10))),
                "country": country,
                "search_lang": search_lang,
            },
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_SEARCH_API_KEY,
            },
        )

    response.raise_for_status()

    data = response.json()

    web = data.get("web")

    if not isinstance(web, dict):
        web = {}

    raw_results = web.get("results")

    if not isinstance(raw_results, list):
        raw_results = []

    results = [
        normalize_brave_result(item)
        for item in raw_results
        if isinstance(item, dict)
    ]

    return {
        "query": query,
        "matched": len(results) > 0,
        "results": results,
    }


def search_barcode_with_brave(
    barcode: str,
    *,
    count: int = 5,
    exact: bool = True,
    country: str = "us",
    search_lang: str = "en",
    preferred_domains: list[str] | None = None,
    prefer_domain_first: bool = True,
    fallback_to_general: bool = True,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    require_brave_config()

    normalized_digits = only_digits(barcode)

    if not normalized_digits:
        return {
            "input": barcode,
            "matched": False,
            "message": "Barcode must contain digits.",
            "results": [],
            "candidate_product_names": [],
            "attempts": [],
        }

    preferred_domains = preferred_domains or PREFERRED_BARCODE_DOMAINS

    if prefer_domain_first:
        query_plan = build_brave_barcode_queries(
            normalized_digits,
            exact=exact,
            preferred_domains=preferred_domains,
        )
    else:
        base_query = f'"{normalized_digits}"' if exact else normalized_digits

        query_plan = [
            {
                "label": "general_web",
                "query": base_query,
                "preferred_domain": None,
                "preferred": False,
            }
        ]

    attempts: list[dict[str, Any]] = []
    selected_attempt: dict[str, Any] | None = None

    for query_config in query_plan:
        if not fallback_to_general and not query_config["preferred"]:
            continue

        search_result = run_brave_web_search(
            query_config["query"],
            count=count,
            country=country,
            search_lang=search_lang,
            timeout_seconds=timeout_seconds,
        )

        attempt = {
            "label": query_config["label"],
            "query": query_config["query"],
            "preferred_domain": query_config["preferred_domain"],
            "preferred": query_config["preferred"],
            "matched": search_result["matched"],
            "result_count": len(search_result["results"]),
            "results": search_result["results"],
        }

        attempts.append(attempt)

        if search_result["matched"]:
            selected_attempt = attempt
            break

    selected_results = (
        selected_attempt["results"]
        if selected_attempt
        else []
    )

    candidate_product_names = guess_product_names_from_results(
        selected_results,
        normalized_digits,
        preferred_domains=preferred_domains,
    )

    return {
        "input": barcode,
        "normalized_digits": normalized_digits,
        "matched": selected_attempt is not None,
        "selected_source": selected_attempt["label"] if selected_attempt else None,
        "query": selected_attempt["query"] if selected_attempt else None,
        "preferred_domains": preferred_domains,
        "candidate_product_names": candidate_product_names,
        "results": selected_results,
        "attempts": attempts,
    }