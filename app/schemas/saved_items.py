from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Literal, List

from pydantic import BaseModel, ConfigDict


ContentType = Literal["news", "recall"]


class SaveItemRequest(BaseModel):
    content_type: ContentType
    source_item_id: int


class SavedItemResponse(BaseModel):
    id: int
    user_id: int
    content_type: str
    source_item_id: Optional[int] = None

    title: str
    summary: Optional[str] = None
    url: Optional[str] = None
    image_url: Optional[str] = None
    source_label: Optional[str] = None
    published_at: Optional[str] = None

    snapshot_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SavedItemListResponse(BaseModel):
    items: List[SavedItemResponse]
    count: int