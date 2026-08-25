"""Test factories that create real data by calling the app's own use cases / repositories /
security functions - never reimplementing hashing or persistence logic, so factories stay honest
and don't silently drift from how the app actually behaves.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ride.use_cases import RequestRideUseCase
from app.application.user.use_cases import LoginUserUseCase, RegisterUserUseCase
from app.domain.ride.entities import Ride, RideTier
from app.domain.user.entities import User
from app.infrastructure.db.repositories.driver_profile_repository import (
    SqlAlchemyDriverProfileRepository,
)
from app.infrastructure.db.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.db.repositories.ride_repository import SqlAlchemyRideRepository
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository

DEFAULT_PASSWORD = "supersecret123"


@dataclass
class CreatedUser:
    user: User
    password: str
    access_token: str
    refresh_token: str


async def create_user(
    session: AsyncSession,
    *,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    full_name: str = "Test User",
    phone_number: str | None = None,
    as_driver: bool = False,
) -> CreatedUser:
    """Create a persisted user with a real hashed password and a real JWT, via the app's own
    RegisterUserUseCase/LoginUserUseCase. `as_driver=True` also creates a driver_profiles row
    (a user can be a rider and a driver simultaneously - this doesn't make them exclusively one).
    """
    email = email or f"{uuid4()}@example.com"
    user_repository = SqlAlchemyUserRepository(session)
    driver_profile_repository = SqlAlchemyDriverProfileRepository(session)
    refresh_token_repository = SqlAlchemyRefreshTokenRepository(session)

    register_use_case = RegisterUserUseCase(
        user_repository, driver_profile_repository, refresh_token_repository
    )
    result = await register_use_case.execute(
        email=email,
        password=password,
        full_name=full_name,
        phone_number=phone_number,
        register_as_driver=as_driver,
    )

    login_use_case = LoginUserUseCase(user_repository, refresh_token_repository)
    tokens = await login_use_case.execute(email=email, password=password)

    return CreatedUser(
        user=result.user,
        password=password,
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
    )


async def create_ride(
    session: AsyncSession,
    *,
    rider_id: UUID,
    pickup_latitude: float = 30.05,
    pickup_longitude: float = 31.23,
    dropoff_latitude: float = 30.06,
    dropoff_longitude: float = 31.25,
    tier: RideTier = RideTier.ECONOMY,
) -> Ride:
    """Create a persisted ride (status=REQUESTED) via the app's own RequestRideUseCase."""
    ride_repository = SqlAlchemyRideRepository(session)
    use_case = RequestRideUseCase(ride_repository)
    return await use_case.execute(
        rider_id=rider_id,
        pickup_latitude=pickup_latitude,
        pickup_longitude=pickup_longitude,
        dropoff_latitude=dropoff_latitude,
        dropoff_longitude=dropoff_longitude,
        tier=tier,
    )
