from fastapi import APIRouter

from app.api.dependencies import (
    CurrentUserDep,
    DriverProfileRepositoryDep,
    RatingRepositoryDep,
    UpdateProfileUseCaseDep,
)
from app.api.v1.schemas.user import DriverProfileResponse, ProfileUpdateRequest, UserResponse
from app.application.rating.repository import RatingRepository
from app.domain.driver_profile.entities import DriverProfile
from app.domain.user.entities import User

router = APIRouter(prefix="/users", tags=["users"])


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


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: ProfileUpdateRequest,
    current_user: CurrentUserDep,
    use_case: UpdateProfileUseCaseDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> UserResponse:
    user = await use_case.execute(
        user_id=current_user.id,
        full_name=request.full_name,
        phone_number=request.phone_number,
    )
    driver_profile = await driver_profile_repository.get_by_user_id(user.id)
    return await _to_response(user, driver_profile, rating_repository)
