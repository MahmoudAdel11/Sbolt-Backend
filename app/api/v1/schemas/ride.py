from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.ride.entities import RideStatus


class RideRequestSchema(BaseModel):
    pickup_latitude: float = Field(ge=-90, le=90)
    pickup_longitude: float = Field(ge=-180, le=180)
    dropoff_latitude: float = Field(ge=-90, le=90)
    dropoff_longitude: float = Field(ge=-180, le=180)


class RideResponse(BaseModel):
    id: UUID
    rider_id: UUID
    driver_id: UUID | None
    status: RideStatus
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    requested_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class RideHistoryQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class RideHistoryResponse(BaseModel):
    """items + has_more, not items + total: an accurate total would require a
    separate COUNT(*) on every request, which is wasted cost for a feed users
    mostly scroll through. has_more is derived cheaply by over-fetching by one row."""

    items: list[RideResponse]
    has_more: bool
