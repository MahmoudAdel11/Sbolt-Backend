from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies import (
    AcceptRideUseCaseDep,
    CancelRideUseCaseDep,
    CompleteRideUseCaseDep,
    CurrentUserDep,
    DriverProfileRepositoryDep,
    DriverUserDep,
    GetAvailableRidesUseCaseDep,
    GetRideDetailUseCaseDep,
    GetRideHistoryUseCaseDep,
    RatingRepositoryDep,
    RequestRideUseCaseDep,
    StartRideUseCaseDep,
    SubmitRatingUseCaseDep,
    UserRepositoryDep,
)
from app.api.v1.schemas.rating import RatingCreateRequest, RatingResponse
from app.api.v1.schemas.ride import (
    AvailableRidesQuery,
    RideDriverSummary,
    RideHistoryQuery,
    RideHistoryResponse,
    RideRequestSchema,
    RideResponse,
)
from app.application.driver_profile.repository import DriverProfileRepository
from app.application.rating.repository import RatingRepository
from app.application.user.repository import UserRepository
from app.domain.rating.entities import Rating
from app.domain.ride.entities import Ride

router = APIRouter(prefix="/rides", tags=["rides"])


async def _build_driver_summary(
    driver_id: UUID,
    user_repository: UserRepository,
    driver_profile_repository: DriverProfileRepository,
    rating_repository: RatingRepository,
) -> RideDriverSummary | None:
    user = await user_repository.get_by_id(driver_id)
    driver_profile = await driver_profile_repository.get_by_user_id(driver_id)
    if user is None or driver_profile is None:
        return None

    average_rating, rating_count = await rating_repository.get_average_and_count(driver_id)
    return RideDriverSummary(
        name=user.full_name,
        vehicle_type=driver_profile.vehicle_type,
        vehicle_color=driver_profile.vehicle_color,
        license_plate=driver_profile.license_plate,
        average_rating=average_rating,
        rating_count=rating_count,
    )


async def _to_response(
    ride: Ride,
    user_repository: UserRepository,
    driver_profile_repository: DriverProfileRepository,
    rating_repository: RatingRepository,
) -> RideResponse:
    driver_summary = None
    if ride.driver_id is not None:
        driver_summary = await _build_driver_summary(
            ride.driver_id, user_repository, driver_profile_repository, rating_repository
        )

    return RideResponse(
        id=ride.id,
        rider_id=ride.rider_id,
        driver_id=ride.driver_id,
        driver=driver_summary,
        status=ride.status,
        tier=ride.tier,
        fare=ride.fare,
        pickup_latitude=ride.pickup_latitude,
        pickup_longitude=ride.pickup_longitude,
        dropoff_latitude=ride.dropoff_latitude,
        dropoff_longitude=ride.dropoff_longitude,
        requested_at=ride.requested_at,
        accepted_at=ride.accepted_at,
        completed_at=ride.completed_at,
        cancelled_at=ride.cancelled_at,
    )


@router.post("", response_model=RideResponse, status_code=status.HTTP_201_CREATED)
async def request_ride(
    request: RideRequestSchema,
    current_user: CurrentUserDep,
    use_case: RequestRideUseCaseDep,
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RideResponse:
    ride = await use_case.execute(
        rider_id=current_user.id,
        pickup_latitude=request.pickup_latitude,
        pickup_longitude=request.pickup_longitude,
        dropoff_latitude=request.dropoff_latitude,
        dropoff_longitude=request.dropoff_longitude,
        tier=request.tier,
    )
    return await _to_response(ride, user_repository, driver_profile_repository, rating_repository)


@router.get("/history", response_model=RideHistoryResponse)
async def get_ride_history(
    current_user: CurrentUserDep,
    use_case: GetRideHistoryUseCaseDep,
    query: Annotated[RideHistoryQuery, Depends()],
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
    view: Annotated[Literal["rider", "driver"], Query(alias="as")] = "rider",
) -> RideHistoryResponse:
    rides, has_more = await use_case.execute(
        user_id=current_user.id, view=view, limit=query.limit, offset=query.offset
    )
    # Sequential per-ride lookups, not batched - simplest correct thing at this
    # project's data volume (history pages cap at 100 rides), same "simplicity
    # over premature optimization" call as the average-rating query itself.
    items = [
        await _to_response(ride, user_repository, driver_profile_repository, rating_repository)
        for ride in rides
    ]
    return RideHistoryResponse(items=items, has_more=has_more)


@router.get("/available", response_model=list[RideResponse])
async def get_available_rides(
    current_user: DriverUserDep,
    use_case: GetAvailableRidesUseCaseDep,
    query: Annotated[AvailableRidesQuery, Depends()],
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> list[RideResponse]:
    rides = await use_case.execute(
        driver_id=current_user.id, latitude=query.lat, longitude=query.lng
    )
    # Available rides are unassigned by definition (driver_id IS NULL), so
    # _to_response's driver_id guard means this never actually queries for a
    # driver summary - the deps are only here for _to_response's uniform signature.
    return [
        await _to_response(ride, user_repository, driver_profile_repository, rating_repository)
        for ride in rides
    ]


@router.get("/{ride_id}", response_model=RideResponse)
async def get_ride_detail(
    ride_id: UUID,
    current_user: CurrentUserDep,
    use_case: GetRideDetailUseCaseDep,
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, user_id=current_user.id)
    return await _to_response(ride, user_repository, driver_profile_repository, rating_repository)


@router.post("/{ride_id}/accept", response_model=RideResponse)
async def accept_ride(
    ride_id: UUID,
    current_user: DriverUserDep,
    use_case: AcceptRideUseCaseDep,
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, driver_id=current_user.id)
    return await _to_response(ride, user_repository, driver_profile_repository, rating_repository)


@router.post("/{ride_id}/start", response_model=RideResponse)
async def start_ride(
    ride_id: UUID,
    current_user: DriverUserDep,
    use_case: StartRideUseCaseDep,
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, driver_id=current_user.id)
    return await _to_response(ride, user_repository, driver_profile_repository, rating_repository)


@router.post("/{ride_id}/cancel", response_model=RideResponse)
async def cancel_ride(
    ride_id: UUID,
    current_user: CurrentUserDep,
    use_case: CancelRideUseCaseDep,
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, user_id=current_user.id)
    return await _to_response(ride, user_repository, driver_profile_repository, rating_repository)


@router.post("/{ride_id}/complete", response_model=RideResponse)
async def complete_ride(
    ride_id: UUID,
    current_user: DriverUserDep,
    use_case: CompleteRideUseCaseDep,
    user_repository: UserRepositoryDep,
    driver_profile_repository: DriverProfileRepositoryDep,
    rating_repository: RatingRepositoryDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, driver_id=current_user.id)
    return await _to_response(ride, user_repository, driver_profile_repository, rating_repository)


def _to_rating_response(rating: Rating) -> RatingResponse:
    return RatingResponse(
        id=rating.id,
        ride_id=rating.ride_id,
        rider_id=rating.rider_id,
        driver_id=rating.driver_id,
        score=rating.score,
        created_at=rating.created_at,
    )


@router.post(
    "/{ride_id}/rating", response_model=RatingResponse, status_code=status.HTTP_201_CREATED
)
async def submit_rating(
    ride_id: UUID,
    request: RatingCreateRequest,
    current_user: CurrentUserDep,
    use_case: SubmitRatingUseCaseDep,
) -> RatingResponse:
    rating = await use_case.execute(ride_id=ride_id, rider_id=current_user.id, score=request.score)
    return _to_rating_response(rating)
