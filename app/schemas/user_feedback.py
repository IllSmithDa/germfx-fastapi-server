from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


FeedbackCategory = Literal[
    "general",
    "bug",
    "feature_request",
    "drug_data",
    "account",
    "reports",
    "ui_ux",
    "performance",
    "other",
]

FeedbackReviewStatus = Literal[
    "unread",
    "read",
    "addressed",
]

FeedbackSort = Literal[
    "created_desc",
    "created_asc",
    "updated_desc",
    "rating_desc",
    "rating_asc",
]


class FeedbackCreateRequest(BaseModel):
    category: FeedbackCategory = "general"
    rating: int | None = Field(default=None, ge=1, le=5)
    message: str = Field(min_length=3, max_length=5000)
    page_url: str | None = Field(default=None, max_length=500)


class FeedbackUpdateRequest(BaseModel):
    category: FeedbackCategory | None = None
    rating: int | None = Field(default=None, ge=1, le=5)
    message: str | None = Field(default=None, min_length=3, max_length=5000)
    page_url: str | None = Field(default=None, max_length=500)


class AdminFeedbackStatusUpdateRequest(BaseModel):
    status: FeedbackReviewStatus


class FeedbackOut(BaseModel):
    id: int
    category: str
    rating: int | None = None
    message: str
    page_url: str | None = None
    status: str = "unread"
    created_at: str | None = None
    updated_at: str | None = None


class AdminFeedbackOut(FeedbackOut):
    user_id: int
    username: str | None = None
    user_agent: str | None = None


class AdminFeedbackListOut(BaseModel):
    items: list[AdminFeedbackOut]
    total: int
    page: int
    page_size: int
    has_next: bool


class FeedbackDeleteOut(BaseModel):
    deleted: bool
    feedback_id: int
