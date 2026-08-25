from datetime import UTC, datetime, timedelta

from app.application.refresh_token.repository import RefreshTokenRepository
from app.application.user.repository import UserRepository
from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError
from app.core.jwt import create_access_token
from app.core.security import hash_token


class RefreshAccessTokenUseCase:
    def __init__(
        self, refresh_token_repository: RefreshTokenRepository, user_repository: UserRepository
    ):
        self._refresh_token_repository = refresh_token_repository
        self._user_repository = user_repository

    async def execute(self, refresh_token: str) -> str:
        token_hash = hash_token(refresh_token)
        stored = await self._refresh_token_repository.get_valid_by_hash(token_hash)
        if stored is None:
            raise UnauthorizedError("Invalid or expired refresh token.")

        user = await self._user_repository.get_by_id(stored.user_id)
        if user is None:
            raise UnauthorizedError("User no longer exists.")

        # Sliding expiration: the same row is extended in place, not replaced -
        # concurrent refresh calls with the same token both just push expires_at
        # further out rather than racing to invalidate-and-reissue.
        settings = get_settings()
        new_expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
        await self._refresh_token_repository.extend(stored.id, new_expires_at)

        return create_access_token(subject=str(user.id))


class LogoutUseCase:
    def __init__(self, refresh_token_repository: RefreshTokenRepository):
        self._refresh_token_repository = refresh_token_repository

    async def execute(self, refresh_token: str) -> None:
        await self._refresh_token_repository.delete_by_hash(hash_token(refresh_token))
