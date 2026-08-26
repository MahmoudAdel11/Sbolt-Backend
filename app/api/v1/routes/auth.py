from fastapi import APIRouter, Request, status

from app.api.dependencies import (
    CurrentUserDep,
    DriverProfileRepositoryDep,
    LoginUserUseCaseDep,
    LogoutUseCaseDep,
    RatingRepositoryDep,
    RefreshAccessTokenUseCaseDep,
    RegisterUserUseCaseDep,
)
from app.api.v1.schemas.user import (
    AccessTokenResponse,
    DriverProfileResponse,
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterResponse,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.application.rating.repository import RatingRepository
from app.core.config import get_settings
from app.core.rate_limit import limiter
from app.domain.driver_profile.entities import DriverProfile
from app.domain.user.entities import User

router = APIRouter(prefix="/auth", tags=["auth"])


async def _to_response(
    user: User, driver_profile: DriverProfile | None, rating_repository: RatingRepository
) -> UserResponse:
    driver_profile_response = None
    if driver_profile:
        average_rating, rating_count = await rating_repository.get_average_and_count(user.id)
        driver_profile_response = DriverProfileResponse(
            is_online=driver_profile.is_online,
            vehicle_type=driver_profile.vehicle_type,
            vehicle_color=driver_profile.vehicle_color,
            license_plate=driver_profile.license_plate,
            scooter_type=driver_profile.scooter_type,
            average_rating=average_rating,
            rating_count=rating_count,
        )
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        driver_profile=driver_profile_response,
        created_at=user.created_at,
    )


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_settings().rate_limit_auth)
async def register(
    request: Request,
    body: UserRegisterRequest,
    use_case: RegisterUserUseCaseDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RegisterResponse:
    result = await use_case.execute(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone_number=body.phone_number,
        register_as_driver=body.register_as_driver,
        scooter_type=body.scooter_type,
    )
    driver_profile = await driver_profile_repository.get_by_user_id(result.user.id)
    user_response = await _to_response(result.user, driver_profile, rating_repository)
    return RegisterResponse(
        user=user_response,
        access_token=result.tokens.access_token,
        refresh_token=result.tokens.refresh_token,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_settings().rate_limit_auth)
async def login(
    request: Request, body: LoginRequest, use_case: LoginUserUseCaseDep
) -> TokenResponse:
    tokens = await use_case.execute(email=body.email, password=body.password)
    return TokenResponse(access_token=tokens.access_token, refresh_token=tokens.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(
    current_user: CurrentUserDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> UserResponse:
    driver_profile = await driver_profile_repository.get_by_user_id(current_user.id)
    return await _to_response(current_user, driver_profile, rating_repository)


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    body: RefreshRequest, use_case: RefreshAccessTokenUseCaseDep
) -> AccessTokenResponse:
    access_token = await use_case.execute(refresh_token=body.refresh_token)
    return AccessTokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(body: LogoutRequest, use_case: LogoutUseCaseDep) -> None:
    await use_case.execute(refresh_token=body.refresh_token)
