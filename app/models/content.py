# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Text,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db import Base


class ExternalDrugUpdate(Base):
    __tablename__ = "external_drug_updates"

    id = Column(Integer, primary_key=True, index=True)

    source = Column(String(50), nullable=False, index=True)          # FDA
    source_type = Column(String(50), nullable=False, index=True)     # recall | label_update | approval
    external_id = Column(Text, nullable=False)

    # raw / technical source fields
    technical_title = Column(Text, nullable=False)
    technical_drug_name = Column(Text, nullable=True)

    # user-facing fields
    display_name = Column(Text, nullable=True, index=True)
    official_name = Column(Text, nullable=True, index=True)
    plain_summary = Column(Text, nullable=True)

    # generic normalized fields
    title = Column(Text, nullable=False)
    drug_name = Column(Text, nullable=True, index=True)
    summary = Column(Text, nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True, index=True)
    severity = Column(String(20), nullable=True, index=True)
    classification = Column(String(50), nullable=True)
    status = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)

    # enrichment links
    dailymed_url = Column(Text, nullable=True)
    medlineplus_url = Column(Text, nullable=True)

    raw_json = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_type",
            "external_id",
            name="uq_external_drug_update_source_extid",
        ),
    )


class ExternalFeedSync(Base):
    __tablename__ = "external_feed_syncs"

    id = Column(Integer, primary_key=True, index=True)

    feed_name = Column(String(100), nullable=False, unique=True, index=True)   # e.g. "openfda_drug_enforcement"
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_successful_remote_timestamp = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), nullable=True)   # success | failed | running
    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

class ExternalArticle(Base):
    __tablename__ = "external_articles"

    id = Column(Integer, primary_key=True, index=True)

    source = Column(String(100), nullable=False, index=True)         # e.g. GNews, FDA, etc.
    topic = Column(String(100), nullable=True, index=True)           # drug_safety, fda_news, health_news
    external_id = Column(Text, nullable=False)

    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)

    published_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # optional matching fields
    related_drug_name = Column(Text, nullable=True, index=True)
    matched_display_name = Column(Text, nullable=True, index=True)

    raw_json = Column(JSONB, nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source",
            "external_id",
            name="uq_external_article_source_extid",
        ),
    )

class RecallItem(Base):
    __tablename__ = "recall_items"

    id = Column(Integer, primary_key=True, index=True)

    source = Column(String(20), nullable=False, index=True)          # food | drug
    product_type = Column(String(30), nullable=False, index=True)    # food | medication

    classification = Column(String(20), nullable=True, index=True)   # Class I/II/III
    status = Column(String(50), nullable=True, index=True)

    recall_date = Column(String(20), nullable=True, index=True)      # YYYYMMDD from FDA
    report_date = Column(String(20), nullable=True, index=True)      # YYYYMMDD from FDA

    title = Column(Text, nullable=False)
    reason = Column(Text, nullable=True)
    company = Column(String(255), nullable=True, index=True)
    distribution = Column(Text, nullable=True)

    recall_number = Column(String(100), nullable=True, index=True)
    event_id = Column(String(100), nullable=True, index=True)

    raw_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("source", "recall_number", name="uq_recall_source_number"),
        Index("ix_recall_items_source_recall_date", "source", "recall_date"),
    )


class UserSavedItem(Base):
    __tablename__ = "user_saved_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    content_type = Column(String(20), nullable=False, index=True)   # "news" | "recall"
    source_item_id = Column(Integer, nullable=True, index=True)

    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=True)
    url = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)

    source_label = Column(String(100), nullable=True)
    published_at = Column(String(50), nullable=True)

    snapshot_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "content_type",
            "source_item_id",
            name="uq_user_saved_source_item",
        ),
        Index("ix_user_saved_items_user_content", "user_id", "content_type"),
    )


class ContentReaction(Base):
    __tablename__ = "content_reactions"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    content_type = Column(String(20), nullable=False, index=True)  # "news" | "recall"
    source_item_id = Column(Integer, nullable=False, index=True)

    reaction_type = Column(String(20), nullable=False)  # "like" | "helpful" | "important" | "concerned"

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "content_type",
            "source_item_id",
            name="uq_user_content_reaction",
        ),
        Index("ix_content_reactions_content", "content_type", "source_item_id"),
    )