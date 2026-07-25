# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Text,
    Boolean,
    func,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
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
    usage_counters = relationship(
        "UserUsageCounter",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    feedback = relationship(
        "UserFeedback",
        back_populates="user",
        cascade="all, delete-orphan",
    )