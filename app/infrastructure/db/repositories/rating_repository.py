from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.rating.repository import RatingRepository
from app.core.exceptions import ConflictError
from app.domain.rating.entities import Rating
from app.infrastructure.db.models.rating import RatingModel


def _to_entity(model: RatingModel) -> Rating:
    return Rating(
        id=model.id,
        ride_id=model.ride_id,
        rider_id=model.rider_id,
        driver_id=model.driver_id,
        score=model.score,
        created_at=model.created_at,
    )


class SqlAlchemyRatingRepository(RatingRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, rating: Rating) -> Rating:
        model = RatingModel(
            ride_id=rating.ride_id,
            rider_id=rating.rider_id,
            driver_id=rating.driver_id,
            score=rating.score,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            # The UNIQUE constraint on ride_id is what actually enforces "one
            # rating per ride" - this is the only place that can fire.
            raise ConflictError("This ride has already been rated.") from exc

        await self._session.refresh(model)
        return _to_entity(model)

    async def get_average_and_count(self, driver_id: UUID) -> tuple[float | None, int]:
        result = await self._session.execute(
            select(func.avg(RatingModel.score), func.count(RatingModel.id)).where(
                RatingModel.driver_id == driver_id
            )
        )
        average, count = result.one()
        return (float(average) if average is not None else None, count)
