from uuid import UUID

from app.application.driver_profile.repository import DriverProfileRepository
from app.application.user.repository import UserRepository
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.domain.driver_profile.entities import DriverProfile
from app.domain.user.entities import User


class RegisterUserUseCase:
    def __init__(
        self, user_repository: UserRepository, driver_profile_repository: DriverProfileRepository
    ):
        self._user_repository = user_repository
        self._driver_profile_repository = driver_profile_repository

    async def execute(
        self,
        email: str,
        password: str,
        full_name: str,
        phone_number: str | None = None,
        register_as_driver: bool = False,
    ) -> User:
        if await self._user_repository.exists_by_email(email):
            raise ConflictError("A user with this email already exists.")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
            phone_number=phone_number,
        )
        user = await self._user_repository.create(user)

        if register_as_driver:
            # Both repositories share the request-scoped session (see
            # get_db_session) and neither commits directly - a failure here rolls
            # back the user creation above too, so this can't leave an orphaned
            # user with no driver profile.
            await self._driver_profile_repository.create(DriverProfile(user_id=user.id))

        return user


class LoginUserUseCase:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def execute(self, email: str, password: str) -> str:
        user = await self._user_repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Incorrect email or password.")

        return create_access_token(subject=str(user.id))


class UpdateProfileUseCase:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def execute(
        self, user_id: UUID, full_name: str | None = None, phone_number: str | None = None
    ) -> User:
        user = await self._user_repository.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if full_name is not None:
            user.full_name = full_name
        if phone_number is not None:
            user.phone_number = phone_number

        return await self._user_repository.update(user)


class SetDriverStatusUseCase:
    """Toggles a driver's online/offline availability. Role gating (does the caller
    have a driver profile at all?) happens at the API layer via DriverUserDep - this
    use case only persists the flag, on the driver_profiles row the dependency already
    confirmed exists."""

    def __init__(self, driver_profile_repository: DriverProfileRepository):
        self._driver_profile_repository = driver_profile_repository

    async def execute(self, user_id: UUID, is_online: bool) -> DriverProfile:
        driver_profile = await self._driver_profile_repository.get_by_user_id(user_id)
        if driver_profile is None:
            raise NotFoundError("Driver profile not found.")

        driver_profile.is_online = is_online
        return await self._driver_profile_repository.update(driver_profile)
