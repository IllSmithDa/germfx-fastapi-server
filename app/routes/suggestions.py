# app/routes/suggestions.py
from fastapi import APIRouter, Query
from typing import List
from app.data.medications import medications_brands

router = APIRouter()

@router.get("/medications", response_model=List[str])
def medication_suggestions(
    q: str = Query(..., min_length=1, alias="query"),  # accepts ?q= or ?query=
    limit: int = Query(10, ge=1, le=50),
) -> List[str]:
    q_low = q.strip().lower()
    if not q_low:
        return []
    # prefix first, then substring
    prefix = [b for b in medications_brands if b.lower().startswith(q_low)]
    contains = [b for b in medications_brands if q_low in b.lower() and b not in prefix]
    return (prefix + contains)[:limit]