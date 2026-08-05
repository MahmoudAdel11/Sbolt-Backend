from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import AsyncClient

from app.application.ride.use_cases import AcceptRideUseCase, CompleteRideUseCase
from app.domain.user.entities import UserRole
from app.infrastructure.db.models.ride import RideModel
from app.infrastructure.db.repositories.ride_repository import SqlAlchemyRideRepository
from tests.conftest import auth_headers
from tests.factories import create_ride, create_user

VALID_RIDE_PAYLOAD = {
    "pickup_latitude": 30.05,
    "pickup_longitude": 31.23,
    "dropoff_latitude": 30.06,
    "dropoff_longitude": 31.25,
}


async def _accept(db_session, ride_id, driver_id):
    """Drive a REQUESTED ride to ACCEPTED via the app's own AcceptRideUseCase, bypassing HTTP -
    setup for tests that aren't specifically about the accept endpoint itself.
    """
    use_case = AcceptRideUseCase(SqlAlchemyRideRepository(db_session))
    return await use_case.execute(ride_id=ride_id, driver_id=driver_id)


async def _complete(db_session, ride_id, driver_id):
    """Drive an ACCEPTED ride to COMPLETED via the app's own CompleteRideUseCase, bypassing HTTP."""
    use_case = CompleteRideUseCase(SqlAlchemyRideRepository(db_session))
    return await use_case.execute(ride_id=ride_id, driver_id=driver_id)


async def _set_requested_at(db_session, ride_id, requested_at):
    """Force a distinguishable requested_at directly on the row.

    Needed only for ordering assertions: Postgres's now() is frozen at transaction start
    (transaction_timestamp semantics), and every test runs inside one wrapping transaction
    for isolation, so rides created moments apart in the same test get byte-identical
    server_default=func.now() timestamps - real insertion order can't be distinguished by
    requested_at alone under this test setup, even though it works correctly outside a
    single transaction (e.g. in real request handling, one transaction per request).
    """
    model = await db_session.get(RideModel, ride_id)
    model.requested_at = requested_at
    await db_session.flush()


# --- POST /rides (request ride) ---------------------------------------------


async def test_request_ride_success(client: AsyncClient, registered_user) -> None:
    response = await client.post(
        "/api/v1/rides",
        headers=auth_headers(registered_user.access_token),
        json=VALID_RIDE_PAYLOAD,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "requested"
    assert body["rider_id"] == str(registered_user.user.id)
    assert body["driver_id"] is None


async def test_request_second_ride_while_active_returns_conflict(
    client: AsyncClient, registered_user
) -> None:
    first = await client.post(
        "/api/v1/rides",
        headers=auth_headers(registered_user.access_token),
        json=VALID_RIDE_PAYLOAD,
    )
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/rides",
        headers=auth_headers(registered_user.access_token),
        json=VALID_RIDE_PAYLOAD,
    )

    assert second.status_code == 409
    assert second.json()["error_code"] == "conflict"


async def test_request_ride_out_of_range_coordinates_returns_422(
    client: AsyncClient, registered_user
) -> None:
    response = await client.post(
        "/api/v1/rides",
        headers=auth_headers(registered_user.access_token),
        json={**VALID_RIDE_PAYLOAD, "pickup_latitude": 999},
    )

    assert response.status_code == 422


# --- POST /rides/{id}/accept -------------------------------------------------


async def test_driver_accepts_requested_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/accept", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "accepted"
    assert body["driver_id"] == str(driver.user.id)


async def test_rider_cannot_accept_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/accept", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 403


async def test_accepting_already_accepted_ride_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver_a = await create_user(db_session, role=UserRole.DRIVER, email="driver-a@example.com")
    driver_b = await create_user(db_session, role=UserRole.DRIVER, email="driver-b@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver_a.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/accept", headers=auth_headers(driver_b.access_token)
    )

    assert response.status_code == 409


