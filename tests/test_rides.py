from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.application.ride.use_cases import (
    AcceptRideUseCase,
    CancelRideUseCase,
    CompleteRideUseCase,
    StartRideUseCase,
)
from app.application.user.use_cases import SetDriverStatusUseCase
from app.domain.ride.entities import RideTier
from app.infrastructure.db.models.ride import RideModel
from app.infrastructure.db.repositories.driver_profile_repository import (
    SqlAlchemyDriverProfileRepository,
)
from app.infrastructure.db.repositories.ride_repository import SqlAlchemyRideRepository
from tests.conftest import auth_headers
from tests.factories import create_ride, create_user

VALID_RIDE_PAYLOAD = {
    "pickup_latitude": 30.05,
    "pickup_longitude": 31.23,
    "dropoff_latitude": 30.06,
    "dropoff_longitude": 31.25,
    "tier": "economy",
}


async def _accept(db_session, ride_id, driver_id):
    """Drive a REQUESTED ride to ACCEPTED via the app's own AcceptRideUseCase, bypassing HTTP -
    setup for tests that aren't specifically about the accept endpoint itself.
    """
    use_case = AcceptRideUseCase(SqlAlchemyRideRepository(db_session))
    return await use_case.execute(ride_id=ride_id, driver_id=driver_id)


async def _start(db_session, ride_id, driver_id):
    """Drive an ACCEPTED ride to ONGOING via the app's own StartRideUseCase, bypassing HTTP."""
    use_case = StartRideUseCase(SqlAlchemyRideRepository(db_session))
    return await use_case.execute(ride_id=ride_id, driver_id=driver_id)


async def _complete(db_session, ride_id, driver_id):
    """Drive an ACCEPTED ride to COMPLETED, bypassing HTTP - via the app's own
    StartRideUseCase then CompleteRideUseCase, since ONGOING is now a required
    prerequisite for completion. Callers using this purely as setup (ratings,
    history, driver-summary tests, etc.) don't need to know that; tests that
    specifically exercise the start-required guard call the use cases directly
    instead of going through this helper."""
    await StartRideUseCase(SqlAlchemyRideRepository(db_session)).execute(
        ride_id=ride_id, driver_id=driver_id
    )
    use_case = CompleteRideUseCase(SqlAlchemyRideRepository(db_session))
    return await use_case.execute(ride_id=ride_id, driver_id=driver_id)


async def _cancel(db_session, ride_id, user_id):
    """Drive a ride to CANCELLED via the app's own CancelRideUseCase, bypassing HTTP."""
    use_case = CancelRideUseCase(SqlAlchemyRideRepository(db_session))
    return await use_case.execute(ride_id=ride_id, user_id=user_id)


async def _go_online(db_session, driver_id) -> None:
    """Sets is_online=True directly via the app's own SetDriverStatusUseCase, bypassing HTTP -
    setup for tests that aren't specifically about the status-toggle endpoint itself."""
    use_case = SetDriverStatusUseCase(SqlAlchemyDriverProfileRepository(db_session))
    await use_case.execute(user_id=driver_id, is_online=True)


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
    assert body["tier"] == "economy"
    assert body["fare"] > 0


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


async def test_request_ride_missing_tier_returns_422(
    client: AsyncClient, registered_user
) -> None:
    payload = {k: v for k, v in VALID_RIDE_PAYLOAD.items() if k != "tier"}

    response = await client.post(
        "/api/v1/rides",
        headers=auth_headers(registered_user.access_token),
        json=payload,
    )

    assert response.status_code == 422


async def test_request_ride_invalid_tier_returns_422(
    client: AsyncClient, registered_user
) -> None:
    response = await client.post(
        "/api/v1/rides",
        headers=auth_headers(registered_user.access_token),
        json={**VALID_RIDE_PAYLOAD, "tier": "luxury"},
    )

    assert response.status_code == 422


