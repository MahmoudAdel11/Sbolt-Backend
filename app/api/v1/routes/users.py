from fastapi import APIRouter

from app.api.dependencies import CurrentUserDep, DriverProfileRepositoryDep, UpdateProfileUseCaseDep
from app.api.v1.schemas.user import DriverProfileResponse, ProfileUpdateRequest, UserResponse
from app.domain.driver_profile.entities import DriverProfile
from app.domain.user.entities import User

router = APIRouter(prefix="/users", tags=["users"])


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


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: ProfileUpdateRequest,
    current_user: CurrentUserDep,
    use_case: UpdateProfileUseCaseDep,
    driver_profile_repository: DriverProfileRepositoryDep,
) -> UserResponse:
    user = await use_case.execute(
        user_id=current_user.id,
        full_name=request.full_name,
        phone_number=request.phone_number,
    )
    driver_profile = await driver_profile_repository.get_by_user_id(user.id)
    return _to_response(user, driver_profile)
