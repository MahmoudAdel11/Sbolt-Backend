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


# Explicit hierarchy for driver/scooter-type capability filtering
# (Street=ECONOMY < Ride=COMFORT < Black=PREMIUM, per the scooter-types product
# decision) - StrEnum members compare by string value/identity only, declaration
# order isn't exposed as comparable, so this must be spelled out by hand.
_TIER_RANK: dict[RideTier, int] = {
    RideTier.ECONOMY: 1,
    RideTier.COMFORT: 2,
    RideTier.PREMIUM: 3,
}


def tiers_at_or_below(tier: RideTier) -> list[RideTier]:
    """Every tier a driver whose scooter_type is `tier` can accept - their own
    tier plus every tier ranked below it (a Black driver can also take
    Ride/Street rides; a Street driver can only take Street)."""
    rank = _TIER_RANK[tier]
    return [t for t, r in _TIER_RANK.items() if r <= rank]


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
    # Resolved client-side (CLGeocoder) at request time, sent alongside the
    # coordinates - see the coordinate fields above. None when geocoding
    # failed or wasn't available client-side; display falls back to
    # coordinates in that case (a client-side concern, not this entity's).
    pickup_address: str | None = None
    dropoff_address: str | None = None
    # Server-generated on persistence; unset (None) before the repository assigns them.
    id: UUID | None = None
    requested_at: datetime | None = None
    accepted_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
