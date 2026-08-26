from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.driver_profile.repository import DriverProfileRepository
from app.application.favorite_place.repository import FavoritePlaceRepository
from app.application.favorite_place.use_cases import (
    CreateFavoritePlaceUseCase,
    DeleteFavoritePlaceUseCase,
    ListFavoritePlacesUseCase,
    UpdateFavoritePlaceUseCase,
)
from app.application.rating.repository import RatingRepository
from app.application.refresh_token.repository import RefreshTokenRepository
from app.application.refresh_token.use_cases import LogoutUseCase, RefreshAccessTokenUseCase
from app.application.ride.repository import RideRepository
from app.application.ride.use_cases import (
    AcceptRideUseCase,
    CancelRideUseCase,
    CompleteRideUseCase,
    GetActiveRideUseCase,
    GetAvailableRidesUseCase,
    GetRideDetailUseCase,
    GetRideHistoryUseCase,
    RequestRideUseCase,
    StartRideUseCase,
    SubmitRatingUseCase,
)
from app.application.user.repository import UserRepository
from app.application.user.use_cases import (
    LoginUserUseCase,
    RegisterUserUseCase,
    SetDriverStatusUseCase,
    UpdateDriverVehicleUseCase,
    UpdateProfileUseCase,
)
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.jwt import decode_access_token
from app.domain.user.entities import User
from app.infrastructure.db.repositories.driver_profile_repository import (
    SqlAlchemyDriverProfileRepository,
)
from app.infrastructure.db.repositories.favorite_place_repository import (
    SqlAlchemyFavoritePlaceRepository,
)
from app.infrastructure.db.repositories.rating_repository import SqlAlchemyRatingRepository
from app.infrastructure.db.repositories.refresh_token_repository import (
    SqlAlchemyRefreshTokenRepository,
)
from app.infrastructure.db.repositories.ride_repository import SqlAlchemyRideRepository
from app.infrastructure.db.repositories.user_repository import SqlAlchemyUserRepository
from app.infrastructure.db.session import get_db_session

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def get_user_repository(session: DbSession) -> UserRepository:
    return SqlAlchemyUserRepository(session)


UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]


def get_driver_profile_repository(session: DbSession) -> DriverProfileRepository:
    return SqlAlchemyDriverProfileRepository(session)


DriverProfileRepositoryDep = Annotated[
    DriverProfileRepository, Depends(get_driver_profile_repository)
]


def get_refresh_token_repository(session: DbSession) -> RefreshTokenRepository:
    return SqlAlchemyRefreshTokenRepository(session)


RefreshTokenRepositoryDep = Annotated[
    RefreshTokenRepository, Depends(get_refresh_token_repository)
]


def get_register_use_case(
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    refresh_token_repository: RefreshTokenRepositoryDep,
) -> RegisterUserUseCase:
    return RegisterUserUseCase(user_repository, driver_profile_repository, refresh_token_repository)


RegisterUserUseCaseDep = Annotated[RegisterUserUseCase, Depends(get_register_use_case)]


def get_login_use_case(
    user_repository: UserRepositoryDep, refresh_token_repository: RefreshTokenRepositoryDep
) -> LoginUserUseCase:
    return LoginUserUseCase(user_repository, refresh_token_repository)


LoginUserUseCaseDep = Annotated[LoginUserUseCase, Depends(get_login_use_case)]


def get_refresh_access_token_use_case(
    refresh_token_repository: RefreshTokenRepositoryDep,
    user_repository: UserRepositoryDep,
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(refresh_token_repository, user_repository)


RefreshAccessTokenUseCaseDep = Annotated[
    RefreshAccessTokenUseCase, Depends(get_refresh_access_token_use_case)
]


def get_logout_use_case(refresh_token_repository: RefreshTokenRepositoryDep) -> LogoutUseCase:
    return LogoutUseCase(refresh_token_repository)


LogoutUseCaseDep = Annotated[LogoutUseCase, Depends(get_logout_use_case)]

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repository: UserRepositoryDep,
) -> User:
    payload = decode_access_token(token)
    subject = payload.get("sub")
    if subject is None:
        raise UnauthorizedError("Invalid or expired token.")

    try:
        user_id = UUID(subject)
    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc

    user = await user_repository.get_by_id(user_id)
    if user is None:
        raise UnauthorizedError("User no longer exists.")

    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


async def require_driver(
    current_user: CurrentUserDep, driver_profile_repository: DriverProfileRepositoryDep
) -> User:
    driver_profile = await driver_profile_repository.get_by_user_id(current_user.id)
    if driver_profile is None:
        raise ForbiddenError("This action requires a driver account.")
    return current_user


DriverUserDep = Annotated[User, Depends(require_driver)]


def get_update_profile_use_case(user_repository: UserRepositoryDep) -> UpdateProfileUseCase:
    return UpdateProfileUseCase(user_repository)


UpdateProfileUseCaseDep = Annotated[UpdateProfileUseCase, Depends(get_update_profile_use_case)]


def get_set_driver_status_use_case(
    driver_profile_repository: DriverProfileRepositoryDep,
) -> SetDriverStatusUseCase:
    return SetDriverStatusUseCase(driver_profile_repository)


SetDriverStatusUseCaseDep = Annotated[
    SetDriverStatusUseCase, Depends(get_set_driver_status_use_case)
]


