from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.favorite_place.repository import FavoritePlaceRepository
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.favorite_place.entities import FavoritePlace
from app.infrastructure.db.models.favorite_place import FavoritePlaceModel


def _to_entity(model: FavoritePlaceModel) -> FavoritePlace:
    return FavoritePlace(
        id=model.id,
        user_id=model.user_id,
        label=model.label,
        address=model.address,
        latitude=float(model.latitude),
        longitude=float(model.longitude),
        created_at=model.created_at,
    )


class SqlAlchemyFavoritePlaceRepository(FavoritePlaceRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, favorite_place_id: UUID) -> FavoritePlace | None:
        model = await self._session.get(FavoritePlaceModel, favorite_place_id)
        return _to_entity(model) if model else None

    async def list_by_user(self, user_id: UUID) -> list[FavoritePlace]:
        result = await self._session.execute(
            select(FavoritePlaceModel).where(FavoritePlaceModel.user_id == user_id)
        )
        return [_to_entity(model) for model in result.scalars().all()]

    async def create(self, favorite_place: FavoritePlace) -> FavoritePlace:
        model = FavoritePlaceModel(
            user_id=favorite_place.user_id,
            label=favorite_place.label,
            address=favorite_place.address,
            latitude=favorite_place.latitude,
            longitude=favorite_place.longitude,
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("You already have a favorite place with this label.") from exc

        await self._session.refresh(model)
        return _to_entity(model)

    async def update(self, favorite_place: FavoritePlace) -> FavoritePlace:
        model = await self._session.get(FavoritePlaceModel, favorite_place.id)
        if model is None:
            raise NotFoundError("Favorite place not found.")

        model.label = favorite_place.label
        model.address = favorite_place.address
        model.latitude = favorite_place.latitude
        model.longitude = favorite_place.longitude

        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("You already have a favorite place with this label.") from exc

        await self._session.refresh(model)
        return _to_entity(model)

    async def delete(self, favorite_place_id: UUID) -> None:
        model = await self._session.get(FavoritePlaceModel, favorite_place_id)
        if model is None:
            raise NotFoundError("Favorite place not found.")

        await self._session.delete(model)
        await self._session.flush()
