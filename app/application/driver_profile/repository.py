from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.driver_profile.entities import DriverProfile


class DriverProfileRepository(ABC):
    """Persistence contract for DriverProfile, expressed in terms of the domain entity only."""

    @abstractmethod
    async def get_by_user_id(self, user_id: UUID) -> DriverProfile | None: ...

    @abstractmethod
    async def create(self, driver_profile: DriverProfile) -> DriverProfile: ...

    @abstractmethod
    async def update(self, driver_profile: DriverProfile) -> DriverProfile: ...
