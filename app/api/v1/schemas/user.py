from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.domain.ride.entities import RideTier


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1)
    phone_number: str | None = None
    # A user can be a rider and a driver simultaneously - this only controls
    # whether a driver_profiles row is also created at registration time.
    register_as_driver: bool = False
    # Only meaningful (and required) when register_as_driver is true - a rider
    # has no scooter to declare. Enforced by the validator below rather than a
    # bare `Field(...)` required marker, since making it unconditionally
    # required would force riders to supply a meaningless value.
    scooter_type: RideTier | None = None

    @model_validator(mode="after")
    def _require_scooter_type_for_drivers(self) -> "UserRegisterRequest":
        if self.register_as_driver and self.scooter_type is None:
            raise ValueError("scooter_type is required when registering as a driver.")
        return self


class DriverProfileResponse(BaseModel):
    is_online: bool
    vehicle_type: str | None = None
    vehicle_color: str | None = None
    license_plate: str | None = None
    scooter_type: RideTier | None = None
    # Live-computed on every request (never cached/materialized) - None/0 when
    # the driver has no ratings yet.
    average_rating: float | None = None
    rating_count: int = 0


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
    refresh_token: str
    token_type: str = "bearer"


class RegisterResponse(BaseModel):
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    refresh_token: str


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1)
    phone_number: str | None = None
