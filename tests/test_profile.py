from httpx import AsyncClient

from tests.conftest import auth_headers
from tests.factories import create_user


async def test_update_full_name_only(client: AsyncClient, registered_user) -> None:
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(registered_user.access_token),
        json={"full_name": "Updated Name"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Updated Name"
    assert body["phone_number"] == registered_user.user.phone_number


async def test_update_phone_number_only(client: AsyncClient, registered_user) -> None:
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(registered_user.access_token),
        json={"phone_number": "+201111111111"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["phone_number"] == "+201111111111"
    assert body["full_name"] == registered_user.user.full_name


async def test_update_both_fields(client: AsyncClient, registered_user) -> None:
    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(registered_user.access_token),
        json={"full_name": "Both Updated", "phone_number": "+202222222222"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Both Updated"
    assert body["phone_number"] == "+202222222222"


async def test_update_duplicate_phone_number_returns_conflict(
    client: AsyncClient, db_session
) -> None:
    user_a = await create_user(db_session, email="a@example.com", phone_number="+201234500000")
    user_b = await create_user(db_session, email="b@example.com", phone_number="+201234511111")

    response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(user_b.access_token),
        json={"phone_number": "+201234500000"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "conflict"
    # user_a's phone number is untouched by the failed attempt
    assert user_a.user.phone_number == "+201234500000"


async def test_update_reflected_in_subsequent_me(client: AsyncClient, registered_user) -> None:
    patch_response = await client.patch(
        "/api/v1/users/me",
        headers=auth_headers(registered_user.access_token),
        json={"full_name": "Reflected Name", "phone_number": "+203333333333"},
    )
    assert patch_response.status_code == 200

    me_response = await client.get(
        "/api/v1/auth/me", headers=auth_headers(registered_user.access_token)
    )

    assert me_response.status_code == 200
    body = me_response.json()
    assert body["full_name"] == "Reflected Name"
    assert body["phone_number"] == "+203333333333"
