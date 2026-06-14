# openfda.py
from app.util.normalize_drug_details import _normalize_dosage, _normalize_indications, _score_label, _text_list, _to_bullets
import httpx
from typing import Optional, Dict, Any, List, Tuple

import difflib

OPENFDA_BASE_URL = "https://api.fda.gov/drug/label.json"

async def get_drug_info(drug: str) -> Optional[Dict[str, Any]]:
    """
    Rich, ranked label fetch that extracts indications, warnings, adverse reactions,
    interactions, dosage, and metadata for display.
    """
    search_fields = ["openfda.brand_name", "openfda.generic_name", "openfda.substance_name"]
    best: Dict[str, Any] = {}
    best_score = -1
    # print(f"get_drug_info: searching OpenFDA for drug: {drug}")
    async with httpx.AsyncClient(timeout=20.0) as client:
        # print(f"get_drug_info: querying OpenFDA with search fields: {search_fields}")
        for field in search_fields:
            # Quote the query for stricter matching; adjust if you want broader search
            params = {"search": f'{field}:"{drug}"', "limit": 50}
            try:
                # print( f"Querying OpenFDA with params: {params}")
                resp = await client.get(OPENFDA_BASE_URL, params=params)
                resp.raise_for_status()
                results = resp.json().get("results", []) or []
                for r in results:
                    s, _ = _score_label(drug, r)
                    if s > best_score:
                        best_score = s
                        best = r
                # If we already found a strong brand hit, we can break early.
                if best_score >= 60:
                    break
            except httpx.HTTPError:
                print(f"OpenFDA request error for field {field}: {httpx.HTTPError}")
                continue

    if not best:
        return None
    # print(f"get_drug_info: best OpenFDA match score: {best_score} for drug: {drug}")
    ofda = best.get("openfda", {}) or {}
    indications = _normalize_indications(
        best.get("indications_and_usage") or best.get("purpose") or [],
        max_items=12,
    )
    # print(f"get_drug_info: extracted {len(indications)} indications for drug: {drug}")
    print(f"indication raw: {indications}")
    warnings = _text_list(best.get("warnings"))
    boxed = _to_bullets(best.get("boxed_warning", []), max_items=20)
    adverse = _to_bullets(best.get("adverse_reactions", []), max_items=30)
    interactions = _to_bullets(best.get("drug_interactions", []), max_items=20)
    dosage = _normalize_dosage(
        best.get("dosage_and_administration", []) or best.get("dosage_and_administration_table", []),
        max_items=18,
    )

    # New: extract adverse reactions HTML tables if present
    symptoms_table = best.get("adverse_reactions_table") or []
    if not isinstance(symptoms_table, list):
        symptoms_table = [str(symptoms_table)]
    else:
        symptoms_table = [str(x) for x in symptoms_table if x]

    payload: Dict[str, Any] = {
        "brand_names": ofda.get("brand_name", []),
        "generic_names": ofda.get("generic_name", []),
        "manufacturer_names": ofda.get("manufacturer_name", []),
    
        # identifiers
        "upc_codes": ofda.get("upc", []),
        "package_ndc": ofda.get("package_ndc", []),
        "unii": ofda.get("unii", []),
        "rxcui": ofda.get("rxcui", []),
    
        "route": ofda.get("route", []),
        "product_type": ofda.get("product_type", []),
        "purpose_or_indications": indications,
        "boxed_warning": boxed,
        "warnings_raw": warnings,
        "adverse_reactions": adverse,
        "drug_interactions": interactions,
        "dosage_and_administration": dosage,
        "symptoms_table": symptoms_table,
        "effective_time": best.get("effective_time"),
        "openfda_meta": {
            "product_ndc": ofda.get("product_ndc", []),
            "package_ndc": ofda.get("package_ndc", []),
            "upc": ofda.get("upc", []),
            "unii": ofda.get("unii", []),
            "rxcui": ofda.get("rxcui", []),
            "substance_name": ofda.get("substance_name", []),
            "spl_set_id": ofda.get("spl_set_id", []),
            "spl_id": ofda.get("spl_id", []),
        },
        "source": "openfda.label",
        "query_used": drug,
    }
    # print(f"get_drug_info: returning payload for drug: {drug} with keys: {sorted(payload.keys())}")
    return payload


