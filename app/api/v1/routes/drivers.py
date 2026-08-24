from fastapi import APIRouter

from app.api.dependencies import (
    DriverUserDep,
    RatingRepositoryDep,
    SetDriverStatusUseCaseDep,
    UpdateDriverVehicleUseCaseDep,
)
from app.api.v1.schemas.driver import DriverStatusUpdateRequest, DriverVehicleUpdateRequest
from app.api.v1.schemas.user import DriverProfileResponse, UserResponse
from app.application.rating.repository import RatingRepository
from app.domain.driver_profile.entities import DriverProfile
from app.domain.user.entities import User

router = APIRouter(prefix="/drivers", tags=["drivers"])


async def _to_response(
    user: User, driver_profile: DriverProfile, rating_repository: RatingRepository
) -> UserResponse:
    average_rating, rating_count = await rating_repository.get_average_and_count(user.id)
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        driver_profile=DriverProfileResponse(
            is_online=driver_profile.is_online,
            vehicle_type=driver_profile.vehicle_type,
            vehicle_color=driver_profile.vehicle_color,
            license_plate=driver_profile.license_plate,
            average_rating=average_rating,
            rating_count=rating_count,
        ),
        created_at=user.created_at,
    )


@router.patch("/me/status", response_model=UserResponse)
async def update_driver_status(
    request: DriverStatusUpdateRequest,
    current_user: DriverUserDep,
    use_case: SetDriverStatusUseCaseDep,
    rating_repository: RatingRepositoryDep,
) -> UserResponse:
    driver_profile = await use_case.execute(user_id=current_user.id, is_online=request.is_online)
    return await _to_response(current_user, driver_profile, rating_repository)


@router.patch("/me/vehicle", response_model=UserResponse)
async def update_driver_vehicle(
    request: DriverVehicleUpdateRequest,
    current_user: DriverUserDep,
    use_case: UpdateDriverVehicleUseCaseDep,
    rating_repository: RatingRepositoryDep,
) -> UserResponse:
    driver_profile = await use_case.execute(
        user_id=current_user.id,
        vehicle_type=request.vehicle_type,
        vehicle_color=request.vehicle_color,
        license_plate=request.license_plate,
    )
    return await _to_response(current_user, driver_profile, rating_repository)
