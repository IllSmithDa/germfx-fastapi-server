from pydantic import BaseModel, EmailStr

class ResendVerificationRequest(BaseModel):
    email: EmailStr