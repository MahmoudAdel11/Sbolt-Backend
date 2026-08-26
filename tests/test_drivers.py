from httpx import AsyncClient

from tests.conftest import auth_headers
from tests.factories import create_ride, create_user

# --- PATCH /drivers/me/status --------------------------------------------------


async def test_driver_can_go_online(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={"is_online": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["driver_profile"]["is_online"] is True


async def test_driver_can_go_offline(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)
    await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={"is_online": True},
    )

    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={"is_online": False},
    )

    assert response.status_code == 200
    assert response.json()["driver_profile"]["is_online"] is False


async def test_status_change_reflected_in_subsequent_me(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    patch_response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={"is_online": True},
    )
    assert patch_response.status_code == 200

    me_response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    assert me_response.status_code == 200
    assert me_response.json()["driver_profile"]["is_online"] is True


async def test_rider_cannot_toggle_driver_status(client: AsyncClient, registered_user) -> None:
    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(registered_user.access_token),
        json={"is_online": True},
    )

    assert response.status_code == 403


async def test_status_update_requires_body_field(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={},
    )

    assert response.status_code == 422


async def test_rider_only_account_has_no_driver_profile(client: AsyncClient, db_session) -> None:
    rider = await create_user(db_session)

    response = await client.get("/api/v1/auth/me", headers=auth_headers(rider.access_token))

    assert response.status_code == 200
    assert response.json()["driver_profile"] is None


# --- PATCH /drivers/me/vehicle ---------------------------------------------------


async def test_driver_can_set_vehicle_details(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"vehicle_type": "Sedan", "vehicle_color": "White", "license_plate": "ABC-123"},
    )

    assert response.status_code == 200
    profile = response.json()["driver_profile"]
    assert profile["vehicle_type"] == "Sedan"
    assert profile["vehicle_color"] == "White"
    assert profile["license_plate"] == "ABC-123"


async def test_driver_vehicle_update_is_partial(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)
    await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"vehicle_type": "Sedan", "vehicle_color": "White", "license_plate": "ABC-123"},
    )

    response = await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"vehicle_color": "Black"},
    )

    assert response.status_code == 200
    profile = response.json()["driver_profile"]
    # Only vehicle_color was provided - the others must survive untouched.
    assert profile["vehicle_type"] == "Sedan"
    assert profile["vehicle_color"] == "Black"
    assert profile["license_plate"] == "ABC-123"


async def test_vehicle_details_persist_across_requests(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)
    await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"vehicle_type": "Sedan"},
    )

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    assert response.status_code == 200
    assert response.json()["driver_profile"]["vehicle_type"] == "Sedan"


async def test_driver_with_no_vehicle_details_returns_none_fields(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    profile = response.json()["driver_profile"]
    assert profile["vehicle_type"] is None
    assert profile["vehicle_color"] is None
    assert profile["license_plate"] is None


async def test_rider_cannot_update_vehicle_details(
    client: AsyncClient, registered_user
) -> None:
    response = await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(registered_user.access_token),
        json={"vehicle_type": "Sedan"},
    )

    assert response.status_code == 403


# --- scooter_type -----------------------------------------------------------------


async def test_driver_with_no_scooter_type_returns_null(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    assert response.json()["driver_profile"]["scooter_type"] is None


async def test_driver_can_set_scooter_type_via_vehicle_endpoint(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"scooter_type": "premium"},
    )

    assert response.status_code == 200
    assert response.json()["driver_profile"]["scooter_type"] == "premium"


async def test_scooter_type_update_is_partial_and_does_not_touch_vehicle_fields(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)
    await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"vehicle_type": "Sedan"},
    )

    response = await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"scooter_type": "comfort"},
    )

    assert response.status_code == 200
    profile = response.json()["driver_profile"]
    assert profile["scooter_type"] == "comfort"
    assert profile["vehicle_type"] == "Sedan"  # untouched by this partial update


async def test_scooter_type_persists_across_requests(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, as_driver=True)
    await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"scooter_type": "economy"},
    )

    response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    assert response.json()["driver_profile"]["scooter_type"] == "economy"


