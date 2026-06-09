from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class ExternalDrugUpdateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_type: str
    external_id: str
    title: str
    drug_name: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    severity: Optional[str] = None
    classification: Optional[str] = None
    status: Optional[str] = None
    source_url: Optional[str] = None


class ExternalDrugUpdateListOut(BaseModel):
    items: list[ExternalDrugUpdateOut]
    meta: dict[str, Any]


class ExternalFeedSyncOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    feed_name: str
    last_synced_at: Optional[datetime] = None
    last_successful_remote_timestamp: Optional[datetime] = None
    status: Optional[str] = None
    notes: Optional[str] = None

# app/schemas/external_updates.p
class ExternalDrugUpdateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_type: str
    external_id: str

    technical_title: str
    technical_drug_name: Optional[str] = None

    display_name: Optional[str] = None
    official_name: Optional[str] = None
    plain_summary: Optional[str] = None

    title: str
    drug_name: Optional[str] = None
    summary: Optional[str] = None
    published_at: Optional[datetime] = None
    severity: Optional[str] = None
    classification: Optional[str] = None
    status: Optional[str] = None
    source_url: Optional[str] = None
    dailymed_url: Optional[str] = None
    medlineplus_url: Optional[str] = None


class ExternalArticleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    topic: Optional[str] = None
    external_id: str
    title: str
    summary: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    published_at: Optional[datetime] = None
    related_drug_name: Optional[str] = None
    matched_display_name: Optional[str] = None


class ExternalContentOut(BaseModel):
    items: list[ExternalDrugUpdateOut]
    articles: list[ExternalArticleOut]
    meta: dict[str, Any]