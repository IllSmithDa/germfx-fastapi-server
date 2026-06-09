from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional
from app.util.security import canonicalize_email

class AdminSuspendAccountRequest(BaseModel):
    user_id: int
    reason: Optional[str] = Field(default=None, max_length=500)


class AdminReactivateAccountRequest(BaseModel):
    user_id: int