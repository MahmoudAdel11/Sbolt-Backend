from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from app.application.driver_profile.repository import DriverProfileRepository
from app.application.rating.repository import RatingRepository
from app.application.ride.repository import RideRepository
from app.core.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    RideCancelledError,
    RideNotStartedError,
)
from app.domain.rating.entities import Rating
from app.domain.ride.entities import Ride, RideStatus, RideTier, tiers_at_or_below
from app.domain.ride.geo import DEFAULT_AVAILABLE_RIDES_RADIUS_KM, bounding_box
from app.domain.ride.pricing import compute_fare

# Safety-net cap, not client-configurable - the bounding box already limits result
# size in practice, but this protects against a pathologically dense area.
_AVAILABLE_RIDES_LIMIT = 20


class RequestRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(
        self,
        rider_id: UUID,
        pickup_latitude: float,
        pickup_longitude: float,
        dropoff_latitude: float,
        dropoff_longitude: float,
        tier: RideTier,
    ) -> Ride:
        active_ride = await self._ride_repository.get_active_ride_for_rider_for_update(rider_id)
        if active_ride is not None:
            raise ConflictError("You already have an active ride.")

        fare = compute_fare(
            tier, pickup_latitude, pickup_longitude, dropoff_latitude, dropoff_longitude
        )
        ride = Ride(
            rider_id=rider_id,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            dropoff_latitude=dropoff_latitude,
            dropoff_longitude=dropoff_longitude,
            tier=tier,
            fare=fare,
        )
        return await self._ride_repository.create(ride)


class AcceptRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, driver_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id_for_update(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if ride.status == RideStatus.CANCELLED:
            raise RideCancelledError()
        if ride.status != RideStatus.REQUESTED:
            raise ConflictError("This ride is no longer available to accept.")

        ride.driver_id = driver_id
        ride.status = RideStatus.ACCEPTED
        ride.accepted_at = datetime.now(UTC)
        return await self._ride_repository.update(ride)


class CancelRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, user_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if user_id not in (ride.rider_id, ride.driver_id):
            raise ForbiddenError("You are not part of this ride.")

        if ride.status in (RideStatus.COMPLETED, RideStatus.CANCELLED):
            raise ConflictError("This ride can no longer be cancelled.")

        ride.status = RideStatus.CANCELLED
        ride.cancelled_at = datetime.now(UTC)
        return await self._ride_repository.update(ride)


class StartRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, driver_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if ride.driver_id != driver_id:
            raise ForbiddenError("You are not the driver for this ride.")

        if ride.status == RideStatus.CANCELLED:
            raise RideCancelledError()
        if ride.status != RideStatus.ACCEPTED:
            raise ConflictError("This ride cannot be started from its current status.")

        ride.status = RideStatus.ONGOING
        return await self._ride_repository.update(ride)


class CompleteRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, driver_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if ride.driver_id != driver_id:
            raise ForbiddenError("You are not the driver for this ride.")

        # ONGOING is now REQUIRED before completion - a deliberate product
        # decision, reversing the earlier "start is advisory, ACCEPTED or
        # ONGOING both complete fine" design. A driver who accepts but never
        # calls /start can no longer complete the ride directly; they must
        # start it first. ACCEPTED gets its own distinguishable error
        # (RideNotStartedError) rather than the generic conflict, since it's a
        # recoverable "do X first" situation, not a race condition.
        if ride.status == RideStatus.CANCELLED:
            raise RideCancelledError()
        if ride.status == RideStatus.ACCEPTED:
            raise RideNotStartedError()
        if ride.status != RideStatus.ONGOING:
            raise ConflictError("This ride cannot be completed from its current status.")

        ride.status = RideStatus.COMPLETED
        ride.completed_at = datetime.now(UTC)
        return await self._ride_repository.update(ride)


class SubmitRatingUseCase:
    """Only the ride's rider may rate it, only once it's COMPLETED, and only once
    ever - the third rule is enforced by RatingRepository via a DB UNIQUE
    constraint (translated to ConflictError on violation), not checked here, so
    there's exactly one place that can race-condition-proof it."""

    def __init__(self, ride_repository: RideRepository, rating_repository: RatingRepository):
        self._ride_repository = ride_repository
        self._rating_repository = rating_repository

    async def execute(self, ride_id: UUID, rider_id: UUID, score: int) -> Rating:
        ride = await self._ride_repository.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if ride.rider_id != rider_id:
            raise ForbiddenError("You are not the rider for this ride.")

        if ride.status != RideStatus.COMPLETED:
            raise ConflictError("Only a completed ride can be rated.")

        rating = Rating(
            ride_id=ride.id,
            rider_id=rider_id,
            # ride.driver_id is guaranteed set - a ride can only reach COMPLETED
            # after being accepted, which is what assigns driver_id in the first place.
            driver_id=ride.driver_id,
            score=score,
        )
        return await self._rating_repository.create(rating)


class GetRideHistoryUseCase:
    """`view` is an explicit caller choice, not inferred from stored state - a user can
    now be both rider and driver simultaneously, so "do they have a driver profile"
    can no longer disambiguate which history they mean; the client must say so."""

    def __init__(
        self, ride_repository: RideRepository, driver_profile_repository: DriverProfileRepository
    ):
        self._ride_repository = ride_repository
        self._driver_profile_repository = driver_profile_repository

    async def execute(
        self, user_id: UUID, view: Literal["rider", "driver"], limit: int, offset: int
    ) -> tuple[list[Ride], bool]:
        # Fetch one extra row to detect a next page without a separate COUNT(*) query.
        if view == "driver":
            # Same gating rationale as GetAvailableRidesUseCase: a clear 403 rather
            # than silently falling back to the rider view, which would hide a
            # client bug (asking for driver history from a non-driver account).
            driver_profile = await self._driver_profile_repository.get_by_user_id(user_id)
            if driver_profile is None:
                raise ForbiddenError("This account has no driver profile.")
            rides = await self._ride_repository.list_by_driver(user_id, limit + 1, offset)
        else:
            rides = await self._ride_repository.list_by_rider(user_id, limit + 1, offset)

        has_more = len(rides) > limit
        return rides[:limit], has_more


class GetAvailableRidesUseCase:
    """Unassigned ride requests near a driver, for the polling-based discovery feed.
    "Nearby" is a plain bounding box (see app.domain.ride.geo) - an intentional
    simplification, not PostGIS, so results are cheap but not a precise radius."""

    def __init__(
        self, ride_repository: RideRepository, driver_profile_repository: DriverProfileRepository
    ):
        self._ride_repository = ride_repository
        self._driver_profile_repository = driver_profile_repository

    async def execute(self, driver_id: UUID, latitude: float, longitude: float) -> list[Ride]:
        driver_profile = await self._driver_profile_repository.get_by_user_id(driver_id)
        # Consistent with require_driver's role gating: a clear 403, not a silently
        # empty list, so an offline driver's client can distinguish "you're offline"
        # from "no rides nearby right now" and react accordingly (e.g. prompt to go online).
        if driver_profile is None or not driver_profile.is_online:
            raise ForbiddenError("You must be online to view available rides.")

        lat_min, lat_max, lng_min, lng_max = bounding_box(
            latitude, longitude, DEFAULT_AVAILABLE_RIDES_RADIUS_KM
        )
        # NULL scooter_type (all pre-existing drivers) means "no restriction" -
        # None here skips the tier filter entirely in the repository rather than
        # restricting to an empty allow-list.
        allowed_tiers = (
            tiers_at_or_below(driver_profile.scooter_type)
            if driver_profile.scooter_type is not None
            else None
        )
        return await self._ride_repository.list_available(
            pickup_lat_min=lat_min,
            pickup_lat_max=lat_max,
            pickup_lng_min=lng_min,
            pickup_lng_max=lng_max,
            limit=_AVAILABLE_RIDES_LIMIT,
            allowed_tiers=allowed_tiers,
        )


class GetActiveRideUseCase:
    """Recovery path for a rider who lost track of a pending/accepted/ongoing
    ride client-side (e.g. app force-quit before the ride was accepted) - lets
    them ask "do I currently have an active ride?" as a first-class query,
    rather than the only prior way to find out (a 409 on a fresh
    POST /rides). Read-only: uses the non-locking get_active_ride_for_rider,
    not the _for_update variant RequestRideUseCase uses for its pre-mutation
    conflict check - a plain lookup has no transaction to protect."""

    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, rider_id: UUID) -> Ride | None:
        return await self._ride_repository.get_active_ride_for_rider(rider_id)


class GetRideDetailUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, user_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if user_id not in (ride.rider_id, ride.driver_id):
            raise ForbiddenError("You are not part of this ride.")

        return ride