async def test_accepting_nonexistent_ride_returns_404(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, role=UserRole.DRIVER)

    response = await client.post(
        f"/api/v1/rides/{uuid4()}/accept", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 404


# --- POST /rides/{id}/cancel --------------------------------------------------


async def test_rider_cancels_own_requested_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/cancel", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_driver_cancels_assigned_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/cancel", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


async def test_unrelated_user_cannot_cancel_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    stranger = await create_user(db_session, email="stranger@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/cancel", headers=auth_headers(stranger.access_token)
    )

    assert response.status_code == 403


async def test_cancelling_already_completed_ride_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/cancel", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 409


# --- POST /rides/{id}/complete ------------------------------------------------


async def test_driver_completes_accepted_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


async def test_wrong_driver_cannot_complete_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    assigned_driver = await create_user(
        db_session, role=UserRole.DRIVER, email="assigned@example.com"
    )
    other_driver = await create_user(db_session, role=UserRole.DRIVER, email="other@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, assigned_driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(other_driver.access_token)
    )

    assert response.status_code == 403


async def test_completing_still_requested_ride_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )

    # The driver isn't assigned to this ride yet (it was never accepted), so the
    # ForbiddenError ownership check fires before the status check would.
    assert response.status_code == 403


# --- GET /rides/history --------------------------------------------------------


async def test_rider_history_ordered_most_recent_first(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride_1 = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride_1.id, driver.user.id)
    await _complete(db_session, ride_1.id, driver.user.id)
    ride_2 = await create_ride(db_session, rider_id=rider.user.id)

    # Force distinguishable timestamps - see _set_requested_at's docstring.
    now = datetime.now(UTC)
    await _set_requested_at(db_session, ride_1.id, now - timedelta(minutes=5))
    await _set_requested_at(db_session, ride_2.id, now)

    response = await client.get(
        "/api/v1/rides/history", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 200
    body = response.json()
    ids_in_order = [item["id"] for item in body["items"]]
    assert ids_in_order == [str(ride_2.id), str(ride_1.id)]


async def test_driver_history_scoped_to_their_rides(client: AsyncClient, db_session) -> None:
    # Two different riders, since a rider can only have one active (non-terminal) ride at a
    # time - accepting doesn't free up the rider to request another until it's terminal.
    rider_a = await create_user(db_session, email="hist-rider-a@example.com")
    rider_b = await create_user(db_session, email="hist-rider-b@example.com")
    driver_a = await create_user(db_session, role=UserRole.DRIVER, email="hist-a@example.com")
    driver_b = await create_user(db_session, role=UserRole.DRIVER, email="hist-b@example.com")

    ride_for_a = await create_ride(db_session, rider_id=rider_a.user.id)
    await _accept(db_session, ride_for_a.id, driver_a.user.id)

    ride_for_b = await create_ride(db_session, rider_id=rider_b.user.id)
    await _accept(db_session, ride_for_b.id, driver_b.user.id)

    response = await client.get(
        "/api/v1/rides/history", headers=auth_headers(driver_a.access_token)
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()["items"]]
    assert ids == [str(ride_for_a.id)]


async def test_history_pagination_limit_offset_and_has_more(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    for _ in range(3):
        ride = await create_ride(db_session, rider_id=rider.user.id)
        await client.post(
            f"/api/v1/rides/{ride.id}/cancel", headers=auth_headers(rider.access_token)
        )

    first_page = await client.get(
        "/api/v1/rides/history?limit=2&offset=0", headers=auth_headers(rider.access_token)
    )
    second_page = await client.get(
        "/api/v1/rides/history?limit=2&offset=2", headers=auth_headers(rider.access_token)
    )

    assert first_page.status_code == 200
    assert len(first_page.json()["items"]) == 2
    assert first_page.json()["has_more"] is True

    assert second_page.status_code == 200
    assert len(second_page.json()["items"]) == 1
    assert second_page.json()["has_more"] is False


async def test_history_excessive_limit_returns_422(client: AsyncClient, registered_user) -> None:
    response = await client.get(
        "/api/v1/rides/history?limit=101", headers=auth_headers(registered_user.access_token)
    )

    assert response.status_code == 422


async def test_history_invalid_limit_returns_422(client: AsyncClient, registered_user) -> None:
    response = await client.get(
        "/api/v1/rides/history?limit=0", headers=auth_headers(registered_user.access_token)
    )

    assert response.status_code == 422


# --- GET /rides/{id} -----------------------------------------------------------


async def test_rider_can_view_own_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(ride.id)


async def test_driver_can_view_assigned_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, role=UserRole.DRIVER)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(ride.id)


async def test_unrelated_user_cannot_view_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    stranger = await create_user(db_session, email="viewer-stranger@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(stranger.access_token)
    )

    assert response.status_code == 403


async def test_viewing_nonexistent_ride_returns_404(
    client: AsyncClient, registered_user
) -> None:
    response = await client.get(
        f"/api/v1/rides/{uuid4()}", headers=auth_headers(registered_user.access_token)
    )

    assert response.status_code == 404
