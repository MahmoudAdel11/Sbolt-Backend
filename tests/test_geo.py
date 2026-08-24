import pytest

from app.domain.ride.geo import haversine_km


def test_haversine_same_point_is_zero() -> None:
    assert haversine_km(30.05, 31.23, 30.05, 31.23) == pytest.approx(0.0, abs=1e-9)


def test_haversine_one_degree_latitude_is_about_111_km() -> None:
    # A well-known reference: one degree of latitude is ~111.2 km everywhere
    # on Earth (matches this codebase's own _KM_PER_DEGREE_LATITUDE constant
    # in bounding_box, used here purely as an independent sanity check).
    distance = haversine_km(0.0, 0.0, 1.0, 0.0)
    assert distance == pytest.approx(111.19, abs=0.1)


def test_haversine_cairo_to_alexandria_matches_known_distance() -> None:
    # Cairo (30.0444, 31.2357) to Alexandria (31.2001, 29.9187) - commonly
    # cited straight-line distance is ~180 km.
    distance = haversine_km(30.0444, 31.2357, 31.2001, 29.9187)
    assert distance == pytest.approx(180.0, abs=2.0)


def test_haversine_is_symmetric() -> None:
    a_to_b = haversine_km(30.05, 31.23, 30.06, 31.25)
    b_to_a = haversine_km(30.06, 31.25, 30.05, 31.23)
    assert a_to_b == pytest.approx(b_to_a, abs=1e-9)
