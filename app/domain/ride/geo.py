import math

# Intentional simplification (not an oversight): "nearby" is a plain lat/lng bounding
# box, not a true radius, and not backed by PostGIS/any geospatial index or extension.
# A bounding box is cheap (two BETWEEN comparisons on existing Numeric columns, no new
# infra) and close enough for a driver-availability feed at this stage. It over-includes
# the box's corners (up to ~1.41x the intended radius from the center) rather than a
# precise circle - acceptable here since it only widens candidates slightly, never hides
# genuinely nearby rides. Revisit with PostGIS if precise radius search is ever needed.
DEFAULT_AVAILABLE_RIDES_RADIUS_KM = 5.0

# Degrees of latitude per kilometre is constant everywhere on Earth (a standard,
# widely-used approximation - WGS84's actual value varies by a fraction of a percent
# with latitude, which doesn't matter at this precision).
_KM_PER_DEGREE_LATITUDE = 111.32


def bounding_box(
    latitude: float, longitude: float, radius_km: float = DEFAULT_AVAILABLE_RIDES_RADIUS_KM
) -> tuple[float, float, float, float]:
    """Returns (lat_min, lat_max, lng_min, lng_max) for a simple bounding box of
    +/-radius_km around (latitude, longitude).

    Longitude degrees shrink toward the poles by a factor of cos(latitude), unlike
    latitude degrees which are constant - so the longitude offset must account for it.
    Clamped defensively at the poles (cos -> 0) to avoid a division blow-up; driver
    availability searches at the poles aren't a real scenario, this just keeps the
    function total instead of raising.
    """
    lat_offset = radius_km / _KM_PER_DEGREE_LATITUDE

    cos_latitude = max(math.cos(math.radians(latitude)), 1e-6)
    lng_offset = radius_km / (_KM_PER_DEGREE_LATITUDE * cos_latitude)

    return (
        latitude - lat_offset,
        latitude + lat_offset,
        longitude - lng_offset,
        longitude + lng_offset,
    )


# Mean Earth radius in kilometres - the standard constant for haversine.
_EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line (great-circle) distance between two points, in km.

    Deliberately not a routed/driving distance - there's no directions API
    on this backend, and iOS's own (now-superseded) client-side fare
    estimate used the same kind of straight-line distance
    (CLLocation.distance(from:)), so this keeps the fare formula
    consistent with what was already considered "close enough."
    """
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lng2 - lng1)

    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return _EARTH_RADIUS_KM * c
