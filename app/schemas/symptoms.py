from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, List
from datetime import date, datetime

# Briefs for nested response
class SymptomTermBrief(BaseModel):
    id: int
    term: str
    class Config:
        from_attributes = True

# Create payload (single entry)
class SymptomLogCreate(BaseModel):
    symptom_text: str = Field(..., min_length=2, max_length=100)
    date: date
    details: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=10)
    user_medication_id: Optional[int] = Field(None, ge=1)
    symptom_id: Optional[int] = Field(None, ge=1)
    possible_trigger: Optional[str] = None
    management_strategy: Optional[str] = None

    # helpful guard: if severity is provided, enforce range early
    @field_validator("severity")
    @classmethod
    def _check_severity(cls, v):
        return v

# Response shape
class UserMedicationBrief(BaseModel):
    id: int
    name: Optional[str] = None
    nickname: Optional[str] = None

    class Config:
        from_attributes = True


class SymptomLogOut(BaseModel):
    id: int
    user_id: int
    date: date
    symptom_text: str
    details: Optional[str] = None
    severity: Optional[int] = None

    # FK field
    user_medication_id: Optional[int] = None

    # relationship object
    user_medication: Optional[UserMedicationBrief] = None

    symptom: Optional[SymptomTermBrief] = None

    created_at: datetime
    possible_trigger: Optional[str] = None
    management_strategy: Optional[str] = None
    
    class Config:
        from_attributes = True
# List wrapper
class SymptomLogList(BaseModel):
    items: List[SymptomLogOut]
    total: int

class SymptomLogUpdate(BaseModel):
    date: date
    symptom_text: Optional[str] = Field(None, max_length=100)
    details: Optional[str] = None
    severity: Optional[int] = Field(None, ge=1, le=10)
    user_medication_id: Optional[int] = Field(None, ge=1)
    symptom_id: Optional[int] = None
    possible_trigger: Optional[str] = None
    management_strategy: Optional[str] = None