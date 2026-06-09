from pydantic import BaseModel
from typing import List, Annotated, Optional, List
from datetime import date, datetime

class DrugIndexBrief(BaseModel):
    id: int
    name: str
    generic_name: Optional[str] = None
    strength: Optional[str] = None
    ndc: Optional[str] = None
    rxnorm_id: Optional[str] = None
    class Config:
        from_attributes = True


class DrugIndexRef(BaseModel):
    id: int
    name: str

# Drug index search result
class DrugIndexOut(BaseModel):
    id: int
    name: str
    kind: str
    manufacturer: Optional[str] = None
    score: Optional[float] = None  # returned by search
    class Config: from_attributes = True