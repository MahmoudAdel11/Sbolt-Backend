from fastapi import APIRouter, Request, status

from app.api.dependencies import (
    CurrentUserDep,
    DriverProfileRepositoryDep,
    LoginUserUseCaseDep,
    RegisterUserUseCaseDep,
)
from app.api.v1.schemas.user import (
    DriverProfileResponse,
    LoginRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.domain.driver_profile.entities import DriverProfile
from app.domain.user.entities import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_response(user: User, driver_profile: DriverProfile | None) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        driver_profile=(
            DriverProfileResponse(is_online=driver_profile.is_online) if driver_profile else None
        ),
        created_at=user.created_at,
    )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_settings().rate_limit_auth)
async def register(
    request: Request,
    body: UserRegisterRequest,
    use_case: RegisterUserUseCaseDep,
    driver_profile_repository: DriverProfileRepositoryDep,
) -> UserResponse:
    user = await use_case.execute(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone_number=body.phone_number,
        register_as_driver=body.register_as_driver,
    )
    driver_profile = await driver_profile_repository.get_by_user_id(user.id)
    return _to_response(user, driver_profile)


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_settings().rate_limit_auth)
async def login(
    request: Request, body: LoginRequest, use_case: LoginUserUseCaseDep
) -> TokenResponse:
    access_token = await use_case.execute(email=body.email, password=body.password)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: CurrentUserDep, driver_profile_repository: DriverProfileRepositoryDep
) -> UserResponse:
    driver_profile = await driver_profile_repository.get_by_user_id(current_user.id)
    return _to_response(current_user, driver_profile)


# TODO(phase-3): refresh tokens.
