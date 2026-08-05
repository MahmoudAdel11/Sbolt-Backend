from datetime import UTC, datetime
from uuid import UUID

from app.application.ride.repository import RideRepository
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.domain.ride.entities import Ride, RideStatus
from app.domain.user.entities import User, UserRole


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
    ) -> Ride:
        active_ride = await self._ride_repository.get_active_ride_for_rider_for_update(rider_id)
        if active_ride is not None:
            raise ConflictError("You already have an active ride.")

        ride = Ride(
            rider_id=rider_id,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            dropoff_latitude=dropoff_latitude,
            dropoff_longitude=dropoff_longitude,
        )
        return await self._ride_repository.create(ride)


class AcceptRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, driver_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id_for_update(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

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


class CompleteRideUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, ride_id: UUID, driver_id: UUID) -> Ride:
        ride = await self._ride_repository.get_by_id(ride_id)
        if ride is None:
            raise NotFoundError("Ride not found.")

        if ride.driver_id != driver_id:
            raise ForbiddenError("You are not the driver for this ride.")

        # No separate ACCEPTED -> ONGOING ("start ride") transition exists yet, so
        # ACCEPTED is treated as the ride being underway; adding a dedicated "start"
        # endpoint here would be scope creep beyond this phase. Once one exists,
        # tighten this check to RideStatus.ONGOING only.
        if ride.status not in (RideStatus.ACCEPTED, RideStatus.ONGOING):
            raise ConflictError("This ride cannot be completed from its current status.")

        ride.status = RideStatus.COMPLETED
        ride.completed_at = datetime.now(UTC)
        return await self._ride_repository.update(ride)


class GetRideHistoryUseCase:
    def __init__(self, ride_repository: RideRepository):
        self._ride_repository = ride_repository

    async def execute(self, user: User, limit: int, offset: int) -> tuple[list[Ride], bool]:
        # Fetch one extra row to detect a next page without a separate COUNT(*) query.
        if user.role == UserRole.DRIVER:
            rides = await self._ride_repository.list_by_driver(user.id, limit + 1, offset)
        else:
            rides = await self._ride_repository.list_by_rider(user.id, limit + 1, offset)

        has_more = len(rides) > limit
        return rides[:limit], has_more


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
