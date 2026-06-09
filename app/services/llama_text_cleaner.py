# ollama run llama3.2:3b-instruct-q4_K_M

import json, httpx, re, os
from typing import List, Dict, Any, Union

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.getenv("LLAMA_MODEL", "llama3.2:3b-instruct-q4_K_M")


PROMPT_PREFIX = """You clean and summarize FDA warning text into short, customer-friendly sentences and group them.

Rules:
- Split run-on text into sentences.
- Generate categories based on warnings mentioned (e.g., Allergy Warning, Pregnancy Warning, Liver Warning, Eye Warning etc).
- For each category created, summarize the warning detail in 1-2 sentences (the shorter the better).
- Generate a list of side effects (one to 5 words) mentioned based the the provided warning after the "TEXT" clause.
- Keep warnings and side effects separate. Warnings go under warnings_key, side effects go under side_effects.
- Remove bullets and other unnecessary special characters (•, ■, -, *) and fix spacing.
- Sentence-case each sentence. Keep acronyms uppercase (NSAID, MAOI).
- End every sentence with a single period.
- Remove duplicates.

Return ONLY valid single JSON. Do not include anything else in the response. Put everything under a single warnings_key or a single side_effects key The following is an example structure you should follow (adapt categories as needed). 


{
  "warnings_key": {
    "allergy": "...",
    "liver": "....",
    "pregnancy": "...",
    "driving_or_machinery": "...",
    "cardiovascular": "....",
    "other": "...."
  },
  side_effects: [
  '...', 
  '...',
  ]
}   

TEXT:
"""

def _safe_json_find(s: str) -> Dict[str, Any]:
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {}


def _safe_json_find(s: str) -> Dict[str, Any]:
    if not s:
        return {}

    # 1) direct parse (best case: pure JSON)
    s2 = s.strip()
    try:
        obj = json.loads(s2)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    # 2) strip common code fences
    s2 = re.sub(r"^\s*```(?:json)?\s*", "", s2, flags=re.I)
    s2 = re.sub(r"\s*```\s*$", "", s2)

    try:
        obj = json.loads(s2)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    # 3) fallback: find first JSON object block (non-greedy)
    m = re.search(r"\{.*?\}", s2, flags=re.S)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}
    
def _unwrap_warnings_key_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(data, dict):
        return {}
    wk = data.get("warnings_key")
    if isinstance(wk, dict):
        while isinstance(wk.get("warnings_key"), dict):
            wk = wk["warnings_key"]
        return wk
    return {}

def _normalize_side_effects(data: Dict[str, Any]) -> List[str]:
    se = data.get("side_effects") if isinstance(data, dict) else None
    if not isinstance(se, list):
        return []
    out = []
    for x in se:
        if isinstance(x, str):
            s = x.strip()
            if s:
                out.append(s)
    # de-dupe, preserve order
    seen = set()
    deduped = []
    for s in out:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            deduped.append(s)
    return deduped


async def clean_with_llama(warnings_text: Union[str, List[str]], timeout=25) -> Dict[str, Any]:
    print(f"LLama cleaning warnings_text: {warnings_text}")

    if isinstance(warnings_text, list):
        joined = " ".join(str(x) for x in warnings_text if x)
    else:
        joined = str(warnings_text or "")

    joined = joined.strip()
    if not joined:
        print("LLama v1: empty input, skipping.")
        return {"warnings_key": {}, "warnings_simple": []}

    base = OLLAMA_URL.rstrip("/")
    generate_url = base if base.endswith("/api/generate") else f"{base}/api/generate"

    payload = {
        "model": MODEL,
        "prompt": PROMPT_PREFIX + joined,  # PROMPT_PREFIX unchanged
        "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 5000}, # setting the value to 5000 fixes truncation issues
        "stream": False,                       # ✅ prevent multiple JSON objects
        "format": "json",                      
    }

    print(f"LLama v1 posting to: {generate_url}")

    # More robust timeouts like v2
    req_timeout = httpx.Timeout(connect=5.0, read=timeout, write=10.0, pool=5.0)

    # Retry a couple times for transient connect issues
    backoffs = [0.0, 0.75, 1.5]

    async with httpx.AsyncClient(timeout=req_timeout) as client:
        # quick health check: if this fails, you’ll get a clear error
        try:
            tags = await client.get(f"{base}/api/tags", timeout=5.0)
            print(f"LLama v1 health /api/tags status: {tags.status_code}")
        except Exception as e:
            print(f"LLama v1 health check error: {type(e).__name__}: {repr(e)}")


        for attempt, delay in enumerate(backoffs, 1):
            if delay:
                import asyncio
                await asyncio.sleep(delay)

            # print(f"LLama v1 attempt {attempt}/{len(backoffs)} (streaming)")
            try:
                out_chunks: List[str] = []
                async with client.stream("POST", generate_url, json=payload) as r:
                    # print(f"LLama v1 status: {r.status_code}")
                    if r.status_code != 200:
                        body = (await r.aread())[:300]
                        # print(f"LLama v1 non-200 body (first 300): {body}")
                        last_err = RuntimeError(f"Non-200: {r.status_code}")
                        continue

                    async for line in r.aiter_lines():
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            out_chunks.append(obj.get("response", ""))
                            if obj.get("done") is True:
                                break
                        except Exception:
                            pass

                # print(f"LLama raw chunks: {out_chunks[:3]} ... (total {len(out_chunks)})")
                text = "".join(out_chunks)

                print( "LLama v1 full json:", text)
                data = _safe_json_find(text)

                if not data:
                    print("LLama v1: could not extract JSON from output.")
                    return {"warnings_key": {}, "warnings_simple": []}

                warning_data = _unwrap_warnings_key_dict(data)
                side_effects = _normalize_side_effects(data)
                warnings_simple = data.get("warnings_simple", []) if isinstance(data, dict) else []
                symptom_table = data.get("adverse_reactions_table", []) if isinstance(data, dict) else []

                returnObj = {
                    "warnings_key": warning_data or {},
                    "side_effects": side_effects,
                    "warnings_simple": warnings_simple if isinstance(warnings_simple, list) else [],
                    "adverse_reactions_table": symptom_table if isinstance(symptom_table, list) else [],
                }
                print(returnObj)
                return returnObj

            except (httpx.ConnectError, httpx.ReadTimeout, httpx.ConnectTimeout) as e:
                last_err = e
                print(f"LLama v1 HTTP error (attempt {attempt}): {type(e).__name__}: {repr(e)}")
                continue
            except Exception as e:
                last_err = e
                print(f"LLama v1 unexpected error: {type(e).__name__}: {repr(e)}")
                break
