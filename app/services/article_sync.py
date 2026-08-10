from __future__ import annotations

from datetime import datetime, timezone, timedelta
import os
from typing import Any
import requests
import xml.etree.ElementTree as ET
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app import models

ARTICLE_FEED_NAME = "general_health_articles"
ARTICLE_STALE_AFTER_HOURS = 12
MAX_ARTICLES = 500

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


MEDLINEPLUS_SEARCH_URL = "https://wsearch.nlm.nih.gov/ws/query"

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
NEWSDATA_BASE_URL = "https://newsdata.io/api/1/latest"


def fetch_general_article_payloads() -> list[dict[str, Any]]:
    if not NEWSDATA_API_KEY:
        raise RuntimeError("NEWSDATA_API_KEY is not configured")

    params = {
        "apikey": NEWSDATA_API_KEY,
        "language": "en",
        "category": "health",
        "q": "drug OR medication OR pharmaceutical OR FDA OR recall OR warning",
    }

    response = requests.get(NEWSDATA_BASE_URL, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()

    if data.get("status") != "success":
        raise RuntimeError(f"NewsData.io error: {data}")

    return data.get("results", [])


def articles_exist(db: Session) -> bool:
    count = db.execute(
        select(func.count()).select_from(models.ExternalArticle)
    ).scalar_one()
    return count > 0


def _parse_article_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def normalize_article_item(
    item: dict[str, Any],
    topic: str = "health_news",
    related_drug_name: str | None = None,
) -> dict[str, Any]:
    title = item.get("title") or "Article"
    summary = item.get("description")
    url = item.get("link")
    image_url = item.get("image_url")
    published_raw = item.get("pubDate")
    source_name = item.get("source_id") or "Unknown"

    return {
        "source": str(source_name),
        "topic": topic,
        "external_id": str(url or title),
        "title": str(title),
        "summary": summary,
        "url": url or str(title),
        "image_url": image_url,
        "published_at": _parse_article_date(published_raw),
        "related_drug_name": related_drug_name,
        "matched_display_name": related_drug_name,
        "raw_json": item,
    }
def _get_or_create_sync_state(db: Session, feed_name: str) -> models.ExternalFeedSync:
    sync = db.execute(
        select(models.ExternalFeedSync).where(models.ExternalFeedSync.feed_name == feed_name)
    ).scalars().first()

    if sync:
        return sync

    sync = models.ExternalFeedSync(
        feed_name=feed_name,
        status="never_run",
    )
    db.add(sync)
    db.flush()
    return sync



def _normalize_title(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def upsert_articles(db: Session, normalized_items: list[dict[str, Any]]) -> int:
    count = 0

    existing_articles = db.execute(
        select(models.ExternalArticle)
    ).scalars().all()

    articles_by_title = {
        _normalize_title(article.title): article
        for article in existing_articles
        if article.title
    }

    for item in normalized_items:
        existing = db.execute(
            select(models.ExternalArticle).where(
                models.ExternalArticle.source == item["source"],
                models.ExternalArticle.external_id == item["external_id"],
            )
        ).scalars().first()

        if not existing:
            existing = articles_by_title.get(_normalize_title(item["title"]))

        if existing:
            existing.topic = item["topic"]
            existing.title = item["title"]
            existing.summary = item["summary"]
            existing.url = item["url"]
            existing.image_url = item["image_url"]
            existing.published_at = item["published_at"]
            existing.related_drug_name = item["related_drug_name"]
            existing.matched_display_name = item["matched_display_name"]
            existing.raw_json = item["raw_json"]
            db.add(existing)
        else:
            article = models.ExternalArticle(**item)
            db.add(article)
            articles_by_title[_normalize_title(item["title"])] = article

        count += 1

    return count

def prune_old_articles(db: Session, keep: int = MAX_ARTICLES) -> int:
    total = db.execute(
        select(func.count()).select_from(models.ExternalArticle)
    ).scalar_one()

    overflow = total - keep
    if overflow <= 0:
        return 0

    oldest_ids = db.execute(
        select(models.ExternalArticle.id)
        .order_by(
            models.ExternalArticle.published_at.asc().nullsfirst(),
            models.ExternalArticle.created_at.asc(),
        )
        .limit(overflow)
    ).scalars().all()

    if not oldest_ids:
        return 0

    # Reactions are not snapshots and should not outlive their source article.
    # Saved items are intentionally left alone because they store their own
    # article snapshot data.
    db.execute(
        delete(models.ContentReaction).where(
            models.ContentReaction.content_type == "news",
            models.ContentReaction.source_item_id.in_(oldest_ids),
        )
    )

    db.execute(
        delete(models.ExternalArticle).where(
            models.ExternalArticle.id.in_(oldest_ids)
        )
    )

    return len(oldest_ids)

def sync_general_articles(db: Session) -> dict:
    sync = _get_or_create_sync_state(db, ARTICLE_FEED_NAME)
    sync.status = "running"
    sync.notes = None
    db.add(sync)
    db.commit()

    try:
        fetched_items = fetch_general_article_payloads()
        normalized = [
            normalize_article_item(item, topic="health_news")
            for item in fetched_items
        ]
        
        upserted = upsert_articles(db, normalized)
        deleted = prune_old_articles(db, keep=MAX_ARTICLES)

        sync.last_synced_at = _now_utc()
        sync.status = "success"
        sync.notes = f"Upserted {upserted} article records, pruned {deleted} old records"

        db.add(sync)
        db.commit()

        return {
            "feed_name": ARTICLE_FEED_NAME,
            "upserted": upserted,
        }

    except Exception as e:
        db.rollback()

        sync = _get_or_create_sync_state(db, ARTICLE_FEED_NAME)
        sync.last_synced_at = _now_utc()
        sync.status = "failed"
        sync.notes = str(e)
        db.add(sync)
        db.commit()
        raise


def ensure_articles_fresh(db: Session) -> dict:
    sync = _get_or_create_sync_state(db, ARTICLE_FEED_NAME)
    db.commit()

    is_empty = not articles_exist(db)
    is_stale = (
        not sync.last_synced_at
        or sync.last_synced_at < (_now_utc() - timedelta(hours=ARTICLE_STALE_AFTER_HOURS))
    )

    if is_empty or is_stale:
        return sync_general_articles(db)

    return {
        "feed_name": ARTICLE_FEED_NAME,
        "skipped": True,
        "reason": "fresh",
        "last_synced_at": sync.last_synced_at,
    }