async def test_request_ride_computes_correct_fare_per_tier(
    client: AsyncClient, registered_user
) -> None:
    # Same pickup/dropoff as VALID_RIDE_PAYLOAD -> distance is fixed, so each
    # tier's fare is deterministic: base_price[tier] + distance_km * per_km_rate[tier].
    expected_fares = {"economy": 21.67, "comfort": 35.0, "premium": 55.56}

    for tier, expected_fare in expected_fares.items():
        response = await client.post(
            "/api/v1/rides",
            headers=auth_headers(registered_user.access_token),
            json={**VALID_RIDE_PAYLOAD, "tier": tier},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["tier"] == tier
        assert body["fare"] == pytest.approx(expected_fare, abs=0.01)

        # One active ride at a time - cancel before requesting the next tier.
        await client.post(
            f"/api/v1/rides/{body['id']}/cancel", headers=auth_headers(registered_user.access_token)
        )


# --- POST /rides/{id}/accept -------------------------------------------------


async def test_driver_accepts_requested_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
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
    driver_a = await create_user(db_session, as_driver=True, email="driver-a@example.com")
    driver_b = await create_user(db_session, as_driver=True, email="driver-b@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver_a.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/accept", headers=auth_headers(driver_b.access_token)
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "conflict"


async def test_accepting_cancelled_ride_returns_distinguishable_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _cancel(db_session, ride.id, rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/accept", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "ride_cancelled"
    assert body["message"] == "This ride was cancelled by the rider."


async def test_accepting_nonexistent_ride_returns_404(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.post(
        f"/api/v1/rides/{uuid4()}/accept", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 404


# --- POST /rides/{id}/start ---------------------------------------------------


async def test_driver_starts_accepted_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/start", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ongoing"

    detail = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(driver.access_token)
    )
    assert detail.json()["status"] == "ongoing"


async def test_wrong_driver_cannot_start_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    assigned_driver = await create_user(
        db_session, as_driver=True, email="assigned@example.com"
    )
    other_driver = await create_user(db_session, as_driver=True, email="other@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, assigned_driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/start", headers=auth_headers(other_driver.access_token)
    )

    assert response.status_code == 403


async def test_starting_still_requested_ride_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/start", headers=auth_headers(driver.access_token)
    )

    # The driver isn't assigned to this ride yet (it was never accepted), so the
    # ForbiddenError ownership check fires before the status check would.
    assert response.status_code == 403


async def test_starting_already_ongoing_ride_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _start(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/start", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "conflict"


async def test_starting_completed_ride_returns_conflict(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/start", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "conflict"


async def test_starting_cancelled_ride_returns_distinguishable_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _cancel(db_session, ride.id, rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/start", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "ride_cancelled"
    assert body["message"] == "This ride was cancelled by the rider."


async def test_starting_nonexistent_ride_returns_404(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.post(
        f"/api/v1/rides/{uuid4()}/start", headers=auth_headers(driver.access_token)
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
    driver = await create_user(db_session, as_driver=True)
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
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/cancel", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 409


# --- POST /rides/{id}/complete ------------------------------------------------


async def test_completing_accepted_ride_without_starting_returns_ride_not_started(
    client: AsyncClient, db_session
) -> None:
    """Reverses a previously-passing test's expected outcome: completing directly
    from ACCEPTED (skipping /start) used to succeed (200) when start was advisory.
    Per an explicit product decision, ONGOING is now a required prerequisite for
    completion, so this must now 409 with a distinguishable, recoverable error -
    "start it first" - rather than the generic conflict message."""
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "ride_not_started"
    assert body["message"] == "Start the ride before completing it."


async def test_driver_completes_ongoing_ride(client: AsyncClient, db_session) -> None:
    """Happy path: ONGOING is the only status CompleteRideUseCase accepts now -
    calling /start first is required, not advisory (reversed from an earlier
    "ACCEPTED or ONGOING both fine" design this session)."""
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _start(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


async def test_fare_is_frozen_across_the_ride_lifecycle(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id, tier=RideTier.COMFORT)
    requested_fare = ride.fare

    accept_response = await client.post(
        f"/api/v1/rides/{ride.id}/accept", headers=auth_headers(driver.access_token)
    )
    assert accept_response.json()["fare"] == pytest.approx(requested_fare)
    assert accept_response.json()["tier"] == "comfort"

    await _start(db_session, ride.id, driver.user.id)  # required before /complete now

    complete_response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )
    assert complete_response.json()["fare"] == pytest.approx(requested_fare)
    assert complete_response.json()["tier"] == "comfort"


async def test_wrong_driver_cannot_complete_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    assigned_driver = await create_user(
        db_session, as_driver=True, email="assigned@example.com"
    )
    other_driver = await create_user(db_session, as_driver=True, email="other@example.com")
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
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )

    # The driver isn't assigned to this ride yet (it was never accepted), so the
    # ForbiddenError ownership check fires before the status check would.
    assert response.status_code == 403


async def test_completing_cancelled_ride_returns_distinguishable_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _cancel(db_session, ride.id, rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/complete", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 409
    body = response.json()
    assert body["error_code"] == "ride_cancelled"
    assert body["message"] == "This ride was cancelled by the rider."


# --- POST /rides/{id}/rating ----------------------------------------------------


async def test_rider_rates_completed_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 5},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["ride_id"] == str(ride.id)
    assert body["rider_id"] == str(rider.user.id)
    assert body["driver_id"] == str(driver.user.id)
    assert body["score"] == 5


async def test_rating_a_ride_twice_returns_conflict(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)
    await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 4},
    )

    response = await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 5},
    )

    assert response.status_code == 409


async def test_rating_someone_elses_ride_returns_forbidden(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    stranger = await create_user(db_session, email="rating-stranger@example.com")
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(stranger.access_token),
        json={"score": 3},
    )

    assert response.status_code == 403


async def test_rating_a_non_completed_ride_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 3},
    )

    assert response.status_code == 409


async def test_rating_nonexistent_ride_returns_404(client: AsyncClient, registered_user) -> None:
    response = await client.post(
        f"/api/v1/rides/{uuid4()}/rating",
        headers=auth_headers(registered_user.access_token),
        json={"score": 3},
    )

    assert response.status_code == 404


async def test_rating_out_of_range_score_returns_422(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)

    response = await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 6},
    )

    assert response.status_code == 422


