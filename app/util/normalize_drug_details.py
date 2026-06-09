import datetime
import re
from typing import Dict, Any, List, Optional, Tuple
from app.models import DrugDetail, DrugIndex

def _text_list(v: Any) -> List[str]:
    if not v:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if x]
    return [str(v)]

def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()
      
def _to_bullets(blocks: List[str], max_items: int = 20) -> List[str]:

    # print('running')
    if not blocks:
        return []
    raw = "\n".join([b for b in blocks if b])
    # Normalize common bullet markers & heavy HTML-ish tables to lines
    raw = raw.replace("•", "\n").replace("·", "\n").replace("●", "\n")
    # rudimentary strip of html tags
    raw = re.sub(r"<[^>]+>", " ", raw)
    parts = []
    for part in re.split(r"[\n;]+", raw):
        part = _normalize(part)
        if not part:
            continue
        # further split long narrations
        if len(part) > 200:
            parts.extend([_normalize(x) for x in re.split(r"(?<=[.!?])\s+", part) if _normalize(x)])
        else:
            parts.append(part)
    # clean bullets
    out, seen = [], set()
    for p in parts:
        p = re.sub(r"^\s*[-–—*]\s*", "", p)
        p = p.strip(" -–—*.,:;")
        if not p:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= max_items:
            break
    return out

