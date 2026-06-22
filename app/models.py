# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Date,
    Text,
    Boolean,
    ForeignKey,
    CheckConstraint,
    Index,
    func,
)
from datetime import datetime, timezone
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from app.db import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("username", name="uq_users_username"),
        UniqueConstraint("email_hash", name="uq_users_email_hash"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), nullable=False, index=True)
    email_hash = Column(String(64), nullable=False, index=True)    
    email_enc = Column(String(512), nullable=True)  # <-- MUST exist
    password_hash = Column(String(255), nullable=False)
    is_email_verified = Column(Boolean, nullable=False, server_default="false")
    email_verification_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    symptom_logs = relationship(
        "SymptomLog", back_populates="user", cascade="all, delete-orphan"
    )
        # ✨ ADD THIS:
    user_medications = relationship(
        "UserMedication", back_populates="user", cascade="all, delete-orphan"
    )
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_active = Column(Boolean, nullable=False, server_default="true")
    # account_status can be "active", "deactivated", "suspended"
    account_status = Column(String(20), nullable=False, server_default="active")
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    suspended_at = Column(DateTime(timezone=True), nullable=True)
    suspension_reason = Column(Text, nullable=True)
    role = Column(String(20), nullable=False, server_default="user", index=True)
    settings = relationship(
        "UserSettings",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    subscription = relationship(
        "UserSubscription",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
#   
# Optional normalized catalog of symptom terms (e.g., “nausea”, “headache”)
class Symptom(Base):
    __tablename__ = "symptoms"
    __table_args__ = (UniqueConstraint("term", name="uq_symptoms_term"),)

    id = Column(Integer, primary_key=True)
    term = Column(String(100), nullable=False, index=True)  # lowercase preferred
    definition = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # backrefs
    logs = relationship("SymptomLog", back_populates="symptom")

    # User-reported symptom entries (the actual logs)
class SymptomLog(Base):
    __tablename__ = "symptom_logs"
    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 10", name="ck_symptom_logs_severity_range"),
        Index("ix_symptom_logs_user_date", "user_id", "date"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # replace old medication FK
    user_medication_id = Column(
        Integer,
        ForeignKey("user_medications.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    symptom_id = Column(Integer, ForeignKey("symptoms.id", ondelete="SET NULL"), nullable=True, index=True)

    # always store the actual symptom label
    symptom_text = Column(String(100), nullable=False)

    date = Column(Date, nullable=False, index=True)

    details = Column(Text, nullable=True)
    severity = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="symptom_logs")
    user_medication = relationship("UserMedication")
    symptom = relationship("Symptom", back_populates="logs")
    possible_trigger = Column(String(120), nullable=True)
    management_strategy = Column(Text, nullable=True)

class UserMedication(Base):
    __tablename__ = "user_medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # ✅ canonical drug identity for navigation + dedupe
    drug_index_id = Column(Integer, ForeignKey("drug_index.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_index = relationship("DrugIndex")  # or back_populates if you add it on DrugIndex


    drug_detail_id = Column(Integer, ForeignKey("drug_details.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_detail = relationship("DrugDetail", back_populates="user_medications")

    name = Column(String(100))
    dosage = Column(String(100))
    route = Column(String(50))
    frequency = Column(String(100))
    start_date = Column(Date)
    end_date = Column(Date)
    is_active = Column(Boolean, nullable=False, server_default="true")
    notes = Column(Text)
    nickname = Column(String(100))  # optional user-defined name for this medication
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="user_medications")
    symptom_logs = relationship("SymptomLog", back_populates="user_medication")
    tracking_purpose = Column(String(32))

class DrugIndex(Base):
    __tablename__ = "drug_index"
    __table_args__ = (
        UniqueConstraint("normalized_name", "kind", name="uq_drug_index_name_kind"),
    )
    id = Column(Integer, primary_key=True)
    name = Column(String(300), nullable=False)
    normalized_name = Column(String(300), nullable=False, index=True)
    kind = Column(String(20), nullable=False)  # "brand" | "generic" | "substance"
    manufacturer = Column(String(300), nullable=True)
    source = Column(String(40), nullable=False, default="openfda")
    # data from OpenFDA JSON blob
    ndc_codes = Column(ARRAY(String), nullable=True)
    upc_codes = Column(ARRAY(String), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now(), nullable=False)
    latest_detail_id = Column(Integer, ForeignKey("drug_details.id", ondelete="SET NULL"), nullable=True)
    latest_detail = relationship(
        "DrugDetail",
        foreign_keys=[latest_detail_id],
        uselist=False,
    )

    # collection of all details history (index <- details)
    details = relationship(
        "DrugDetail",
        back_populates="drug_index",
        foreign_keys="DrugDetail.drug_index_id",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    

class DrugDetail(Base):
    __tablename__ = "drug_details"
    __table_args__ = (
        UniqueConstraint("drug_index_id", "effective_time", "source", name="uq_drugindex_eff_source"),
        Index("ix_drug_detail_norm_name", "normalized_name"),
        Index("ix_drug_detail_eff_time", "effective_time"),
    )

    id = Column(Integer, primary_key=True)

    drug_index_id = Column(Integer, ForeignKey("drug_index.id", ondelete="CASCADE"), nullable=False, index=True)
    drug_index = relationship(
        "DrugIndex",
        back_populates="details",
        foreign_keys=[drug_index_id],
    )

    name = Column(String(300), nullable=False)
    normalized_name = Column(String(300), nullable=False, index=True)

    symptoms_table = Column(ARRAY(Text), nullable=True)

    brand_names = Column(ARRAY(String))
    generic_names = Column(ARRAY(String))
    manufacturer_names = Column(ARRAY(String))
    route = Column(ARRAY(String))
    product_type = Column(ARRAY(String))

    purpose_or_indications = Column(ARRAY(Text))
    dosage_and_administration = Column(ARRAY(Text))
    adverse_reactions = Column(ARRAY(Text))
    drug_interactions = Column(ARRAY(Text))
    boxed_warning = Column(ARRAY(Text))

    warnings_key = Column(JSONB)
    warnings_raw = Column(ARRAY(Text))
    warnings_simple = Column(ARRAY(Text))
    side_effects = Column(ARRAY(String))
    stop_using_warnings = Column(ARRAY(String))

    upc_codes = Column(ARRAY(String), nullable=True)
    package_ndc = Column(ARRAY(String), nullable=True)
    unii = Column(ARRAY(String), nullable=True)
    rxcui = Column(ARRAY(String), nullable=True)
    
    openfda_meta = Column(JSONB)
    source = Column(String(80), nullable=False, default="openfda.label")
    query_used = Column(String(300))

    effective_time = Column(Date, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user_medications = relationship("UserMedication", back_populates="drug_detail", cascade="all, delete-orphan")
    
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
class UserSettings(Base):
    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    theme = Column(String(20), nullable=False, server_default="system")
    default_report_range = Column(String(20), nullable=False, server_default="30d")
    top_symptom_limit = Column(Integer, nullable=False, server_default="10")

    remember_last_medication = Column(Boolean, nullable=False, server_default="false")
    recent_suggestions_first = Column(Boolean, nullable=False, server_default="true")
    
    default_recall_state = Column(String(10), nullable=False, server_default="all")
    default_recall_type = Column(String(20), nullable=False, server_default="all")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="settings")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "provider_subscription_id",
            name="uq_user_subscription_provider_subscription",
        ),
        Index("ix_user_subscriptions_user_provider", "user_id", "provider"),
        Index("ix_user_subscriptions_provider_customer", "provider", "provider_customer_id"),
    )

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # App entitlement fields
    plan = Column(String(30), nullable=False, server_default="free", index=True)
    status = Column(String(30), nullable=False, server_default="free", index=True)

    # Payment provider source
    provider = Column(String(30), nullable=False, server_default="manual", index=True)

    provider_customer_id = Column(String(255), nullable=True)
    provider_subscription_id = Column(String(255), nullable=True)
    provider_transaction_id = Column(String(255), nullable=True)

    # Subscription window
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)

    cancel_at_period_end = Column(Boolean, nullable=False, server_default="false")

    # Useful for manual grants/testing
    granted_by_admin = Column(Boolean, nullable=False, server_default="false")
    notes = Column(Text, nullable=True)

    # Store provider webhook/session payload fragments when useful
    provider_raw = Column(JSONB, nullable=True)

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

    user = relationship(
        "User",
        back_populates="subscription",
    )

class BillingWebhookEvent(Base):
    __tablename__ = "billing_webhook_events"

    id = Column(Integer, primary_key=True, index=True)

    provider = Column(String(30), nullable=False, index=True)
    event_id = Column(String(255), nullable=False)
    event_type = Column(String(100), nullable=False, index=True)

    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    raw_json = Column(JSONB, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "event_id",
            name="uq_billing_webhook_provider_event",
        ),
    )