from uuid import UUID

from fastapi import APIRouter, status

from app.api.dependencies import (
    CreateFavoritePlaceUseCaseDep,
    CurrentUserDep,
    DeleteFavoritePlaceUseCaseDep,
    ListFavoritePlacesUseCaseDep,
    UpdateFavoritePlaceUseCaseDep,
)
from app.api.v1.schemas.favorite_place import (
    FavoritePlaceCreateRequest,
    FavoritePlaceResponse,
    FavoritePlaceUpdateRequest,
)
from app.domain.favorite_place.entities import FavoritePlace

router = APIRouter(prefix="/favorite-places", tags=["favorite-places"])


def _to_response(favorite_place: FavoritePlace) -> FavoritePlaceResponse:
    return FavoritePlaceResponse(
        id=favorite_place.id,
        user_id=favorite_place.user_id,
        label=favorite_place.label,
        address=favorite_place.address,
        latitude=favorite_place.latitude,
        longitude=favorite_place.longitude,
        created_at=favorite_place.created_at,
    )


@router.post("", response_model=FavoritePlaceResponse, status_code=status.HTTP_201_CREATED)
async def create_favorite_place(
    request: FavoritePlaceCreateRequest,
    current_user: CurrentUserDep,
    use_case: CreateFavoritePlaceUseCaseDep,
) -> FavoritePlaceResponse:
    favorite_place = await use_case.execute(
        user_id=current_user.id,
        label=request.label,
        address=request.address,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    return _to_response(favorite_place)


@router.get("", response_model=list[FavoritePlaceResponse])
async def list_favorite_places(
    current_user: CurrentUserDep,
    use_case: ListFavoritePlacesUseCaseDep,
) -> list[FavoritePlaceResponse]:
    favorite_places = await use_case.execute(user_id=current_user.id)
    return [_to_response(favorite_place) for favorite_place in favorite_places]


@router.patch("/{favorite_place_id}", response_model=FavoritePlaceResponse)
async def update_favorite_place(
    favorite_place_id: UUID,
    request: FavoritePlaceUpdateRequest,
    current_user: CurrentUserDep,
    use_case: UpdateFavoritePlaceUseCaseDep,
) -> FavoritePlaceResponse:
    favorite_place = await use_case.execute(
        favorite_place_id=favorite_place_id,
        user_id=current_user.id,
        label=request.label,
        address=request.address,
        latitude=request.latitude,
        longitude=request.longitude,
    )
    return _to_response(favorite_place)


@router.delete("/{favorite_place_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_favorite_place(
    favorite_place_id: UUID,
    current_user: CurrentUserDep,
    use_case: DeleteFavoritePlaceUseCaseDep,
) -> None:
    await use_case.execute(favorite_place_id=favorite_place_id, user_id=current_user.id)
