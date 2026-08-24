from app.domain.ride.entities import RideTier
from app.domain.ride.geo import haversine_km

# Hardcoded per confirmed decision - no admin configuration, no DB table.
# Placeholder EGP values, one flat base price per tier (not a multiplier
# applied to a single shared base) plus a tier-specific per-km rate -
# cosmetic numbers, easy to tune later without touching the formula itself.
_BASE_PRICE_EGP: dict[RideTier, float] = {
    RideTier.ECONOMY: 15.0,
    RideTier.COMFORT: 25.0,
    RideTier.PREMIUM: 40.0,
}
_PER_KM_RATE_EGP: dict[RideTier, float] = {
    RideTier.ECONOMY: 3.0,
    RideTier.COMFORT: 4.5,
    RideTier.PREMIUM: 7.0,
}


def compute_fare(
    tier: RideTier,
    pickup_latitude: float,
    pickup_longitude: float,
    dropoff_latitude: float,
    dropoff_longitude: float,
) -> float:
    """base_price[tier] + haversine_km(pickup, dropoff) * per_km_rate[tier].

    Computed once, at request time, from the same pickup/dropoff coordinates
    stored on the ride - never recalculated later, since those coordinates
    never change after a ride is requested.
    """
    distance_km = haversine_km(
        pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude
    )
    return _BASE_PRICE_EGP[tier] + distance_km * _PER_KM_RATE_EGP[tier]
