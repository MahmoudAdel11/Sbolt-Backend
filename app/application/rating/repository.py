from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.rating.entities import Rating


class RatingRepository(ABC):
    """Persistence contract for Rating, expressed in terms of the domain entity only."""

    @abstractmethod
    async def create(self, rating: Rating) -> Rating: ...

    @abstractmethod
    async def get_average_and_count(self, driver_id: UUID) -> tuple[float | None, int]:
        """Live aggregate - `None`/`0` when the driver has no ratings yet, never cached."""
        ...
