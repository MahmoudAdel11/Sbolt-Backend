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


class AvailableRidesQuery(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class RideHistoryQuery(BaseModel):
    # NOTE: `view` (below) is intentionally NOT on this model. FastAPI 0.115's
    # Depends()-bound-Pydantic-model query params bind by field *name*, not
    # alias/Field(alias=...) - confirmed via the generated OpenAPI schema, which
    # exposed "view" instead of the intended "as" when this field lived here. The
    # `as` query param is instead declared directly on the route function via
    # Query(alias="as"), since Python can't name an attribute `as` (a keyword)
    # for a model field to alias away from in the first place.
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class RideHistoryResponse(BaseModel):
    """items + has_more, not items + total: an accurate total would require a
    separate COUNT(*) on every request, which is wasted cost for a feed users
    mostly scroll through. has_more is derived cheaply by over-fetching by one row."""

    items: list[RideResponse]
    has_more: bool
