from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.driver_profile.repository import DriverProfileRepository
from app.core.exceptions import NotFoundError
from app.domain.driver_profile.entities import DriverProfile
from app.infrastructure.db.models.driver_profile import DriverProfileModel


def _to_entity(model: DriverProfileModel) -> DriverProfile:
    return DriverProfile(
        id=model.id,
        user_id=model.user_id,
        is_online=model.is_online,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SqlAlchemyDriverProfileRepository(DriverProfileRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_user_id(self, user_id: UUID) -> DriverProfile | None:
        result = await self._session.execute(
            select(DriverProfileModel).where(DriverProfileModel.user_id == user_id)
        )
        model = result.scalar_one_or_none()
        return _to_entity(model) if model else None

    async def create(self, driver_profile: DriverProfile) -> DriverProfile:
        model = DriverProfileModel(
            user_id=driver_profile.user_id,
            is_online=driver_profile.is_online,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)

    async def update(self, driver_profile: DriverProfile) -> DriverProfile:
        model = await self._session.get(DriverProfileModel, driver_profile.id)
        if model is None:
            raise NotFoundError("Driver profile not found.")

        model.is_online = driver_profile.is_online

        await self._session.flush()
        await self._session.refresh(model)
        return _to_entity(model)