def _score_label(drug_query: str, item: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    ofda = item.get("openfda", {}) or {}
    brand_names = [b.lower() for b in ofda.get("brand_name", [])]
    pnl = " ".join(item.get("package_label_principal_display_panel", [])).lower()
    substance = [s.lower() for s in ofda.get("substance_name", [])]
    product_type = " ".join(ofda.get("product_type", [])).lower()
    eff_time = int(item.get("effective_time", "0") or "0")

    # feature presence
    fields_present = sum(bool(item.get(k)) for k in [
        "adverse_reactions", "warnings", "indications_and_usage", "boxed_warning", "dosage_and_administration"
    ])

    score = 0
    q = drug_query.lower()

    # exact brand match boosts
    if any(q == b for b in brand_names):
        score += 40
    if "tylenol" in q and ("tylenol" in pnl or any("tylenol" in b for b in brand_names)):
        score += 30

    # substance and product type preference
    if any("acetaminophen" == s for s in substance):
        score += 15
    if "human otc drug" in product_type:
        score += 10

    # recency
    score += min(20, max(0, (eff_time // 10000) - 2000))  # rough year weighting

    # completeness
    score += fields_present * 3

    return score, item

def _to_date(yyyymmdd: Optional[str]):
    if not yyyymmdd: return None
    try:
        return datetime.strptime(yyyymmdd, "%Y%m%d").date()
    except Exception:
        return None
    
def _pick_warnings_source(base: Dict[str, Any]) -> List[str]:
    """
    Choose the best available warnings-like text source.
    Priority:
      1) warnings_raw (label 'warnings' field)
      2) boxed_warning (strong warnings)
      3) adverse_reactions (often contains safety info when warnings is missing)
    """
    if not base:
        return []

    w = base.get("warnings_raw") or []
    if isinstance(w, list) and len(w) > 0:
        return w

    boxed = base.get("boxed_warning") or []
    if isinstance(boxed, list) and len(boxed) > 0:
        return boxed

    adverse = base.get("adverse_reactions") or []
    if isinstance(adverse, list) and len(adverse) > 0:
        return adverse

    return []


def _build_payload(detail: DrugDetail, index_row: Optional[DrugIndex]) -> Dict[str, Any]:
    print("Building payload for detail id:", detail)
    print("symptoms_table:", detail.symptoms_table or [])

    return {
        "brand_names": detail.brand_names or [],
        "generic_names": detail.generic_names or [],
        "manufacturer_names": detail.manufacturer_names or [],
        "upc_codes": detail.upc_codes or [],
        "package_ndc": detail.package_ndc or [],
        "unii": detail.unii or [],
        "rxcui": detail.rxcui or [],
        "route": detail.route or [],
        "product_type": detail.product_type or [],
        "purpose_or_indications": detail.purpose_or_indications or [],
        "boxed_warning": detail.boxed_warning or [],
        "warnings_key": detail.warnings_key or {},
        "warnings_raw": detail.warnings_raw or [],
        "warnings_simple": detail.warnings_simple or [],
        "adverse_reactions": detail.adverse_reactions or [],
        "drug_interactions": detail.drug_interactions or [],
        "dosage_and_administration": detail.dosage_and_administration or [],
        "effective_time": detail.effective_time.strftime("%Y%m%d") if detail.effective_time else None,
        "openfda_meta": detail.openfda_meta or {},
        "source": detail.source,
        "query_used": detail.query_used or (index_row.name if index_row else None),
        "drug_detail_id": detail.id,
        "symptoms_table": detail.symptoms_table or [],
        "drug_index_id": (index_row.id if index_row else None),
    }

def _clean_section_refs(text: str) -> str:
    if not text:
        return text

    # Remove refs like (1), (1.1), (1.2, 1.3), ( 4.4 )
    text = re.sub(
        r"\(\s*\d+(?:\.\d+)*(?:\s*,\s*\d+(?:\.\d+)*)*\s*\)",
        " ",
        text,
    )

    # Remove refs like 2.4 ) or 4.4 ) left behind
    text = re.sub(
        r"\b\d+(?:\.\d+)+\s*\)",
        " ",
        text,
    )

    # Remove standalone inline refs like 2.1, 4.4, 5.4 when they behave like section markers
    text = re.sub(
        r"(?:(?<=\s)|^)\d+(?:\.\d+)+(?=\s+[A-Z])",
        " ",
        text,
    )

    # Remove empty parentheses
    text = re.sub(r"\(\s*\)", " ", text)

    # Remove orphaned opening parens that are clearly leftover refs
    text = re.sub(r"\(\s*(?=$|\d|\.)", " ", text)

    # remove bullet point markers
    text = text.replace("•", "").replace("·", "").replace("●", "")

    # Remove standalone nested bullet "o"
    text = re.sub(r"(?:(?<=\s)|^)[oO](?=\s)", " ", text)

    text = re.sub(r"\s+", " ", text).strip()
    return text

def _normalize_indications(blocks: List[str], max_items: int = 12) -> List[str]:
    if not blocks:
        return []

    raw = " ".join(str(b) for b in blocks if b)
    # rudimentary strip of html tags
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = raw.replace("®", "")
    raw = _normalize(raw)
    raw = _clean_section_refs(raw)

    # Remove top heading only
    raw = re.sub(
        r"^\s*\d+\s+INDICATIONS?\s+AND\s+USAGE\s+",
        "",
        raw,
        flags=re.I,
    )

    # Split on subsection markers like 1.1, 1.2, 1.3
    parts = re.split(r"\s(?=\d+\.\d+\s)", raw)

    intro = parts[0].strip() if parts else ""
    subsections = parts[1:] if len(parts) > 1 else []

    out: List[str] = []

    # ---- Intro handling ----
    if intro:
        intro = _normalize(_clean_section_refs(intro))
        intro = intro.strip(" -–—*.,:;")

        if intro and intro.lower() not in {"is indicated", "indicated", "use"}:
            # If intro is long, split by sentence boundaries
            intro_parts = re.split(r"(?<=[.!?])\s+", intro)

            for part in intro_parts:
                part = _normalize(part).strip(" -–—*.,:;")
                if not part:
                    continue
                if len(part) < 12:
                    continue
                if not re.search(r"[a-zA-Z]", part):
                    continue
                out.append(part)

    # ---- Subsection handling ----
    for section in subsections:
        section = _normalize(section)
        if not section:
            continue

        m = re.match(
            r"^(?P<num>\d+\.\d+)\s+(?P<label>[A-Za-z'’\-\s]+?)\s+[A-Z0-9\-]+(?:\s+is)?\s+indicated for(?: the treatment of)?\s+(?P<body>.+)$",
            section,
            flags=re.I,
        )

        if m:
            label = _normalize(m.group("label")).rstrip(".")
            body = _normalize(_clean_section_refs(m.group("body"))).rstrip(".")
            bullet = f"{label}: {body}"
        else:
            bullet = _normalize(_clean_section_refs(section)).strip(" -–—*.,:;")

        if not bullet:
            continue
        if len(bullet) < 12:
            continue
        if not re.search(r"[a-zA-Z]", bullet):
            continue

        out.append(bullet)

    # ---- Dedupe ----
    cleaned: List[str] = []
    seen = set()

    def normalize_key(text: str) -> str:
        text = text.lower()
        text = re.sub(r"\b(is indicated for(?: the treatment of)?)\b", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" .,:;")
        return text

    for item in out:
        item = _normalize(item).strip()
        if not item:
            continue

        key = normalize_key(item)
        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        cleaned.append(item)

        if len(cleaned) >= max_items:
            break

    return cleaned


def _normalize_dosage(blocks: List[str], max_items: int = 18) -> List[str]:
    if not blocks:
        return []

    raw = " ".join(str(b) for b in blocks if b)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = _normalize(raw)
    raw = _clean_section_refs(raw)

    # Remove heading only
    raw = re.sub(
        r"^\s*\d+\s+DOSAGE\s+AND\s+ADMINISTRATION\s+",
        "",
        raw,
        flags=re.I,
    )

    # Split on major subsection markers before they get swallowed into bullets
    parts = re.split(
        r"(?=\b(?:Take orally|Assess|If a dose is missed|Recommended Dosage in|Recommended starting dosage|The recommended|Recommended dosage|Dosage range is|Adults|Pediatric Patients|Pediatric patients|Use the lowest effective dose)\b)",
        raw,
        flags=re.I,
    )

    out: List[str] = []

    for section in parts:
        section = _normalize(_clean_section_refs(section)).strip(" -–—*.,:;")
        if not section:
            continue
        if len(section) < 10:
            continue
        if not re.search(r"[a-zA-Z]", section):
            continue

        # Secondary split for common run-on dosage clauses
        subparts = re.split(
            r"(?=\bIf a dose is missed\b)"
            r"|(?=\bPatients requiring\b)"
            r"|(?=\bRecommended starting dosage\b)"
            r"|(?=\bDosage range is\b)"
            r"|(?=\bPediatric Patients\b)"
            r"|(?=\bPediatric patients\b)"
            r"|(?=\bAdults\b)"
            r"|(?=\bUse the lowest effective dose\b)",
            section,
            flags=re.I,
        )

        for sub in subparts:
            sub = _normalize(_clean_section_refs(sub)).strip(" -–—*.,:;")
            if not sub:
                continue
            if len(sub) < 10:
                continue
            if not re.search(r"[a-zA-Z]", sub):
                continue

            low = sub.lower()
            if low in {
                "recommended dosage in",
                "pediatric patients",
                "adults",
                "important dosage information",
                "recommended dosage for adult patients",
            }:
                continue

            # normalize leading capitalization
            sub = re.sub(r"^\brecommended\b", "Recommended", sub, flags=re.I)
            sub = re.sub(r"^\bdosage range\b", "Dosage range", sub, flags=re.I)
            sub = re.sub(r"^\bpediatric patients\b", "Pediatric patients", sub, flags=re.I)
            sub = re.sub(r"^\badults\b", "Adults", sub, flags=re.I)

            out.append(sub)

    cleaned: List[str] = []
    seen = set()

    for item in out:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(item)

        if len(cleaned) >= max_items:
            break

    return cleaned