def get_update_driver_vehicle_use_case(
    driver_profile_repository: DriverProfileRepositoryDep,
) -> UpdateDriverVehicleUseCase:
    return UpdateDriverVehicleUseCase(driver_profile_repository)


UpdateDriverVehicleUseCaseDep = Annotated[
    UpdateDriverVehicleUseCase, Depends(get_update_driver_vehicle_use_case)
]


def get_rating_repository(session: DbSession) -> RatingRepository:
    return SqlAlchemyRatingRepository(session)


RatingRepositoryDep = Annotated[RatingRepository, Depends(get_rating_repository)]


def get_ride_repository(session: DbSession) -> RideRepository:
    return SqlAlchemyRideRepository(session)


RideRepositoryDep = Annotated[RideRepository, Depends(get_ride_repository)]


def get_request_ride_use_case(ride_repository: RideRepositoryDep) -> RequestRideUseCase:
    return RequestRideUseCase(ride_repository)


RequestRideUseCaseDep = Annotated[RequestRideUseCase, Depends(get_request_ride_use_case)]


def get_accept_ride_use_case(ride_repository: RideRepositoryDep) -> AcceptRideUseCase:
    return AcceptRideUseCase(ride_repository)


AcceptRideUseCaseDep = Annotated[AcceptRideUseCase, Depends(get_accept_ride_use_case)]


def get_cancel_ride_use_case(ride_repository: RideRepositoryDep) -> CancelRideUseCase:
    return CancelRideUseCase(ride_repository)


CancelRideUseCaseDep = Annotated[CancelRideUseCase, Depends(get_cancel_ride_use_case)]


def get_start_ride_use_case(ride_repository: RideRepositoryDep) -> StartRideUseCase:
    return StartRideUseCase(ride_repository)


StartRideUseCaseDep = Annotated[StartRideUseCase, Depends(get_start_ride_use_case)]


def get_complete_ride_use_case(ride_repository: RideRepositoryDep) -> CompleteRideUseCase:
    return CompleteRideUseCase(ride_repository)


CompleteRideUseCaseDep = Annotated[CompleteRideUseCase, Depends(get_complete_ride_use_case)]


def get_submit_rating_use_case(
    ride_repository: RideRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> SubmitRatingUseCase:
    return SubmitRatingUseCase(ride_repository, rating_repository)


SubmitRatingUseCaseDep = Annotated[SubmitRatingUseCase, Depends(get_submit_rating_use_case)]


def get_ride_history_use_case(
    ride_repository: RideRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
) -> GetRideHistoryUseCase:
    return GetRideHistoryUseCase(ride_repository, driver_profile_repository)


GetRideHistoryUseCaseDep = Annotated[GetRideHistoryUseCase, Depends(get_ride_history_use_case)]


def get_ride_detail_use_case(ride_repository: RideRepositoryDep) -> GetRideDetailUseCase:
    return GetRideDetailUseCase(ride_repository)


GetRideDetailUseCaseDep = Annotated[GetRideDetailUseCase, Depends(get_ride_detail_use_case)]


def get_active_ride_use_case(ride_repository: RideRepositoryDep) -> GetActiveRideUseCase:
    return GetActiveRideUseCase(ride_repository)


GetActiveRideUseCaseDep = Annotated[GetActiveRideUseCase, Depends(get_active_ride_use_case)]


def get_available_rides_use_case(
    ride_repository: RideRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
) -> GetAvailableRidesUseCase:
    return GetAvailableRidesUseCase(ride_repository, driver_profile_repository)


GetAvailableRidesUseCaseDep = Annotated[
    GetAvailableRidesUseCase, Depends(get_available_rides_use_case)
]


def get_favorite_place_repository(session: DbSession) -> FavoritePlaceRepository:
    return SqlAlchemyFavoritePlaceRepository(session)


FavoritePlaceRepositoryDep = Annotated[
    FavoritePlaceRepository, Depends(get_favorite_place_repository)
]


def get_create_favorite_place_use_case(
    favorite_place_repository: FavoritePlaceRepositoryDep,
) -> CreateFavoritePlaceUseCase:
    return CreateFavoritePlaceUseCase(favorite_place_repository)


CreateFavoritePlaceUseCaseDep = Annotated[
    CreateFavoritePlaceUseCase, Depends(get_create_favorite_place_use_case)
]


def get_list_favorite_places_use_case(
    favorite_place_repository: FavoritePlaceRepositoryDep,
) -> ListFavoritePlacesUseCase:
    return ListFavoritePlacesUseCase(favorite_place_repository)


ListFavoritePlacesUseCaseDep = Annotated[
    ListFavoritePlacesUseCase, Depends(get_list_favorite_places_use_case)
]


def get_update_favorite_place_use_case(
    favorite_place_repository: FavoritePlaceRepositoryDep,
) -> UpdateFavoritePlaceUseCase:
    return UpdateFavoritePlaceUseCase(favorite_place_repository)


UpdateFavoritePlaceUseCaseDep = Annotated[
    UpdateFavoritePlaceUseCase, Depends(get_update_favorite_place_use_case)
]


def get_delete_favorite_place_use_case(
    favorite_place_repository: FavoritePlaceRepositoryDep,
) -> DeleteFavoritePlaceUseCase:
    return DeleteFavoritePlaceUseCase(favorite_place_repository)


DeleteFavoritePlaceUseCaseDep = Annotated[
    DeleteFavoritePlaceUseCase, Depends(get_delete_favorite_place_use_case)
]