async def test_updating_vehicle_with_invalid_scooter_type_returns_422(
    client: AsyncClient, db_session
) -> None:
    driver = await create_user(db_session, as_driver=True)

    response = await client.patch(
        "/api/v1/drivers/me/vehicle",
        headers=auth_headers(driver.access_token),
        json={"scooter_type": "not-a-real-tier"},
    )

    assert response.status_code == 422


# --- Both roles simultaneously ---------------------------------------------------


async def test_same_account_can_use_both_rider_and_driver_flows(
    client: AsyncClient, db_session
) -> None:
    """The central claim of this refactor: one account, both capabilities at once -
    not two accounts, not a mode switch that disables the other role."""
    both = await create_user(db_session, as_driver=True, email="both-roles@example.com")

    # Rider flow: request a ride as this same account.
    request_response = await client.post(
        "/api/v1/rides",
        headers=auth_headers(both.access_token),
        json={
            "pickup_latitude": 30.05,
            "pickup_longitude": 31.23,
            "dropoff_latitude": 30.06,
            "dropoff_longitude": 31.25,
            "tier": "economy",
        },
    )
    assert request_response.status_code == 201
    own_ride_id = request_response.json()["id"]
    assert request_response.json()["rider_id"] == str(both.user.id)

    # Cancel the account's own ride first - nothing stops a driver from seeing/
    # accepting their own rider-side ride, which isn't what this test is about;
    # cancelling it isolates the assertion below to "can this account see rides
    # requested by someone else while acting as a driver."
    await client.post(
        f"/api/v1/rides/{own_ride_id}/cancel", headers=auth_headers(both.access_token)
    )

    # Driver flow: go online and see (someone else's) available rides.
    status_response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(both.access_token),
        json={"is_online": True},
    )
    assert status_response.status_code == 200
    assert status_response.json()["driver_profile"]["is_online"] is True

    other_rider = await create_user(db_session, email="other-rider-for-both-test@example.com")
    other_ride = await create_ride(
        db_session, rider_id=other_rider.user.id, pickup_latitude=30.05, pickup_longitude=31.23
    )

    available_response = await client.get(
        "/api/v1/rides/available?lat=30.05&lng=31.23",
        headers=auth_headers(both.access_token),
    )
    assert available_response.status_code == 200
    assert [r["id"] for r in available_response.json()] == [str(other_ride.id)]


async def test_same_account_gets_separately_scoped_rider_and_driver_history(
    client: AsyncClient, db_session
) -> None:
    both = await create_user(db_session, as_driver=True, email="both-history@example.com")
    other_rider = await create_user(db_session, email="other-rider-for-history@example.com")

    # As rider: a ride this account requested.
    own_ride_as_rider = await create_ride(
        db_session, rider_id=both.user.id, pickup_latitude=30.05, pickup_longitude=31.23
    )
    await client.post(
        f"/api/v1/rides/{own_ride_as_rider.id}/cancel", headers=auth_headers(both.access_token)
    )

    # As driver: a ride this account accepted, requested by someone else.
    ride_to_accept = await create_ride(
        db_session, rider_id=other_rider.user.id, pickup_latitude=30.05, pickup_longitude=31.23
    )
    accept_response = await client.post(
        f"/api/v1/rides/{ride_to_accept.id}/accept", headers=auth_headers(both.access_token)
    )
    assert accept_response.status_code == 200

    rider_history = await client.get(
        "/api/v1/rides/history?as=rider", headers=auth_headers(both.access_token)
    )
    driver_history = await client.get(
        "/api/v1/rides/history?as=driver", headers=auth_headers(both.access_token)
    )

    assert [item["id"] for item in rider_history.json()["items"]] == [str(own_ride_as_rider.id)]
    assert [item["id"] for item in driver_history.json()["items"]] == [str(ride_to_accept.id)]


async def test_rider_only_account_gets_403_for_driver_history_view(
    client: AsyncClient, registered_user
) -> None:
    response = await client.get(
        "/api/v1/rides/history?as=driver", headers=auth_headers(registered_user.access_token)
    )

    assert response.status_code == 403
