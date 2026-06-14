from __future__ import annotations

import os
from typing import Any

import httpx


RXNORM_BASE_URL = os.getenv(
    "RXNORM_BASE_URL",
    "https://rxnav.nlm.nih.gov",
).rstrip("/")


PRODUCT_TTYS = {
    "SBD",
    "SCD",
    "BPCK",
    "GPCK",
}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _as_str_list(value: Any) -> list[str]:
    result: list[str] = []

    for item in _as_list(value):
        if item is None:
            continue

        text = str(item).strip()

        if text:
            result.append(text)

    return result


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    for value in values:
        if value in seen:
            continue

        seen.add(value)
        result.append(value)

    return result


def _rxnorm_get(
    path: str,
    *,
    params: dict[str, Any] | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, Any]:
    url = f"{RXNORM_BASE_URL}{path}"

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.get(
            url,
            params=params or {},
            headers={
                "Accept": "application/json",
            },
        )

    response.raise_for_status()

    return response.json()


def is_product_tty(
    tty: str | None,
) -> bool:
    return bool(tty and tty.upper() in PRODUCT_TTYS)


def find_rxcuis_by_name(
    name: str,
    *,
    search: int = 2,
    allsrc: int = 0,
) -> list[str]:
    """
    findRxcuiByString:
    GET /REST/rxcui.json?name=<name>&search=<0|1|2|9>&allsrc=<0|1>

    search:
    0 = exact
    1 = normalized
    2 = exact or normalized
    9 = approximate
    """
    data = _rxnorm_get(
        "/REST/rxcui.json",
        params={
            "name": name,
            "search": str(search),
            "allsrc": str(allsrc),
        },
    )

    id_group = data.get("idGroup")

    if not isinstance(id_group, dict):
        return []

    return _unique(
        _as_str_list(
            id_group.get("rxnormId")
        )
    )


def approximate_rxcuis_by_name(
    name: str,
    *,
    max_entries: int = 3,
    option: int = 1,
) -> list[dict[str, Any]]:
    """
    getApproximateMatch:
    GET /REST/approximateTerm.json?term=<name>&maxEntries=<n>&option=<0|1>

    option:
    0 = current concepts
    1 = active concepts
    """
    data = _rxnorm_get(
        "/REST/approximateTerm.json",
        params={
            "term": name,
            "maxEntries": str(max_entries),
            "option": str(option),
        },
    )

    group = data.get("approximateGroup")

    if not isinstance(group, dict):
        return []

    candidates = group.get("candidate")

    result: list[dict[str, Any]] = []

    for item in _as_list(candidates):
        if not isinstance(item, dict):
            continue

        rxcui = item.get("rxcui")

        if not rxcui:
            continue

        result.append(
            {
                "rxcui": str(rxcui),
                "rxaui": item.get("rxaui"),
                "score": item.get("score"),
                "rank": item.get("rank"),
                "name": item.get("name"),
                "source": "approximateTerm",
            }
        )

    return result


def get_rx_concept_properties(
    rxcui: str,
) -> dict[str, Any] | None:
    data = _rxnorm_get(
        f"/REST/rxcui/{rxcui}/properties.json"
    )

    props = data.get("properties")

    if isinstance(props, dict):
        return props

    return None


def get_drug_products_by_name(
    name: str,
) -> list[dict[str, Any]]:
    """
    getDrugs:
    GET /REST/drugs.json?name=<name>

    This expands brand/group/form names into product-level concepts.
    Product-level concepts are the ones that can usually return NDCs:
    SBD, SCD, BPCK, GPCK.
    """
    data = _rxnorm_get(
        "/REST/drugs.json",
        params={
            "name": name,
        },
    )

    drug_group = data.get("drugGroup")

    if not isinstance(drug_group, dict):
        return []

    concept_groups = drug_group.get("conceptGroup")

    products: list[dict[str, Any]] = []

    for group in _as_list(concept_groups):
        if not isinstance(group, dict):
            continue

        tty = group.get("tty")

        if not is_product_tty(str(tty) if tty else None):
            continue

        concept_properties = group.get("conceptProperties")

        for item in _as_list(concept_properties):
            if not isinstance(item, dict):
                continue

            rxcui = item.get("rxcui")

            if not rxcui:
                continue

            products.append(
                {
                    "rxcui": str(rxcui),
                    "name": item.get("name"),
                    "synonym": item.get("synonym"),
                    "tty": tty,
                    "language": item.get("language"),
                    "suppress": item.get("suppress"),
                    "source": "getDrugs",
                }
            )

    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    for product in products:
        rxcui = product["rxcui"]

        if rxcui in seen:
            continue

        seen.add(rxcui)
        result.append(product)

    return result


