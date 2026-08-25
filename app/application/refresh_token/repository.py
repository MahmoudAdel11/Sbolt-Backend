from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.refresh_token.entities import RefreshToken


class RefreshTokenRepository(ABC):
    """Persistence contract for RefreshToken, expressed in terms of the domain entity only."""

    @abstractmethod
    async def create(self, user_id: UUID) -> str:
        """Generates a new opaque token, stores its hash, and returns the raw value.
        The raw value is only ever available here - never persisted, never retrievable again."""
        ...

    @abstractmethod
    async def get_valid_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Returns the token only if it exists and has not expired."""
        ...

    @abstractmethod
    async def extend(self, token_id: UUID, new_expires_at: datetime) -> None: ...

    @abstractmethod
    async def delete_by_hash(self, token_hash: str) -> None: ...
