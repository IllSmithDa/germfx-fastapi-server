from __future__ import annotations

from app.services.articles import sync_articles_for_date
from app.services.article_sync import ensure_articles_fresh
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session

from app import models
from app.core.auth import get_authenticated_user
from app.db import get_db

from datetime import date as date_cls
router = APIRouter(tags=["articles"])

@router.get("")
def get_articles(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=20),
    query: str | None = Query(None),
    sort: str = Query("latest"),
    db: Session = Depends(get_db),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 20)
    offset = (page - 1) * page_size

    sync_warning = None
    try:
        ensure_articles_fresh(db)
    except Exception as e:
        print(f"Error occurred while ensuring articles are fresh: {e}")
        sync_warning = str(e)

    reaction_count = func.count(models.ContentReaction.id).label("reaction_count")

    base_query = (
        select(models.ExternalArticle, reaction_count)
        .outerjoin(
            models.ContentReaction,
            (models.ContentReaction.content_type == "news")
            & (models.ContentReaction.source_item_id == models.ExternalArticle.id),
        )
        .group_by(models.ExternalArticle.id)
    )

    count_query = select(func.count()).select_from(models.ExternalArticle)

    if query and query.strip():
        like_query = f"%{query.strip()}%"

        search_filter = or_(
            models.ExternalArticle.title.ilike(like_query),
            models.ExternalArticle.summary.ilike(like_query),
            models.ExternalArticle.source.ilike(like_query),
            models.ExternalArticle.topic.ilike(like_query),
            models.ExternalArticle.related_drug_name.ilike(like_query),
            models.ExternalArticle.matched_display_name.ilike(like_query),
        )

        base_query = base_query.where(search_filter)
        count_query = count_query.where(search_filter)

    total = db.execute(count_query).scalar_one()

    if sort == "popular":
        base_query = base_query.order_by(
            reaction_count.desc(),
            models.ExternalArticle.published_at.desc().nullslast(),
            models.ExternalArticle.id.desc(),
        )
    elif sort == "oldest":
        base_query = base_query.order_by(
            models.ExternalArticle.published_at.asc().nullsfirst(),
            models.ExternalArticle.id.asc(),
        )
    else:
        sort = "latest"
        base_query = base_query.order_by(
            models.ExternalArticle.published_at.desc().nullslast(),
            models.ExternalArticle.id.desc(),
        )

    rows = db.execute(
        base_query.offset(offset).limit(page_size)
    ).all()

    articles = []
    for article, count in rows:
        item = {
            "id": article.id,
            "source": article.source,
            "topic": article.topic,
            "external_id": article.external_id,
            "title": article.title,
            "summary": article.summary,
            "url": article.url,
            "image_url": article.image_url,
            "published_at": article.published_at,
            "related_drug_name": article.related_drug_name,
            "matched_display_name": article.matched_display_name,
            "reaction_count": int(count or 0),
        }
        articles.append(item)

    total_pages = (total + page_size - 1) // page_size

    return {
        "items": articles,
        "count": len(articles),
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "sort": sort,
        "meta": {
            "message": (
                "Showing stored articles. Live article sync could not be refreshed."
                if sync_warning else None
            )
        },
    }

@router.post("/fill-by-date")
def fill_articles_by_date(
    # Date format: YYYY-MM-DD
    # Example:
    #   /api/content/articles/fill-by-date?date=2026-04-01
    date: date_cls = Query(
        ...,
        description="Date to fetch articles for, in YYYY-MM-DD format. Example: /api/content/articles/fill-by-date?date=2026-04-01",
    ),
    db: Session = Depends(get_db),
):
    """
    Temporary bootstrap route used to manually add stored articles
    for one specific date.

    Pass the date as a query param in YYYY-MM-DD format:
    /api/content/articles/fill-by-date?date=2026-04-01
    """
    try:
        result = sync_articles_for_date(db, date)
        return {
            "message": "Manual article fill completed.",
            **result,
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Manual article fill failed: {e}",
        )

        