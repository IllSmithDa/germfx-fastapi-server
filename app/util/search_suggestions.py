from typing import List, Dict, Any
def _best_suggestion(
    strict_results: List[Dict[str, Any]],
    fuzzy_results: List[Dict[str, Any]], 
    original_query: str,
) -> str | None:
    if strict_results:
        return None
    if not fuzzy_results:
        return None

    top = fuzzy_results[0].get("name")
    if not top:
        return None

    if top.strip().lower() == original_query.strip().lower():
        return None

    return top