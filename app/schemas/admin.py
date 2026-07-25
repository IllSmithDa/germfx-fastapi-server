from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional
from app.util.security import canonicalize_email

class AdminSuspendAccountRequest(BaseModel):
    user_id: int
    reason: Optional[str] = Field(default=None, max_length=500)


class AdminReactivateAccountRequest(BaseModel):
    user_id: int

class DrugIndexCodeUpdateRequest(BaseModel):
    add_upc_codes: list[str] = Field(default_factory=list)
    add_ndc_codes: list[str] = Field(default_factory=list)
    remove_upc_codes: list[str] = Field(default_factory=list)
    remove_ndc_codes: list[str] = Field(default_factory=list)

class SuspendUserRequest(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=320)

    reason: Optional[str] = Field(default=None, max_length=500)


class UnsuspendUserRequest(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=320)

    reason: Optional[str] = Field(default=None, max_length=500)

class AdminUserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    account_status: str | None = None
    suspended_at: datetime | None = None
    suspension_reason: str | None = None