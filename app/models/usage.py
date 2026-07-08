# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from app.db import Base


class UsageLimit(Base):
    __tablename__ = "usage_limits"

    id = Column(Integer, primary_key=True, index=True)

    feature_key = Column(String(80), unique=True, nullable=False)
    free_limit = Column(Integer, nullable=False, default=5)

    description = Column(String(255), nullable=True)

    updated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class UserUsageCounter(Base):
    __tablename__ = "user_usage_counters"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    feature_key = Column(String(80), nullable=False, index=True)

    used_count = Column(Integer, nullable=False, server_default="0")

    last_used_at = Column(DateTime(timezone=True), nullable=True)

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

    user = relationship("User", back_populates="usage_counters")

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "feature_key",
            name="uq_user_usage_counter_user_feature",
        ),
        Index("ix_user_usage_counters_user_feature", "user_id", "feature_key"),
    )