def expand_candidate_to_product_concepts(
    *,
    rxcui: str,
    concept_name: str | None,
    tty: str | None,
    approximate_name: str | None = None,
    max_products: int = 3,
) -> list[dict[str, Any]]:
    """
    If the candidate is already product-level, keep it.
    If it is BN/SBDG/SBDF/etc., expand by name through getDrugs().
    """
    if is_product_tty(tty):
        return [
            {
                "rxcui": rxcui,
                "name": concept_name,
                "tty": tty,
                "source": "original_product_candidate",
            }
        ]

    names_to_try: list[str] = []

    if concept_name:
        names_to_try.append(concept_name)

    if approximate_name and approximate_name not in names_to_try:
        names_to_try.append(approximate_name)

    products: list[dict[str, Any]] = []

    for name in names_to_try:
        try:
            products.extend(
                get_drug_products_by_name(name)
            )
        except Exception:
            continue

    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    for product in products:
        product_rxcui = product.get("rxcui")

        if not product_rxcui:
            continue

        if product_rxcui in seen:
            continue

        seen.add(product_rxcui)
        result.append(product)

        if len(result) >= max_products:
            break

    return result


def get_active_ndcs_for_rxcui(
    rxcui: str,
) -> list[str]:
    data = _rxnorm_get(
        f"/REST/rxcui/{rxcui}/ndcs.json"
    )

    ndc_group = data.get("ndcGroup")

    if not isinstance(ndc_group, dict):
        return []

    ndc_list = ndc_group.get("ndcList")

    if not isinstance(ndc_list, dict):
        return []

    return _unique(
        _as_str_list(
            ndc_list.get("ndc")
        )
    )


def get_historical_ndcs_for_rxcui(
    rxcui: str,
    *,
    history: int = 2,
) -> list[dict[str, Any]]:
    """
    getAllHistoricalNDCs:
    GET /REST/rxcui/{rxcui}/allhistoricalndcs.json?history=0|1|2

    history:
    0 = presently directly associated
    1 = ever directly associated
    2 = ever directly or indirectly associated
    """
    data = _rxnorm_get(
        f"/REST/rxcui/{rxcui}/allhistoricalndcs.json",
        params={
            "history": str(history),
        },
    )

    concept = data.get("historicalNdcConcept")

    if not isinstance(concept, dict):
        return []

    historical_times = concept.get("historicalNdcTime")

    rows: list[dict[str, Any]] = []

    for historical_item in _as_list(historical_times):
        if not isinstance(historical_item, dict):
            continue

        status = historical_item.get("status")
        ndc_times = historical_item.get("ndcTime")

        for ndc_time in _as_list(ndc_times):
            if not isinstance(ndc_time, dict):
                continue

            ndcs = _as_str_list(ndc_time.get("ndc"))

            for ndc in ndcs:
                rows.append(
                    {
                        "ndc": ndc,
                        "status": status,
                        "start_date": ndc_time.get("startDate"),
                        "end_date": ndc_time.get("endDate"),
                    }
                )

    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    for row in rows:
        ndc = row["ndc"]

        if ndc in seen:
            continue

        seen.add(ndc)
        result.append(row)

    return result


def get_ndcs_for_product_concept(
    *,
    product: dict[str, Any],
    include_historical: bool,
    history: int,
) -> dict[str, Any]:
    product_rxcui = product["rxcui"]

    active_ndcs: list[str] = []
    historical_ndcs: list[dict[str, Any]] = []
    errors: list[str] = []

    try:
        active_ndcs = get_active_ndcs_for_rxcui(
            product_rxcui
        )
    except Exception as exc:
        errors.append(
            f"Failed to fetch active NDCs: {exc}"
        )

    if include_historical:
        try:
            historical_ndcs = get_historical_ndcs_for_rxcui(
                product_rxcui,
                history=history,
            )
        except Exception as exc:
            errors.append(
                f"Failed to fetch historical NDCs: {exc}"
            )

    all_ndcs = _unique(
        active_ndcs
        + [
            row["ndc"]
            for row in historical_ndcs
            if row.get("ndc")
        ]
    )

    return {
        "rxcui": product_rxcui,
        "name": product.get("name"),
        "synonym": product.get("synonym"),
        "tty": product.get("tty"),
        "source": product.get("source"),
        "active_ndcs": active_ndcs,
        "historical_ndcs": historical_ndcs,
        "all_ndcs": all_ndcs,
        "active_ndc_count": len(active_ndcs),
        "historical_ndc_count": len(historical_ndcs),
        "all_ndc_count": len(all_ndcs),
        "errors": errors,
    }


