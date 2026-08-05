from fastapi import APIRouter

from app.api.dependencies import CurrentUserDep, UpdateProfileUseCaseDep
from app.api.v1.schemas.user import ProfileUpdateRequest, UserResponse

router = APIRouter(prefix="/users", tags=["users"])


@router.patch("/me", response_model=UserResponse)
async def update_me(
    request: ProfileUpdateRequest,
    current_user: CurrentUserDep,
    use_case: UpdateProfileUseCaseDep,
) -> UserResponse:
    user = await use_case.execute(
        user_id=current_user.id,
        full_name=request.full_name,
        phone_number=request.phone_number,
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone_number=user.phone_number,
        is_active=user.is_active,
        created_at=user.created_at,
    )
