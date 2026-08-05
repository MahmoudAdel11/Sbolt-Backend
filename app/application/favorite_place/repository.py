from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.favorite_place.entities import FavoritePlace


class FavoritePlaceRepository(ABC):
    """Persistence contract for FavoritePlace, expressed in terms of the domain entity only."""

    @abstractmethod
    async def get_by_id(self, favorite_place_id: UUID) -> FavoritePlace | None: ...

    @abstractmethod
    async def list_by_user(self, user_id: UUID) -> list[FavoritePlace]: ...

    @abstractmethod
    async def create(self, favorite_place: FavoritePlace) -> FavoritePlace: ...

    @abstractmethod
    async def update(self, favorite_place: FavoritePlace) -> FavoritePlace: ...

    @abstractmethod
    async def delete(self, favorite_place_id: UUID) -> None: ...
