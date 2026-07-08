import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return value

    @field_validator("full_name")
    @classmethod
    def full_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Full name is required")
        return value.strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    full_name: str
