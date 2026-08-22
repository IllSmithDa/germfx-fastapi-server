# app/routes/content_detail.py

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import models
from app.db import get_db

router = APIRouter(tags=["content-detail"])


def serialize_article(article: models.ExternalArticle) -> dict:
    raw = article.raw_json if isinstance(article.raw_json, dict) else {}

    # Prefer the normalized columns used by the rest of GermFx, but keep
    # the original NewsData payload as a fallback for older stored rows.
    summary = article.summary or raw.get("description")
    image_url = article.image_url or raw.get("image_url")

    return {
        "id": article.id,
        "source": article.source,
        "topic": article.topic,
        "external_id": article.external_id,
        "title": article.title,
        "summary": summary,
        # Alias retained for detail-page semantics / future callers.
        "description": summary,
        "url": article.url,
        "image_url": image_url,
        "published_at": article.published_at,
        "related_drug_name": article.related_drug_name,
        "matched_display_name": article.matched_display_name,
    }


def serialize_recall(recall: models.RecallItem) -> dict:
    return {
        "id": recall.id,
        "source": recall.source,
        "product_type": recall.product_type,
        "classification": recall.classification,
        "status": recall.status,
        "recall_date": recall.recall_date,
        "report_date": recall.report_date,
        "title": recall.title,
        "reason": recall.reason,
        "company": recall.company,
        "distribution": recall.distribution,
        "recall_number": recall.recall_number,
        "event_id": recall.event_id,
    }


@router.get("/item/{content_type}/{content_id}")
def get_content_by_id(
    content_type: str,
    content_id: int,
    db: Session = Depends(get_db),
):
    """
    Retrieve one stored News article or Recall item by its database ID.

    Examples:
        GET /api/content/item/news/123
        GET /api/content/item/recall/456

    This endpoint intentionally reads from the local database only. It does
    not trigger article or recall synchronization because a detail-page lookup
    should be fast and deterministic once the item ID is known.
    """
    normalized_type = content_type.strip().lower()

    if normalized_type == "news":
        article = db.get(models.ExternalArticle, content_id)

        if article is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "News article not found.",
                    "code": "CONTENT_NOT_FOUND",
                    "content_type": "news",
                    "content_id": content_id,
                },
            )

        return {
            "content_type": "news",
            "item": serialize_article(article),
        }

    if normalized_type == "recall":
        recall = db.get(models.RecallItem, content_id)

        if recall is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "message": "Recall item not found.",
                    "code": "CONTENT_NOT_FOUND",
                    "content_type": "recall",
                    "content_id": content_id,
                },
            )

        return {
            "content_type": "recall",
            "item": serialize_recall(recall),
        }

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "message": "Unsupported content type. Use 'news' or 'recall'.",
            "code": "INVALID_CONTENT_TYPE",
            "content_type": content_type,
        },
    )