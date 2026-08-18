from uuid import UUID

from app.application.user.repository import UserRepository
from app.core.exceptions import ConflictError, NotFoundError, UnauthorizedError
from app.core.jwt import create_access_token
from app.core.security import hash_password, verify_password
from app.domain.user.entities import User, UserRole


class RegisterUserUseCase:
    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def execute(
        self,
        email: str,
        password: str,
        full_name: str,
        phone_number: str | None = None,
        role: UserRole = UserRole.RIDER,
    ) -> User:
        if await self._user_repository.exists_by_email(email):
            raise ConflictError("A user with this email already exists.")

        user = User(
            email=email,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_active=True,
            phone_number=phone_number,
            role=role,
        )
        return await self._user_repository.create(user)


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
    """Toggles a driver's online/offline availability. Role gating (rider vs driver)
    happens at the API layer via DriverUserDep - this use case only persists the flag."""

    def __init__(self, user_repository: UserRepository):
        self._user_repository = user_repository

    async def execute(self, user_id: UUID, is_online: bool) -> User:
        return await self._user_repository.set_online_status(user_id, is_online)
