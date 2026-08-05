from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    phone_number: str | None = None


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone_number: str | None
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    phone_number: str | None = None
