# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Text,
    Boolean,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import JSONB
from app.db import Base

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
