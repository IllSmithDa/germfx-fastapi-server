# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    UniqueConstraint,
    DateTime,
    Date,
    Text,
    ForeignKey,
    CheckConstraint,
    Index,
    func,
)
from sqlalchemy.orm import relationship
from app.db import Base

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