# app/models.py
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Date,
    Text,
    Boolean,
    ForeignKey,
    func,
)
from sqlalchemy.orm import relationship
from app.db import Base



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
