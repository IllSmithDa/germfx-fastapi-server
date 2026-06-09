from pydantic import BaseModel, Field
from typing import List, Annotated, Optional, List
from datetime import date, datetime
from app.schemas.drug_index import DrugIndexBrief, DrugIndexRef
class UserMedicationListItem(BaseModel):
    id: int
    user_id: int
    name: Optional[str] = None
    dosage: Optional[str] = None
    route: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: bool
    notes: Optional[str] = None
    nickname: Optional[str] = None
    drug_index_id: int
    drug_detail_id: int
    created_at: datetime
    tracking_purpose: Optional[str] = None
    class Config:
        from_attributes = True

class UserMedicationList(BaseModel):
    items: List[UserMedicationListItem]
    total: int

class UserMedicationCreate(BaseModel):
    drug_detail_id: int = Field(..., ge=1)
    drug_index_id: int = Field(..., ge=1)
    name: Optional[str] = Field(None, max_length=100)
    dosage: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=50)
    frequency: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = True
    notes: Optional[str] = None
    nickname: Optional[str] = None
    tracking_purpose: Optional[str] = None

class UserMedicationOut(BaseModel):
    id: int
    user_id: int
    name: Optional[str]
    dosage: Optional[str]
    route: Optional[str]
    frequency: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    is_active: bool
    notes: Optional[str]
    nickname: Optional[str]
    created_at: datetime
    drug_index_id: int
    drug_detail_id: int
    tracking_purpose: Optional[str]
    class Config:
        from_attributes = True


class UserMedicationContainsOut(BaseModel):
    added: bool
    user_medication_id: int | None = None

class UserMedicationUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    dosage: Optional[str] = Field(None, max_length=100)
    route: Optional[str] = Field(None, max_length=50)
    frequency: Optional[str] = Field(None, max_length=100)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    nickname: Optional[str] = None
    tracking_purpose: Optional[str] = None