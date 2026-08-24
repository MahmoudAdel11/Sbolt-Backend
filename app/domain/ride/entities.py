from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class RideStatus(StrEnum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    ONGOING = "ongoing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RideTier(StrEnum):
    ECONOMY = "economy"
    COMFORT = "comfort"
    PREMIUM = "premium"


@dataclass
class Ride:
    rider_id: UUID
    pickup_latitude: float
    pickup_longitude: float
    dropoff_latitude: float
    dropoff_longitude: float
    # No default, unlike status/driver_id below - every ride must have an
    # explicit tier and a fare computed from it at request time (see
    # app.domain.ride.pricing.compute_fare); there is no meaningful "unset"
    # state for either, unlike the fields that follow.
    tier: RideTier
    fare: float
    status: RideStatus = RideStatus.REQUESTED
    driver_id: UUID | None = None
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    requested_at: datetime | None = None
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
