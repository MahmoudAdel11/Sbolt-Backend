from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.ride.entities import Ride, RideTier


class RideRepository(ABC):
    """Persistence contract for Ride, expressed in terms of the domain entity only."""

    @abstractmethod
    async def get_by_id(self, ride_id: UUID) -> Ride | None: ...

    @abstractmethod
    async def get_by_id_for_update(self, ride_id: UUID) -> Ride | None:
        """Like get_by_id, but locks the row (SELECT ... FOR UPDATE) for the rest of the
        transaction. Use for check-then-act sequences where a concurrent writer must be
        blocked until this transaction commits or rolls back."""
        ...

    @abstractmethod
    async def create(self, ride: Ride) -> Ride: ...

    @abstractmethod
    async def update(self, ride: Ride) -> Ride: ...

    @abstractmethod
    async def get_active_ride_for_rider(self, rider_id: UUID) -> Ride | None: ...

    @abstractmethod
    async def get_active_ride_for_rider_for_update(self, rider_id: UUID) -> Ride | None:
        """Like get_active_ride_for_rider, but locks any matching row for the rest of the
        transaction - see get_by_id_for_update."""
        ...

    @abstractmethod
    async def list_by_rider(self, rider_id: UUID, limit: int, offset: int) -> list[Ride]: ...

    @abstractmethod
    async def list_by_driver(self, driver_id: UUID, limit: int, offset: int) -> list[Ride]: ...

    @abstractmethod
    async def list_available(
        self,
        pickup_lat_min: float,
        pickup_lat_max: float,
        pickup_lng_min: float,
        pickup_lng_max: float,
        limit: int,
        allowed_tiers: list[RideTier] | None = None,
    ) -> list[Ride]:
        """Unassigned (driver_id IS NULL), REQUESTED rides whose pickup point falls
        within the given bounding box - see app.domain.ride.geo for how the box is
        derived. Most-recent-first, capped at limit.

        `allowed_tiers=None` applies no tier filtering at all (every tier is
        returned) - used for a driver with no scooter_type set. Passing a list
        restricts results to those tiers only (see
        app.domain.ride.entities.tiers_at_or_below)."""
        ...
