from pydantic import BaseModel, Field


class DriverStatusUpdateRequest(BaseModel):
    is_online: bool


class DriverVehicleUpdateRequest(BaseModel):
    """Partial update - all fields optional, only provided ones change."""

    vehicle_type: str | None = Field(default=None, min_length=1, max_length=50)
    vehicle_color: str | None = Field(default=None, min_length=1, max_length=30)
    license_plate: str | None = Field(default=None, min_length=1, max_length=20)
