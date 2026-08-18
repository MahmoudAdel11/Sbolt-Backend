from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.user.entities import User


class UserRepository(ABC):
    """Persistence contract for User, expressed in terms of the domain entity only."""

    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def create(self, user: User) -> User: ...

    @abstractmethod
    async def update(self, user: User) -> User: ...

    @abstractmethod
    async def exists_by_email(self, email: str) -> bool: ...

    @abstractmethod
    async def set_online_status(self, user_id: UUID, is_online: bool) -> User:
        """Sets is_online directly, independent of the profile-fields update() method -
        driver availability is a distinct concern from profile editing."""
        ...
