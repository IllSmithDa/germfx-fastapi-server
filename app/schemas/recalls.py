from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class RecallItemSchema(BaseModel):
    id: int
    source: str
    product_type: str

    classification: Optional[str] = None
    status: Optional[str] = None

    recall_date: Optional[str] = None
    report_date: Optional[str] = None

    title: str
    reason: Optional[str] = None
    company: Optional[str] = None
    distribution: Optional[str] = None

    recall_number: Optional[str] = None
    event_id: Optional[str] = None

    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RecallListResponse(BaseModel):
    items: List[RecallItemSchema]
    count: int
    total: int
    limit: int
    skip: int


class RecallSyncResponse(BaseModel):
    sync_date: str
    food_fetched: int
    drug_fetched: int
    inserted: int
    trimmed: int
    total_after: int


class RecallFiltersSchema(BaseModel):
    source: Optional[str] = None
    limit: int
    skip: int
    sync_if_needed: bool = True


class RecallSourceMetaSchema(BaseModel):
    disclaimer: Optional[str] = None
    terms: Optional[str] = None
    license: Optional[str] = None
    last_updated: Optional[str] = None
    results: Optional[Dict[str, Any]] = None

# app/schemas/reports.py
class SymptomContextReportItem(BaseModel):
    symptom_text: str
    possible_triggers: list[str] = []
    management_strategies: list[str] = []