from __future__ import annotations

from typing import Any, Dict, List, Optional
from collections import Counter

from sqlalchemy.orm import Session

from app.models import ContentReaction, RecallItem, ExternalArticle


VALID_CONTENT_TYPES = {"news", "recall"}
VALID_REACTIONS = {"like", "helpful", "important", "concerned", "amazed"}


def _validate_content_type(content_type: str) -> None:
    if content_type not in VALID_CONTENT_TYPES:
        raise ValueError("Unsupported content_type")


def _validate_reaction_type(reaction_type: str) -> None:
    if reaction_type not in VALID_REACTIONS:
        raise ValueError("Unsupported reaction_type")


def _source_exists(db: Session, content_type: str, source_item_id: int) -> bool:
    if content_type == "news":
        return db.get(ExternalArticle, source_item_id) is not None

    if content_type == "recall":
        return db.get(RecallItem, source_item_id) is not None

    return False


def _get_existing_reaction(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_id: int,
) -> Optional[ContentReaction]:
    return (
        db.query(ContentReaction)
        .filter(
            ContentReaction.user_id == user_id,
            ContentReaction.content_type == content_type,
            ContentReaction.source_item_id == source_item_id,
        )
        .first()
    )


def get_reaction_summary(
    db: Session,
    *,
    content_type: str,
    source_item_id: int,
) -> Dict[str, Any]:
    _validate_content_type(content_type)

    rows = (
        db.query(ContentReaction)
        .filter(
            ContentReaction.content_type == content_type,
            ContentReaction.source_item_id == source_item_id,
        )
        .all()
    )

    counts = Counter(row.reaction_type for row in rows)

    user_reaction = _get_existing_reaction(
        db,
        content_type=content_type,
        source_item_id=source_item_id,
    )

    return {
        "content_type": content_type,
        "source_item_id": source_item_id,
        "user_reaction": user_reaction.reaction_type if user_reaction else None,
        "counts": {
            "like": counts.get("like", 0),
            "helpful": counts.get("helpful", 0),
            "important": counts.get("important", 0),
            "concerned": counts.get("concerned", 0),
            "amazed": counts.get("amazed", 0)
        },
    }


def toggle_reaction(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_id: int,
    reaction_type: str,
) -> Dict[str, Any]:
    _validate_content_type(content_type)
    _validate_reaction_type(reaction_type)

    if not _source_exists(db, content_type, source_item_id):
        raise ValueError("Source item not found")

    existing = _get_existing_reaction(
        db,
        user_id=user_id,
        content_type=content_type,
        source_item_id=source_item_id,
    )

    if existing and existing.reaction_type == reaction_type:
        db.delete(existing)
        db.commit()
    elif existing:
        existing.reaction_type = reaction_type
        db.commit()
        db.refresh(existing)
    else:
        reaction = ContentReaction(
            user_id=user_id,
            content_type=content_type,
            source_item_id=source_item_id,
            reaction_type=reaction_type,
        )
        db.add(reaction)
        db.commit()

    return get_reaction_summary(
        db,
        user_id=user_id,
        content_type=content_type,
        source_item_id=source_item_id,
    )


def remove_reaction(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_id: int,
) -> Dict[str, Any]:
    _validate_content_type(content_type)

    existing = _get_existing_reaction(
        db,
        user_id=user_id,
        content_type=content_type,
        source_item_id=source_item_id,
    )

    if existing:
        db.delete(existing)
        db.commit()

    return get_reaction_summary(
        db,
        user_id=user_id,
        content_type=content_type,
        source_item_id=source_item_id,
    )


def get_bulk_reaction_summaries(
    db: Session,
    *,
    user_id: int,
    content_type: str,
    source_item_ids: List[int],
) -> Dict[str, Any]:
    _validate_content_type(content_type)

    clean_ids = list({int(i) for i in source_item_ids if int(i) > 0})

    if not clean_ids:
        return {"items": []}

    rows = (
        db.query(ContentReaction)
        .filter(
            ContentReaction.content_type == content_type,
            ContentReaction.source_item_id.in_(clean_ids),
        )
        .all()
    )

    grouped: Dict[int, Counter] = {
        item_id: Counter() for item_id in clean_ids
    }

    user_reactions: Dict[int, Optional[str]] = {
        item_id: None for item_id in clean_ids
    }

    for row in rows:
        grouped[row.source_item_id][row.reaction_type] += 1

        if row.user_id == user_id:
            user_reactions[row.source_item_id] = row.reaction_type

    return {
        "items": [
            {
                "content_type": content_type,
                "source_item_id": item_id,
                "user_reaction": user_reactions.get(item_id),
                "counts": {
                    "like": grouped[item_id].get("like", 0),
                    "helpful": grouped[item_id].get("helpful", 0),
                    "important": grouped[item_id].get("important", 0),
                    "concerned": grouped[item_id].get("concerned", 0),
                    "amazed": grouped[item_id].get("amazed", 0),
                },
            }
            for item_id in clean_ids
        ]
    }