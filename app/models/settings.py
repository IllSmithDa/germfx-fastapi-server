# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from app.db import Base

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
