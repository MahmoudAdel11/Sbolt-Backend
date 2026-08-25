import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.refresh_token.repository import RefreshTokenRepository
from app.core.config import get_settings
from app.core.security import hash_token
from app.domain.refresh_token.entities import RefreshToken
from app.infrastructure.db.models.refresh_token import RefreshTokenModel


def _to_entity(model: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=model.id,
        user_id=model.user_id,
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        created_at=model.created_at,
    )


class SqlAlchemyRefreshTokenRepository(RefreshTokenRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def create(self, user_id: UUID) -> str:
        settings = get_settings()
        raw_token = secrets.token_urlsafe(32)
        model = RefreshTokenModel(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days),
        )
        self._session.add(model)
        await self._session.flush()
        return raw_token

    async def get_valid_by_hash(self, token_hash: str) -> RefreshToken | None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(
                RefreshTokenModel.token_hash == token_hash,
                RefreshTokenModel.expires_at > datetime.now(UTC),
            )
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def extend(self, token_id: UUID, new_expires_at: datetime) -> None:
        model = await self._session.get(RefreshTokenModel, token_id)
        if model is not None:
            model.expires_at = new_expires_at
            await self._session.flush()

    async def delete_by_hash(self, token_hash: str) -> None:
        result = await self._session.execute(
            select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        if model is not None:
            await self._session.delete(model)
            await self._session.flush()