# --- Average rating on DriverProfileResponse --------------------------------------


async def test_driver_with_no_ratings_has_null_average_and_zero_count(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    profile = response.json()["driver_profile"]
    assert profile["average_rating"] is None
    assert profile["rating_count"] == 0


async def test_average_rating_reflects_single_rating(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)
    await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 4},
    )

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    profile = response.json()["driver_profile"]
    assert profile["average_rating"] == 4.0
    assert profile["rating_count"] == 1


async def test_average_rating_reflects_multiple_ratings(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)
    scores = [5, 3, 4]

    for score in scores:
        rider = await create_user(db_session, email=f"rater-{score}-{uuid4()}@example.com")
        ride = await create_ride(db_session, rider_id=rider.user.id)
        await _accept(db_session, ride.id, driver.user.id)
        await _complete(db_session, ride.id, driver.user.id)
        await client.post(
            f"/api/v1/rides/{ride.id}/rating",
            headers=auth_headers(rider.access_token),
            json={"score": score},
        )

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    profile = response.json()["driver_profile"]
    assert profile["rating_count"] == 3
    assert profile["average_rating"] == pytest.approx(4.0)  # (5 + 3 + 4) / 3


# --- GET /rides/history --------------------------------------------------------


async def test_rider_history_ordered_most_recent_first(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
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
    driver_a = await create_user(db_session, as_driver=True, email="hist-a@example.com")
    driver_b = await create_user(db_session, as_driver=True, email="hist-b@example.com")

    ride_for_a = await create_ride(db_session, rider_id=rider_a.user.id)
    await _accept(db_session, ride_for_a.id, driver_a.user.id)

    ride_for_b = await create_ride(db_session, rider_id=rider_b.user.id)
    await _accept(db_session, ride_for_b.id, driver_b.user.id)

    response = await client.get(
        "/api/v1/rides/history?as=driver", headers=auth_headers(driver_a.access_token)
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
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(driver.access_token)
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(ride.id)


async def test_requested_ride_has_null_driver(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    ride = await create_ride(db_session, rider_id=rider.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["driver_id"] is None
    assert body["driver"] is None


async def test_accepted_ride_embeds_driver_summary(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True, full_name="Jane Driver")
    await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"vehicle_type": "Sedan", "vehicle_color": "White", "license_plate": "ABC-123"},
    )
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(rider.access_token)
    )

    assert response.status_code == 200
    driver_summary = response.json()["driver"]
    assert driver_summary["name"] == "Jane Driver"
    assert driver_summary["vehicle_type"] == "Sedan"
    assert driver_summary["vehicle_color"] == "White"
    assert driver_summary["license_plate"] == "ABC-123"
    assert driver_summary["average_rating"] is None
    assert driver_summary["rating_count"] == 0


async def test_completed_ride_embeds_driver_summary_with_average_rating(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)
    await _complete(db_session, ride.id, driver.user.id)
    await client.post(
        f"/api/v1/rides/{ride.id}/rating",
        headers=auth_headers(rider.access_token),
        json={"score": 5},
    )

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(rider.access_token)
    )

    driver_summary = response.json()["driver"]
    assert driver_summary["average_rating"] == 5.0
    assert driver_summary["rating_count"] == 1


