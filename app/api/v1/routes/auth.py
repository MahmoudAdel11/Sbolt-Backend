from fastapi import APIRouter, Request, status

from app.api.dependencies import CurrentUserDep, LoginUserUseCaseDep, RegisterUserUseCaseDep
from app.api.v1.schemas.user import (
    LoginRequest,
    TokenResponse,
    UserRegisterRequest,
    UserResponse,
)
from app.core.config import get_settings
from app.core.rate_limit import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(get_settings().rate_limit_auth)
async def register(
    request: Request, body: UserRegisterRequest, use_case: RegisterUserUseCaseDep
) -> UserResponse:
    user = await use_case.execute(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        phone_number=body.phone_number,
        role=body.role,
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        role=user.role,
        is_online=user.is_online,
        created_at=user.created_at,
    )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_settings().rate_limit_auth)
async def login(
    request: Request, body: LoginRequest, use_case: LoginUserUseCaseDep
) -> TokenResponse:
    access_token = await use_case.execute(email=body.email, password=body.password)
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone_number=current_user.phone_number,
        is_active=current_user.is_active,
        role=current_user.role,
        is_online=current_user.is_online,
        created_at=current_user.created_at,
    )


# TODO(phase-3): refresh tokens.
