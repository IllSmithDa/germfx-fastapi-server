from typing import List, List
from pydantic import BaseModel

class MedicationCreate(BaseModel):
    name: str
    dosage: str
    route: str
    side_effects: List[str]

class MedicationOut(MedicationCreate):
    id: int

    class Config:
        orm_mode = True

class MedicationNameBrief(BaseModel):
    id: int
    name: str
    class Config:
        from_attributes = True
