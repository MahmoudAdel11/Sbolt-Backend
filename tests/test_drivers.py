from httpx import AsyncClient

from app.domain.user.entities import UserRole
from tests.conftest import auth_headers
from tests.factories import create_user

# --- PATCH /drivers/me/status --------------------------------------------------


async def test_driver_can_go_online(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, role=UserRole.DRIVER)

    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={"is_online": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["is_online"] is True
    assert body["role"] == "driver"


async def test_driver_can_go_offline(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, role=UserRole.DRIVER)
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
    assert response.json()["is_online"] is False


async def test_status_change_reflected_in_subsequent_me(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, role=UserRole.DRIVER)

    patch_response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={"is_online": True},
    )
    assert patch_response.status_code == 200

    me_response = await client.get("/api/v1/auth/me", headers=auth_headers(driver.access_token))

    assert me_response.status_code == 200
    assert me_response.json()["is_online"] is True


async def test_rider_cannot_toggle_driver_status(client: AsyncClient, registered_user) -> None:
    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(registered_user.access_token),
        json={"is_online": True},
    )

    assert response.status_code == 403


async def test_status_update_requires_body_field(client: AsyncClient, db_session) -> None:
    driver = await create_user(db_session, role=UserRole.DRIVER)

    response = await client.patch(
        "/api/v1/drivers/me/status",
        headers=auth_headers(driver.access_token),
        json={},
    )

    assert response.status_code == 422
