from uuid import UUID

from app.application.favorite_place.repository import FavoritePlaceRepository
from app.core.exceptions import ForbiddenError, NotFoundError
from app.domain.favorite_place.entities import FavoritePlace


class CreateFavoritePlaceUseCase:
    def __init__(self, favorite_place_repository: FavoritePlaceRepository):
        self._favorite_place_repository = favorite_place_repository

    async def execute(
        self, user_id: UUID, label: str, address: str, latitude: float, longitude: float
    ) -> FavoritePlace:
        favorite_place = FavoritePlace(
            user_id=user_id, label=label, address=address, latitude=latitude, longitude=longitude
        )
        return await self._favorite_place_repository.create(favorite_place)


class ListFavoritePlacesUseCase:
    def __init__(self, favorite_place_repository: FavoritePlaceRepository):
        self._favorite_place_repository = favorite_place_repository

    async def execute(self, user_id: UUID) -> list[FavoritePlace]:
        return await self._favorite_place_repository.list_by_user(user_id)


class UpdateFavoritePlaceUseCase:
    def __init__(self, favorite_place_repository: FavoritePlaceRepository):
        self._favorite_place_repository = favorite_place_repository

    async def execute(
        self,
        favorite_place_id: UUID,
        user_id: UUID,
        label: str | None = None,
        address: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> FavoritePlace:
        favorite_place = await self._favorite_place_repository.get_by_id(favorite_place_id)
        if favorite_place is None:
            raise NotFoundError("Favorite place not found.")

        if favorite_place.user_id != user_id:
            raise ForbiddenError("You do not have access to this favorite place.")

        if label is not None:
            favorite_place.label = label
        if address is not None:
            favorite_place.address = address
        if latitude is not None:
            favorite_place.latitude = latitude
        if longitude is not None:
            favorite_place.longitude = longitude

        return await self._favorite_place_repository.update(favorite_place)


class DeleteFavoritePlaceUseCase:
    def __init__(self, favorite_place_repository: FavoritePlaceRepository):
        self._favorite_place_repository = favorite_place_repository

    async def execute(self, favorite_place_id: UUID, user_id: UUID) -> None:
        favorite_place = await self._favorite_place_repository.get_by_id(favorite_place_id)
        if favorite_place is None:
            raise NotFoundError("Favorite place not found.")

        if favorite_place.user_id != user_id:
            raise ForbiddenError("You do not have access to this favorite place.")

        await self._favorite_place_repository.delete(favorite_place_id)
