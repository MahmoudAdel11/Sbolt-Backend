from fastapi import APIRouter

from app.api.dependencies import DriverUserDep, SetDriverStatusUseCaseDep
from app.api.v1.schemas.driver import DriverStatusUpdateRequest
from app.api.v1.schemas.user import DriverProfileResponse, UserResponse

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.patch("/me/status", response_model=UserResponse)
async def update_driver_status(
    request: DriverStatusUpdateRequest,
    current_user: DriverUserDep,
    use_case: SetDriverStatusUseCaseDep,
) -> UserResponse:
    driver_profile = await use_case.execute(user_id=current_user.id, is_online=request.is_online)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        phone_number=current_user.phone_number,
        is_active=current_user.is_active,
        driver_profile=DriverProfileResponse(is_online=driver_profile.is_online),
        created_at=current_user.created_at,
    )
