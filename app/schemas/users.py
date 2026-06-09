from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional
from app.util.security import canonicalize_email


class UserCreate(BaseModel):
    username: str = Field(min_length=4, max_length=20)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    is_email_verified: bool

    class Config:
        from_attributes = True


class UserDetailOut(BaseModel):
    id: Optional[int]
    username: str
    is_email_verified: Optional[bool] = None
    email: str

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    identifier: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")

        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password")

        return self


class ChangeUsernameRequest(BaseModel):
    new_username: str = Field(min_length=4, max_length=20)


class ChangeEmailRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_email: EmailStr
    confirm_new_email: EmailStr

    @model_validator(mode="after")
    def validate_emails(self):
        if (
            canonicalize_email(self.new_email)
            != canonicalize_email(self.confirm_new_email)
        ):
            raise ValueError("New emails do not match")
        return self
    

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_passwords(self):
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self

class ConfirmPasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)

class DeleteAccountRequest(BaseModel):
    current_password: str = Field(min_length=1)
    confirmation_text: str = Field(min_length=1)

class ReactivateAccountRequest(BaseModel):
    identifier: str = Field(min_length=3)
    password: str = Field(min_length=1)
