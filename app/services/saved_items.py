from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.models import UserSavedItem, RecallItem
from app.models import ExternalArticle  # replace if your news model name is different


def _make_json_safe(value):
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _make_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_make_json_safe(v) for v in value]
    return value


def _serialize_saved_item(row: UserSavedItem) -> Dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "content_type": row.content_type,
        "source_item_id": row.source_item_id,
        "title": row.title,
        "summary": row.summary,
        "url": row.url,
        "image_url": row.image_url,
        "source_label": row.source_label,
        "published_at": row.published_at,
        "snapshot_json": row.snapshot_json,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _build_recall_snapshot(recall: RecallItem) -> Dict[str, Any]:
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


def _build_article_snapshot(article: ExternalArticle) -> Dict[str, Any]:
    return {
        "id": article.id,
        "title": article.title,
        "summary": getattr(article, "summary", None),
        "url": getattr(article, "url", None),
        "image_url": getattr(article, "image_url", None),
        "source": getattr(article, "source", None),
        "published_at": _make_json_safe(getattr(article, "published_at", None)),
    }


def _find_existing_saved_item(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_id: int,
) -> Optional[UserSavedItem]:
    return (
        db.query(UserSavedItem)
        .filter(
            UserSavedItem.user_id == user_id,
            UserSavedItem.content_type == content_type,
            UserSavedItem.source_item_id == source_item_id,
        )
        .first()
    )


def save_item_for_user(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_id: int,
) -> Dict[str, Any]:
    existing = _find_existing_saved_item(
        db,
        user_id=user_id,
        content_type=content_type,
        source_item_id=source_item_id,
    )
    if existing:
        return _serialize_saved_item(existing)

    if content_type == "recall":
        source_row = db.get(RecallItem, source_item_id)
        if not source_row:
            raise ValueError("Recall not found")

        snapshot = _make_json_safe(_build_recall_snapshot(source_row))

        saved = UserSavedItem(
            user_id=user_id,
            content_type="recall",
            source_item_id=source_row.id,
            title=source_row.title,
            summary=source_row.reason,
            url=None,
            image_url=None,
            source_label=source_row.source,
            published_at=_make_json_safe(source_row.report_date or source_row.recall_date),
            snapshot_json=snapshot,
        )

    elif content_type == "news":
        source_row = db.get(ExternalArticle, source_item_id)
        if not source_row:
            raise ValueError("News article not found")

        snapshot = _make_json_safe(_build_article_snapshot(source_row))

        saved = UserSavedItem(
            user_id=user_id,
            content_type="news",
            source_item_id=source_row.id,
            title=source_row.title,
            summary=getattr(source_row, "summary", None),
            url=getattr(source_row, "url", None),
            image_url=getattr(source_row, "image_url", None),
            source_label=getattr(source_row, "source", None),
            published_at=_make_json_safe(getattr(source_row, "published_at", None)),
            snapshot_json=snapshot,
        )

    else:
        raise ValueError("Unsupported content_type")

    db.add(saved)
    db.commit()
    db.refresh(saved)

    return _serialize_saved_item(saved)


def list_saved_items_for_user(
    db: Session,
    *,
    user_id: int,
    content_type: Optional[str] = None,
    query: Optional[str] = None,
    sort: str = "newest",
    limit: int = 20,
    skip: int = 0,
) -> Dict[str, Any]:
    db_query = db.query(UserSavedItem).filter(
        UserSavedItem.user_id == user_id
    )

    if content_type:
        db_query = db_query.filter(
            UserSavedItem.content_type == content_type
        )

    if query and query.strip():
        like_query = f"%{query.strip()}%"

        db_query = db_query.filter(
            or_(
                UserSavedItem.title.ilike(like_query),
                UserSavedItem.summary.ilike(like_query),
                UserSavedItem.source_label.ilike(like_query),
            )
        )

    total = db_query.count()

    if sort == "oldest":
        db_query = db_query.order_by(
            UserSavedItem.published_at.asc().nullslast(),
            UserSavedItem.created_at.asc(),
            UserSavedItem.id.asc(),
        )

    elif sort == "title_asc":
        db_query = db_query.order_by(
            func.lower(UserSavedItem.title).asc().nullslast(),
            UserSavedItem.published_at.desc().nullslast(),
            UserSavedItem.created_at.desc(),
            UserSavedItem.id.desc(),
        )

    elif sort == "title_desc":
        db_query = db_query.order_by(
            func.lower(UserSavedItem.title).desc().nullslast(),
            UserSavedItem.published_at.desc().nullslast(),
            UserSavedItem.created_at.desc(),
            UserSavedItem.id.desc(),
        )

    else:
        db_query = db_query.order_by(
            UserSavedItem.published_at.desc().nullslast(),
            UserSavedItem.created_at.desc(),
            UserSavedItem.id.desc(),
        )

    items = db_query.offset(skip).limit(limit).all()

    return {
        "items": [_serialize_saved_item(item) for item in items],
        "count": len(items),
        "total": total,
        "limit": limit,
        "skip": skip,
        "sort": sort,
    }


def delete_saved_item_for_user(
    db: Session,
    *,
    user_id: int,
    saved_item_id: int,
) -> bool:
    row = (
        db.query(UserSavedItem)
        .filter(
            UserSavedItem.id == saved_item_id,
            UserSavedItem.user_id == user_id,
        )
        .first()
    )

    if not row:
        return False

    db.delete(row)
    db.commit()
    return True


def check_saved_item_for_user(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_id: int,
) -> Dict[str, Any]:
    row = _find_existing_saved_item(
        db,
        user_id=user_id,
        content_type=content_type,
        source_item_id=source_item_id,
    )
    return {
        "saved": row is not None,
        "saved_item_id": row.id if row else None,
    }

def check_bulk_saved_items_for_user(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_ids: list[int],
) -> dict:
    clean_ids = list({int(i) for i in source_item_ids if int(i) > 0})

    if not clean_ids:
        return {"items": []}

    rows = (
        db.query(UserSavedItem)
        .filter(
            UserSavedItem.user_id == user_id,
            UserSavedItem.content_type == content_type,
            UserSavedItem.source_item_id.in_(clean_ids),
        )
        .all()
    )

    row_map = {row.source_item_id: row for row in rows}

    return {
        "items": [
            {
                "source_item_id": item_id,
                "saved": item_id in row_map,
                "saved_item_id": row_map[item_id].id if item_id in row_map else None,
            }
            for item_id in clean_ids
        ]
    }