async def test_embedded_driver_summary_excludes_pii(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(
        db_session, as_driver=True, phone_number="+201234567890"
    )
    ride = await create_ride(db_session, rider_id=rider.user.id)
    await _accept(db_session, ride.id, driver.user.id)

    response = await client.get(
        f"/api/v1/rides/{ride.id}", headers=auth_headers(rider.access_token)
    )

    driver_summary = response.json()["driver"]
    # Explicit absence check, not just "the test passed" - a stranger (the
    # rider) must never see the driver's email or phone number.
    assert "email" not in driver_summary
    assert "phone_number" not in driver_summary
    assert set(driver_summary.keys()) == {
        "name",
        "vehicle_type",
        "vehicle_color",
        "license_plate",
        "average_rating",
        "rating_count",
    }


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


# --- GET /rides/available -------------------------------------------------------


async def test_online_driver_sees_nearby_unassigned_ride(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    await _go_online(db_session, driver.user.id)
    ride = await create_ride(
        db_session, rider_id=rider.user.id, pickup_latitude=30.05, pickup_longitude=31.23
    )

    response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(driver.access_token),
    )

    assert response.status_code == 200
    ids = [item["id"] for item in response.json()]
    assert ids == [str(ride.id)]


async def test_available_rides_excludes_rides_outside_bounding_box(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    driver = await create_user(db_session, as_driver=True)
    await _go_online(db_session, driver.user.id)
    # Far away - Alexandria vs. the driver searching from Cairo, well outside the
    # ~5km default box.
    await create_ride(
        db_session, rider_id=rider.user.id, pickup_latitude=31.2001, pickup_longitude=29.9187
    )

    response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(driver.access_token),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_available_rides_excludes_already_assigned_rides(
    client: AsyncClient, db_session
) -> None:
    rider = await create_user(db_session)
    assigned_driver = await create_user(
        db_session, as_driver=True, email="assigned-driver@example.com"
    )
    searching_driver = await create_user(
        db_session, as_driver=True, email="searching-driver@example.com"
    )
    await _go_online(db_session, searching_driver.user.id)
    ride = await create_ride(
        db_session, rider_id=rider.user.id, pickup_latitude=30.05, pickup_longitude=31.23
    )
    await _accept(db_session, ride.id, assigned_driver.user.id)

    response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(searching_driver.access_token),
    )

    assert response.status_code == 200
    assert response.json() == []


async def test_rider_cannot_access_available_rides(client: AsyncClient, registered_user) -> None:
    response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(registered_user.access_token),
    )

    assert response.status_code == 403


async def test_offline_driver_gets_403_on_available_rides(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)  # stays offline (default)

    response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(driver.access_token),
    )

    assert response.status_code == 403


async def test_available_rides_respects_limit_cap(client: AsyncClient, db_session) -> None:
    driver = await create_user(
        db_session, as_driver=True, email="dense-area-driver@example.com"
    )
    await _go_online(db_session, driver.user.id)

    # A rider can only have one active ride at a time, so 22 simultaneously REQUESTED
    # rides need 22 distinct riders - the cap is about result-set size, not about any
    # one rider's state.
    for i in range(22):
        rider = await create_user(db_session, email=f"dense-area-rider-{i}@example.com")
        await create_ride(
            db_session, rider_id=rider.user.id, pickup_latitude=30.05, pickup_longitude=31.23
        )

    response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(driver.access_token),
    )

    assert response.status_code == 200
    assert len(response.json()) == 20  # capped, not all 22


async def test_available_rides_invalid_coordinates_returns_422(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)
    await _go_online(db_session, driver.user.id)

    response = await client.get(
        "/api/v1/rides/available?lat=999&lng=31.23",
        headers=auth_headers(driver.access_token),
    )

    assert response.status_code == 422
