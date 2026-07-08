from pydantic import BaseModel, EmailStr, Field

class ResendVerificationRequest(BaseModel):
    email: EmailStr
    turnstile_token: str | None = Field(default=None, max_length=2048)