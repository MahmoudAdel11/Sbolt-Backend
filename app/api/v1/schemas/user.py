from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    phone_number: str | None = None
    # A user can be a rider and a driver simultaneously - this only controls
    # whether a driver_profiles row is also created at registration time.
    register_as_driver: bool = False


class DriverProfileResponse(BaseModel):
    is_online: bool


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    phone_number: str | None
    is_active: bool
    # null when the user has no driver profile - the sole source of truth for
    # "is this user a driver", not a role/flag on the user itself.
    driver_profile: DriverProfileResponse | None
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
