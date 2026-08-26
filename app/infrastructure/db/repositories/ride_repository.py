from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ride.repository import RideRepository
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.ride.entities import Ride, RideStatus, RideTier
from app.infrastructure.db.models.ride import RideModel

_TERMINAL_STATUSES = (RideStatus.COMPLETED, RideStatus.CANCELLED)


def _to_entity(model: RideModel) -> Ride:
    return Ride(
        id=model.id,
        rider_id=model.rider_id,
        driver_id=model.driver_id,
        status=model.status,
        pickup_latitude=float(model.pickup_latitude),
        pickup_longitude=float(model.pickup_longitude),
        dropoff_latitude=float(model.dropoff_latitude),
        dropoff_longitude=float(model.dropoff_longitude),
        tier=model.tier,
        fare=float(model.fare),
        requested_at=model.requested_at,
        accepted_at=model.accepted_at,
        completed_at=model.completed_at,
        cancelled_at=model.cancelled_at,
    )


class SqlAlchemyRideRepository(RideRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, ride_id: UUID) -> Ride | None:
        model = await self._session.get(RideModel, ride_id)
        return _to_entity(model) if model else None

    async def get_by_id_for_update(self, ride_id: UUID) -> Ride | None:
        result = await self._session.execute(
            select(RideModel).where(RideModel.id == ride_id).with_for_update()
        )
        model = result.scalars().first()
        return _to_entity(model) if model else None

    async def create(self, ride: Ride) -> Ride:
        model = RideModel(
            rider_id=ride.rider_id,
            driver_id=ride.driver_id,
            status=ride.status,
            pickup_latitude=ride.pickup_latitude,
            pickup_longitude=ride.pickup_longitude,
            dropoff_latitude=ride.dropoff_latitude,
            dropoff_longitude=ride.dropoff_longitude,
            tier=ride.tier,
            fare=ride.fare,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("You already have an active ride.") from exc

        await self._session.refresh(model)
        return _to_entity(model)

    async def update(self, ride: Ride) -> Ride:
        model = await self._session.get(RideModel, ride.id)
        if model is None:
            raise NotFoundError("Ride not found.")

        model.driver_id = ride.driver_id
        model.status = ride.status
        model.accepted_at = ride.accepted_at
        model.completed_at = ride.completed_at
        model.cancelled_at = ride.cancelled_at

        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def get_active_ride_for_rider(self, rider_id: UUID) -> Ride | None:
        result = await self._session.execute(
            select(RideModel).where(
                RideModel.rider_id == rider_id,
                RideModel.status.not_in(_TERMINAL_STATUSES),
            )
        )
        model = result.scalars().first()
        return _to_entity(model) if model else None

    async def get_active_ride_for_rider_for_update(self, rider_id: UUID) -> Ride | None:
        result = await self._session.execute(
            select(RideModel)
            .where(
                RideModel.rider_id == rider_id,
                RideModel.status.not_in(_TERMINAL_STATUSES),
            )
            .with_for_update()
        )
        model = result.scalars().first()
        return _to_entity(model) if model else None

    async def list_by_rider(self, rider_id: UUID, limit: int, offset: int) -> list[Ride]:
        result = await self._session.execute(
            select(RideModel)
            .where(RideModel.rider_id == rider_id)
            .order_by(desc(RideModel.requested_at))
            .limit(limit)
            .offset(offset)
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def list_by_driver(self, driver_id: UUID, limit: int, offset: int) -> list[Ride]:
        result = await self._session.execute(
            select(RideModel)
            .where(RideModel.driver_id == driver_id)
            .order_by(desc(RideModel.requested_at))
            .limit(limit)
            .offset(offset)
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def list_available(
        self,
        pickup_lat_min: float,
        pickup_lat_max: float,
        pickup_lng_min: float,
        pickup_lng_max: float,
        limit: int,
        allowed_tiers: list[RideTier] | None = None,
    ) -> list[Ride]:
        conditions = [
            RideModel.status == RideStatus.REQUESTED,
            RideModel.driver_id.is_(None),
            RideModel.pickup_latitude.between(pickup_lat_min, pickup_lat_max),
            RideModel.pickup_longitude.between(pickup_lng_min, pickup_lng_max),
        ]
        # None means "no restriction" (driver has no scooter_type set) - skip the
        # tier condition entirely rather than filtering to an empty allow-list.
        if allowed_tiers is not None:
            conditions.append(RideModel.tier.in_(allowed_tiers))

        result = await self._session.execute(
            select(RideModel)
            .where(*conditions)
            .order_by(desc(RideModel.requested_at))
            .limit(limit)
        )
        return [_to_entity(model) for model in result.scalars().all()]