SUGGEST_FIELDS = [
    "openfda.brand_name",
    "openfda.generic_name",
    "openfda.substance_name",
]


async def search_drug_names(query: str, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Return a ranked list of name suggestions (brand/generic/substance).
    Works even for partials & mild misspellings by:
      1) querying multiple OpenFDA fields,
      2) extracting + deduping names,
      3) scoring with fuzzy ratio (difflib),
      4) returning top N with a 'type' and optional 'manufacturer'.
    """
    q = (query or "").strip()
    if not q:
        return []

    names: Dict[str, Dict[str, Any]] = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            for field in SUGGEST_FIELDS:
                # be generous: get a bunch of docs, then mine names locally
                params = {"search": f"{field}:{q}", "limit": 100}
                try:
                    r = await client.get(OPENFDA_BASE_URL, params=params)
                    r.raise_for_status()
                except Exception:
                    continue

                results = (r.json() or {}).get("results", []) or []
                for doc in results:
                    ofda = doc.get("openfda", {}) or {}
                    # collect all candidate arrays from this document
                    candidates: List[Tuple[str, str]] = []
                    for key, typ in [
                        ("brand_name", "brand"),
                        ("generic_name", "generic"),
                        ("substance_name", "substance"),
                    ]:
                        for val in ofda.get(key, []) or []:
                            name = str(val).strip()
                            if name:
                                candidates.append((name, typ))
                        
                    manufacturer = (ofda.get("manufacturer_name") or [None])[0]
                    upc_codes = ofda.get("upc", []) or []

                    ndc_codes = []
                    ndc_codes.extend(ofda.get("package_ndc", []) or [])
                    ndc_codes.extend(ofda.get("product_ndc", []) or [])

                    # add to global dictionary (dedupe by normalized name)
                    for name, typ in candidates:
                        k = name.lower()
                        entry = names.get(k)

                        if not entry:
                            names[k] = {
                                "name": name,
                                "type": typ,
                                "manufacturer": manufacturer,
                                "upc_codes": upc_codes,
                                "ndc_codes": ndc_codes,
                            }
                        else:
                            # prefer a more specific type order: brand > generic > substance
                            rank = {"brand": 3, "generic": 2, "substance": 1}

                            if rank.get(typ, 0) > rank.get(entry["type"], 0):
                                entry["type"] = typ

                            if not entry.get("manufacturer") and manufacturer:
                                entry["manufacturer"] = manufacturer

                            entry["upc_codes"] = list(
                                dict.fromkeys(
                                    (entry.get("upc_codes") or []) + upc_codes
                                )
                            )

                            entry["ndc_codes"] = list(
                                dict.fromkeys(
                                    (entry.get("ndc_codes") or []) + ndc_codes
                                )
                            )
    except Exception:
        pass

    # fuzzy-rank against the query
    scored = []
    for entry in names.values():
        score = difflib.SequenceMatcher(None, entry["name"].lower(), q.lower()).ratio()
        scored.append({**entry, "score": round(float(score), 4)})

    scored.sort(key=lambda x: (-x["score"], x["type"] != "brand", x["name"]))
    return scored[:limit]


async def get_drug_info_by_code(code: str) -> Optional[Dict[str, Any]]:
    search_fields = [
        "openfda.upc",
        "openfda.package_ndc",
        "openfda.product_ndc",
        "openfda.rxcui",
        "openfda.unii",
    ]

    best: Dict[str, Any] = {}
    best_score = -1

    async with httpx.AsyncClient(timeout=20.0) as client:
        for field in search_fields:
            params = {"search": f'{field}:"{code}"', "limit": 10}
            try:
                resp = await client.get(OPENFDA_BASE_URL, params=params)
                resp.raise_for_status()
                results = resp.json().get("results", []) or []

                for r in results:
                    # Reuse your existing ranker for general label quality
                    s, _ = _score_label(code, r)
                    if s > best_score:
                        best_score = s
                        best = r

                if best:
                    break
            except httpx.HTTPError:
                continue

    if not best:
        return None

    ofda = best.get("openfda", {}) or {}
    indications = _to_bullets(best.get("indications_and_usage") or best.get("purpose") or [])
    warnings = _text_list(best.get("warnings"))
    boxed = _to_bullets(best.get("boxed_warning", []), max_items=20)
    adverse = _to_bullets(best.get("adverse_reactions", []), max_items=30)
    interactions = _to_bullets(best.get("drug_interactions", []), max_items=20)
    dosage = _to_bullets(
        best.get("dosage_and_administration", []) or best.get("dosage_and_administration_table", []),
        max_items=30,
    )

    symptoms_table = best.get("adverse_reactions_table") or []
    if not isinstance(symptoms_table, list):
        symptoms_table = [str(symptoms_table)]
    else:
        symptoms_table = [str(x) for x in symptoms_table if x]

    payload: Dict[str, Any] = {
        "brand_names": ofda.get("brand_name", []),
        "generic_names": ofda.get("generic_name", []),
        "manufacturer_names": ofda.get("manufacturer_name", []),
        "upc_codes": ofda.get("upc", []),
        "package_ndc": ofda.get("package_ndc", []),
        "unii": ofda.get("unii", []),
        "rxcui": ofda.get("rxcui", []),
        "route": ofda.get("route", []),
        "product_type": ofda.get("product_type", []),
        "purpose_or_indications": indications,
        "boxed_warning": boxed,
        "warnings_raw": warnings,
        "adverse_reactions": adverse,
        "drug_interactions": interactions,
        "dosage_and_administration": dosage,
        "symptoms_table": symptoms_table,
        "effective_time": best.get("effective_time"),
        "openfda_meta": {
            "product_ndc": ofda.get("product_ndc", []),
            "package_ndc": ofda.get("package_ndc", []),
            "upc": ofda.get("upc", []),
            "unii": ofda.get("unii", []),
            "rxcui": ofda.get("rxcui", []),
            "substance_name": ofda.get("substance_name", []),
            "spl_set_id": ofda.get("spl_set_id", []),
            "spl_id": ofda.get("spl_id", []),
        },
        "source": "openfda.label",
        "query_used": code,
    }
    return payload

def _drug_index_kind_priority(kind: str | None) -> int:
    normalized = (kind or "").strip().lower()

    if normalized == "brand":
        return 0

    if normalized == "generic":
        return 1

    if normalized == "substance":
        return 2

    return 3


def _matched_field_priority(field: str | None) -> int:
    normalized = (field or "").strip().lower()

    if normalized == "openfda.upc":
        return 0

    if normalized == "openfda.package_ndc":
        return 1

    if normalized == "openfda.product_ndc":
        return 2

    return 3

#  Search OpenFDA label data by UPC/NDC code and return DrugIndex-ready items.
async def search_drug_index_items_by_code(
    code: str,
    *,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    Search OpenFDA label data by UPC/NDC code and return DrugIndex-ready items.

    This intentionally focuses only on:
    - openfda.upc
    - openfda.package_ndc
    - openfda.product_ndc

    It does not use UNII or RxCUI.

    Important:
    The scanned raw code and matched lookup candidate are also saved into the
    returned code arrays so the newly upserted DrugIndex can be found by the
    same scanner input on the next local lookup.
    """
    from app.util.normailize_codes import build_code_lookup_candidates

    raw_code = (code or "").strip()

    print("raw code: ", raw_code)
    if not raw_code:
        return []

    lookup_candidates = build_code_lookup_candidates(raw_code)

    search_fields = [
        "openfda.upc",
        "openfda.package_ndc",
        "openfda.product_ndc",
    ]

    names: Dict[str, Dict[str, Any]] = {}

    async with httpx.AsyncClient(timeout=20.0) as client:
        for candidate_code in lookup_candidates:
            for field in search_fields:
                params = {
                    "search": f'{field}:"{candidate_code}"',
                    "limit": min(max(limit, 1), 100),
                }

                try:
                    resp = await client.get(
                        OPENFDA_BASE_URL,
                        params=params,
                    )

                    print(
                        "OpenFDA lookup:",
                        {
                            "field": field,
                            "candidate_code": candidate_code,
                            "status_code": resp.status_code,
                            "url": str(resp.url),
                        },
                    )

                    if resp.status_code == 404:
                        print(
                            "OpenFDA no results:",
                            {
                                "field": field,
                                "candidate_code": candidate_code,
                                "body": resp.text[:500],
                            },
                        )
                        continue
                    
                    resp.raise_for_status()

                except httpx.HTTPStatusError as exc:
                    print(
                        "OpenFDA HTTP status error:",
                        {
                            "field": field,
                            "candidate_code": candidate_code,
                            "status_code": exc.response.status_code,
                            "url": str(exc.request.url),
                            "body": exc.response.text[:1000],
                        },
                    )
                    continue
                
                except httpx.RequestError as exc:
                    print(
                        "OpenFDA request error:",
                        {
                            "field": field,
                            "candidate_code": candidate_code,
                            "url": str(exc.request.url) if exc.request else None,
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                        },
                    )
                    continue
                
                try:
                    results = resp.json().get("results", []) or []
                except ValueError as exc:
                    print(
                        "OpenFDA JSON parse error:",
                        {
                            "field": field,
                            "candidate_code": candidate_code,
                            "status_code": resp.status_code,
                            "body": resp.text[:1000],
                            "error": str(exc),
                        },
                    )
                    continue

                results = resp.json().get("results", []) or []
                
                print("new results", results)

                for doc in results:
                    ofda = doc.get("openfda", {}) or {}

                    manufacturer = (ofda.get("manufacturer_name") or [None])[0]

                    upc_codes: List[str] = []
                    upc_codes.extend(ofda.get("upc", []) or [])

                    ndc_codes: List[str] = []
                    ndc_codes.extend(ofda.get("package_ndc", []) or [])
                    ndc_codes.extend(ofda.get("product_ndc", []) or [])

                    # Preserve the scanner input that produced this match.
                    # This prevents the "OpenFDA found it, but re-query returned []" problem.
                    if field == "openfda.upc":
                        upc_codes.extend([raw_code, candidate_code])
                    else:
                        ndc_codes.extend([raw_code, candidate_code])

                    upc_codes = list(
                        dict.fromkeys(
                            str(value).strip()
                            for value in upc_codes
                            if str(value or "").strip()
                        )
                    )

                    ndc_codes = list(
                        dict.fromkeys(
                            str(value).strip()
                            for value in ndc_codes
                            if str(value or "").strip()
                        )
                    )

                    candidates: List[Tuple[str, str]] = []

                    for key, typ in [
                        ("brand_name", "brand"),
                        ("generic_name", "generic"),
                        ("substance_name", "substance"),
                    ]:
                        for value in ofda.get(key, []) or []:
                            name = str(value).strip()

                            if name:
                                candidates.append((name, typ))

                    for name, typ in candidates:
                        normalized_key = f"{name.strip().lower()}::{typ}"

                        entry = names.get(normalized_key)

                        if not entry:
                            names[normalized_key] = {
                                "name": name,
                                "type": typ,
                                "manufacturer": manufacturer,
                                "upc_codes": upc_codes,
                                "ndc_codes": ndc_codes,
                                "source": "openfda",
                                "matched_code": candidate_code,
                                "matched_field": field,
                                "raw_code": raw_code,
                            }

                            continue

                        if not entry.get("manufacturer") and manufacturer:
                            entry["manufacturer"] = manufacturer

                        entry["upc_codes"] = list(
                            dict.fromkeys(
                                (entry.get("upc_codes") or []) + upc_codes
                            )
                        )

                        entry["ndc_codes"] = list(
                            dict.fromkeys(
                                (entry.get("ndc_codes") or []) + ndc_codes
                            )
                        )

    items = list(names.values())

    items.sort(
        key=lambda item: (
            _drug_index_kind_priority(item.get("type")),
            _matched_field_priority(item.get("matched_field")),
            str(item.get("name") or "").lower(),
        )
    )
    
    return items[:limit]