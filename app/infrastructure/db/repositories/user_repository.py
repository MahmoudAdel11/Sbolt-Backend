from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.user.repository import UserRepository
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.user.entities import User
from app.infrastructure.db.models.user import UserModel


def _to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        hashed_password=model.hashed_password,
        full_name=model.full_name,
        is_active=model.is_active,
        role=model.role,
        created_at=model.created_at,
        updated_at=model.updated_at,
        phone_number=model.phone_number,
    )


class SqlAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._session.get(UserModel, user_id)
        return _to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def create(self, user: User) -> User:
        model = UserModel(
            email=user.email,
            hashed_password=user.hashed_password,
            full_name=user.full_name,
            phone_number=user.phone_number,
            is_active=user.is_active,
            role=user.role,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def update(self, user: User) -> User:
        model = await self._session.get(UserModel, user.id)
        if model is None:
            raise NotFoundError("User not found.")

        model.full_name = user.full_name
        model.phone_number = user.phone_number

        try:
            await self._session.flush()
        except IntegrityError as exc:
            raise ConflictError("This phone number is already in use.") from exc

        await self._session.refresh(model)
        return _to_entity(model)

    async def exists_by_email(self, email: str) -> bool:
        result = await self._session.execute(select(UserModel.id).where(UserModel.email == email))
        return result.scalar_one_or_none() is not None
