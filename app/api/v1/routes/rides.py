from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.dependencies import (
    AcceptRideUseCaseDep,
    CancelRideUseCaseDep,
    CompleteRideUseCaseDep,
    CurrentUserDep,
    DriverUserDep,
    GetAvailableRidesUseCaseDep,
    GetRideDetailUseCaseDep,
    GetRideHistoryUseCaseDep,
    RequestRideUseCaseDep,
)
from app.api.v1.schemas.ride import (
    AvailableRidesQuery,
    RideHistoryQuery,
    RideHistoryResponse,
    RideRequestSchema,
    RideResponse,
)
from app.domain.ride.entities import Ride

router = APIRouter(prefix="/rides", tags=["rides"])


def _to_response(ride: Ride) -> RideResponse:
    return RideResponse(
        id=ride.id,
        rider_id=ride.rider_id,
        driver_id=ride.driver_id,
        status=ride.status,
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
) -> RideResponse:
    ride = await use_case.execute(
        rider_id=current_user.id,
        pickup_latitude=request.pickup_latitude,
        pickup_longitude=request.pickup_longitude,
        dropoff_latitude=request.dropoff_latitude,
        dropoff_longitude=request.dropoff_longitude,
    )
    return _to_response(ride)


@router.get("/history", response_model=RideHistoryResponse)
async def get_ride_history(
    current_user: CurrentUserDep,
    use_case: GetRideHistoryUseCaseDep,
    query: Annotated[RideHistoryQuery, Depends()],
) -> RideHistoryResponse:
    rides, has_more = await use_case.execute(
        user=current_user, limit=query.limit, offset=query.offset
    )
    return RideHistoryResponse(items=[_to_response(ride) for ride in rides], has_more=has_more)


@router.get("/available", response_model=list[RideResponse])
async def get_available_rides(
    current_user: DriverUserDep,
    use_case: GetAvailableRidesUseCaseDep,
    query: Annotated[AvailableRidesQuery, Depends()],
) -> list[RideResponse]:
    rides = await use_case.execute(driver=current_user, latitude=query.lat, longitude=query.lng)
    return [_to_response(ride) for ride in rides]


@router.get("/{ride_id}", response_model=RideResponse)
async def get_ride_detail(
    ride_id: UUID,
    current_user: CurrentUserDep,
    use_case: GetRideDetailUseCaseDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, user_id=current_user.id)
    return _to_response(ride)


@router.post("/{ride_id}/accept", response_model=RideResponse)
async def accept_ride(
    ride_id: UUID,
    current_user: DriverUserDep,
    use_case: AcceptRideUseCaseDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, driver_id=current_user.id)
    return _to_response(ride)


@router.post("/{ride_id}/cancel", response_model=RideResponse)
async def cancel_ride(
    ride_id: UUID,
    current_user: CurrentUserDep,
    use_case: CancelRideUseCaseDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, user_id=current_user.id)
    return _to_response(ride)


@router.post("/{ride_id}/complete", response_model=RideResponse)
async def complete_ride(
    ride_id: UUID,
    current_user: DriverUserDep,
    use_case: CompleteRideUseCaseDep,
) -> RideResponse:
    ride = await use_case.execute(ride_id=ride_id, driver_id=current_user.id)
    return _to_response(ride)
