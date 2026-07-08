# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Index,
    func,
)

from app.db import Base

class RequestCooldown(Base):
    __tablename__ = "request_cooldowns"

    id = Column(Integer, primary_key=True, index=True)

    action_key = Column(String(80), nullable=False, index=True)
    subject_type = Column(String(30), nullable=False, index=True)
    subject_key_hash = Column(String(128), nullable=False, index=True)

    last_attempt_at = Column(DateTime(timezone=True), nullable=False)

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

    __table_args__ = (
        UniqueConstraint(
            "action_key",
            "subject_type",
            "subject_key_hash",
            name="uq_request_cooldown_action_subject",
        ),
        Index(
            "ix_request_cooldowns_action_subject",
            "action_key",
            "subject_type",
            "subject_key_hash",
        ),
    )

class EmailRequestCooldown(Base):
    __tablename__ = "email_request_cooldowns"

    id = Column(Integer, primary_key=True, index=True)

    action_key = Column(String(80), nullable=False, index=True)
    email_hash = Column(String(255), nullable=False, index=True)

    last_requested_at = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "action_key",
            "email_hash",
            name="uq_email_request_cooldowns_action_email",
        ),
        Index(
            "ix_email_request_cooldowns_action_email",
            "action_key",
            "email_hash",
        ),
    )
