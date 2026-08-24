import pytest

from app.domain.ride.entities import RideTier
from app.domain.ride.geo import haversine_km
from app.domain.ride.pricing import compute_fare

_PICKUP = (30.05, 31.23)
_DROPOFF = (30.06, 31.25)


@pytest.mark.parametrize(
    ("tier", "base_price", "per_km_rate"),
    [
        (RideTier.ECONOMY, 15.0, 3.0),
        (RideTier.COMFORT, 25.0, 4.5),
        (RideTier.PREMIUM, 40.0, 7.0),
    ],
)
def test_compute_fare_matches_formula_exactly(
    tier: RideTier, base_price: float, per_km_rate: float
) -> None:
    distance_km = haversine_km(*_PICKUP, *_DROPOFF)
    expected = base_price + distance_km * per_km_rate

    fare = compute_fare(tier, *_PICKUP, *_DROPOFF)

    assert fare == pytest.approx(expected, abs=1e-9)


def test_higher_tiers_cost_more_for_the_same_trip() -> None:
    economy = compute_fare(RideTier.ECONOMY, *_PICKUP, *_DROPOFF)
    comfort = compute_fare(RideTier.COMFORT, *_PICKUP, *_DROPOFF)
    premium = compute_fare(RideTier.PREMIUM, *_PICKUP, *_DROPOFF)

    assert economy < comfort < premium


def test_zero_distance_fare_equals_base_price() -> None:
    fare = compute_fare(RideTier.ECONOMY, 30.05, 31.23, 30.05, 31.23)
    assert fare == pytest.approx(15.0, abs=1e-9)