def resolve_name_to_rxnorm_ndcs(
    name: str,
    *,
    search: int = 2,
    allsrc: int = 0,
    include_approximate: bool = True,
    include_historical: bool = True,
    history: int = 2,
    max_candidates: int = 3,
    max_approximate_entries: int = 3,
    max_products_per_candidate: int = 3,
) -> dict[str, Any]:
    cleaned_name = name.strip()

    if not cleaned_name:
        return {
            "input": name,
            "matched": False,
            "message": "Name is required.",
            "rxcui_count": 0,
            "candidates": [],
        }

    exact_or_normalized_rxcuis = find_rxcuis_by_name(
        cleaned_name,
        search=search,
        allsrc=allsrc,
    )

    approximate_candidates: list[dict[str, Any]] = []

    if include_approximate:
        approximate_candidates = approximate_rxcuis_by_name(
            cleaned_name,
            max_entries=max_approximate_entries,
            option=1,
        )

    candidate_rxcuis: list[str] = []

    for rxcui in exact_or_normalized_rxcuis:
        candidate_rxcuis.append(rxcui)

    for candidate in approximate_candidates:
        rxcui = candidate.get("rxcui")

        if rxcui:
            candidate_rxcuis.append(str(rxcui))

    candidate_rxcuis = _unique(candidate_rxcuis)[:max_candidates]

    candidates: list[dict[str, Any]] = []

    for rxcui in candidate_rxcuis:
        props: dict[str, Any] | None = None
        errors: list[str] = []

        try:
            props = get_rx_concept_properties(rxcui)
        except Exception as exc:
            errors.append(
                f"Failed to fetch concept properties: {exc}"
            )

        approximate_meta = next(
            (
                candidate
                for candidate in approximate_candidates
                if str(candidate.get("rxcui")) == rxcui
            ),
            None,
        )

        source = (
            "findRxcuiByString"
            if rxcui in exact_or_normalized_rxcuis
            else "approximateTerm"
        )

        concept_name = (
            props.get("name")
            if props
            else approximate_meta.get("name")
            if approximate_meta
            else None
        )

        concept_tty = (
            props.get("tty")
            if props
            else None
        )

        approximate_name = (
            approximate_meta.get("name")
            if approximate_meta
            else None
        )

        product_concepts = expand_candidate_to_product_concepts(
            rxcui=rxcui,
            concept_name=concept_name,
            tty=concept_tty,
            approximate_name=approximate_name,
            max_products=max_products_per_candidate,
        )

        product_results = [
            get_ndcs_for_product_concept(
                product=product,
                include_historical=include_historical,
                history=history,
            )
            for product in product_concepts
        ]

        all_ndcs = _unique(
            [
                ndc
                for product in product_results
                for ndc in product.get("all_ndcs", [])
            ]
        )

        active_ndcs = _unique(
            [
                ndc
                for product in product_results
                for ndc in product.get("active_ndcs", [])
            ]
        )

        historical_ndcs = [
            row
            for product in product_results
            for row in product.get("historical_ndcs", [])
        ]

        candidates.append(
            {
                "rxcui": rxcui,
                "source": source,
                "approximate_match": approximate_meta,
                "concept": {
                    "name": props.get("name") if props else None,
                    "synonym": props.get("synonym") if props else None,
                    "tty": props.get("tty") if props else None,
                    "language": props.get("language") if props else None,
                    "suppress": props.get("suppress") if props else None,
                    "umlscui": props.get("umlscui") if props else None,
                },
                "expanded_product_count": len(product_results),
                "expanded_products": product_results,
                "active_ndcs": active_ndcs,
                "historical_ndcs": historical_ndcs,
                "all_ndcs": all_ndcs,
                "active_ndc_count": len(active_ndcs),
                "historical_ndc_count": len(historical_ndcs),
                "all_ndc_count": len(all_ndcs),
                "errors": errors,
            }
        )

    matched_candidates = [
        candidate
        for candidate in candidates
        if candidate["all_ndc_count"] > 0
    ]

    return {
        "input": name,
        "normalized_name": cleaned_name,
        "matched": len(matched_candidates) > 0,
        "search": {
            "search": search,
            "allsrc": allsrc,
            "include_approximate": include_approximate,
            "include_historical": include_historical,
            "history": history,
            "max_candidates": max_candidates,
            "max_approximate_entries": max_approximate_entries,
            "max_products_per_candidate": max_products_per_candidate,
        },
        "rxcui_count": len(candidate_rxcuis),
        "matched_candidate_count": len(matched_candidates),
        "best_match": matched_candidates[0] if matched_candidates else None,
        "candidates": candidates,
    }