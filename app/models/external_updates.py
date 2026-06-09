from __future__ import annotations

from datetime import datetime
from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


class ExternalDrugUpdate(Base):
    __tablename__ = "external_drug_updates"

    id = Column(Integer, primary_key=True, index=True)

    # source metadata
    source = Column(String(50), nullable=False, index=True)         # e.g. "FDA"
    source_type = Column(String(50), nullable=False, index=True)    # e.g. "recall", "label_update"
    external_id = Column(Text, nullable=False)

    # normalized display fields
    title = Column(Text, nullable=False)
    drug_name = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    severity = Column(String(20), nullable=True, index=True)        # info | low | medium | high
    classification = Column(String(50), nullable=True)              # e.g. Class I / II / III
    status = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)

    # raw upstream payload for debugging / future fields
    raw_json = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("source", "source_type", "external_id", name="uq_external_drug_update_source_extid"),
    )


class ExternalFeedSync(Base):
    __tablename__ = "external_feed_syncs"

    id = Column(Integer, primary_key=True, index=True)

    feed_name = Column(String(100), nullable=False, unique=True, index=True)   # e.g. "openfda_drug_enforcement"
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_successful_remote_timestamp = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), nullable=True)   # success | failed | running
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)