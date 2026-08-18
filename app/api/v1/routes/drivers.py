from fastapi import APIRouter

from app.api.dependencies import DriverUserDep, SetDriverStatusUseCaseDep
from app.api.v1.schemas.driver import DriverStatusUpdateRequest
from app.api.v1.schemas.user import UserResponse

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.patch("/me/status", response_model=UserResponse)
async def update_driver_status(
    request: DriverStatusUpdateRequest,
    current_user: DriverUserDep,
    use_case: SetDriverStatusUseCaseDep,
) -> UserResponse:
    user = await use_case.execute(user_id=current_user.id, is_online=request.is_online)
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
