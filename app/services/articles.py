from datetime import date as date_cls, datetime, timezone
from typing import Any
import os
from sqlalchemy.orm import Session
import requests

from app.services.article_sync import normalize_article_item, upsert_articles

# Example only:
# Replace these with your actual provider env vars / URL
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY")
NEWSDATA_BASE_URL = "https://newsdata.io/api/1/latest"


def fetch_article_payloads_for_date(target_date: date_cls) -> list[dict[str, Any]]:
    """
    Fetch up to the provider's default article batch for one specific day.
    Expected date format coming into this function: YYYY-MM-DD
    """
    day_str = target_date.isoformat()

    params = {
        "apikey": NEWSDATA_API_KEY,
        "language": "en",
        "category": "health",
        "q": "drug OR medication OR pharmaceutical OR FDA OR recall OR warning",
        "from_date": day_str,
        "to_date": day_str,
    }

    response = requests.get(NEWSDATA_BASE_URL, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    if data.get("status") != "success":
        raise RuntimeError(f"News provider error: {data}")

    return data.get("results", [])


def sync_articles_for_date(db: Session, target_date: date_cls) -> dict[str, Any]:
    """
    Manual bootstrap sync for a specific date.
    This route intentionally does NOT prune/delete any rows.
    """
    fetched_items = fetch_article_payloads_for_date(target_date)

    normalized = [
        normalize_article_item(item, topic="health_news")
        for item in fetched_items
    ]

    upserted = upsert_articles(db, normalized)
    db.commit()

    return {
        "date": target_date.isoformat(),
        "fetched": len(fetched_items),
        "upserted": upserted,
        "deleted": 0,
    }