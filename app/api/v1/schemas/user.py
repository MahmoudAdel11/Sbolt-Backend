from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.domain.user.entities import UserRole


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    phone_number: str | None = None
    # Defaults to RIDER so existing clients that don't send this field are
    # unaffected. Pydantic validates this against the UserRole enum automatically -
    # any value outside {"rider", "driver"} is rejected with a 422, no manual check needed.
    role: UserRole = UserRole.RIDER


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone_number: str | None
    is_active: bool
    role: UserRole
    is_online: bool
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
