from datetime import timedelta

from httpx import AsyncClient

from app.core.jwt import create_access_token, decode_access_token
from tests.factories import DEFAULT_PASSWORD, CreatedUser, create_user

# --- Register --------------------------------------------------------------


async def test_register_success(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "jane@example.com",
            "password": "supersecret123",
            "full_name": "Jane Doe",
            "phone_number": "+201234567890",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "jane@example.com"
    assert body["full_name"] == "Jane Doe"
    assert body["phone_number"] == "+201234567890"
    assert body["is_active"] is True
    assert body["driver_profile"] is None
    assert "id" in body
    assert "created_at" in body
    assert "hashed_password" not in body
    assert "password" not in body


async def test_register_duplicate_email_returns_conflict(client: AsyncClient) -> None:
    payload = {
        "email": "duplicate@example.com",
        "password": "supersecret123",
        "full_name": "First",
    }
    first = await client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201

    second = await client.post(
        "/api/v1/auth/register", json={**payload, "full_name": "Second"}
    )

    assert second.status_code == 409
    assert second.json()["error_code"] == "conflict"


async def test_register_invalid_email_format_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "not-an-email", "password": "supersecret123", "full_name": "Bad Email"},
    )

    assert response.status_code == 422


async def test_register_password_below_minimum_length_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "short1", "full_name": "Short Pass"},
    )

    assert response.status_code == 422


async def test_register_without_driver_flag_has_no_driver_profile(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "no-driver-flag@example.com",
            "password": "supersecret123",
            "full_name": "No Driver Flag",
        },
    )

    assert response.status_code == 201
    assert response.json()["driver_profile"] is None


async def test_register_with_explicit_false_has_no_driver_profile(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "explicit-rider@example.com",
            "password": "supersecret123",
            "full_name": "Explicit Rider",
            "register_as_driver": False,
        },
    )

    assert response.status_code == 201
    assert response.json()["driver_profile"] is None


async def test_register_as_driver_creates_driver_profile(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-driver@example.com",
            "password": "supersecret123",
            "full_name": "New Driver",
            "register_as_driver": True,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["driver_profile"] is not None
    assert body["driver_profile"]["is_online"] is False  # drivers start offline


async def test_register_with_invalid_driver_flag_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad-flag@example.com",
            "password": "supersecret123",
            "full_name": "Bad Flag",
            "register_as_driver": "not-a-boolean-and-not-coercible",
        },
    )

    assert response.status_code == 422


# --- Login -------------------------------------------------------------------


async def test_login_success(client: AsyncClient, db_session) -> None:
    test_user: CreatedUser = await create_user(db_session, email="login-success@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "login-success@example.com", "password": test_user.password},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body

    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(test_user.user.id)


async def test_login_wrong_password_returns_401(client: AsyncClient, db_session) -> None:
    await create_user(db_session, email="wrongpass@example.com")

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpass@example.com", "password": "definitely-wrong"},
    )

    assert response.status_code == 401


async def test_login_nonexistent_email_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody-here@example.com", "password": DEFAULT_PASSWORD},
    )

    assert response.status_code == 401


async def test_login_failures_return_identical_generic_message(
    client: AsyncClient, db_session
) -> None:
    await create_user(db_session, email="enumeration-check@example.com")

    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": "enumeration-check@example.com", "password": "wrong-password"},
    )
    nonexistent_email = await client.post(
        "/api/v1/auth/login",
        json={"email": "truly-nobody@example.com", "password": DEFAULT_PASSWORD},
    )

    assert wrong_password.status_code == nonexistent_email.status_code == 401
    assert wrong_password.json() == nonexistent_email.json()


# --- GET /auth/me --------------------------------------------------------------


async def test_me_success_with_valid_token(client: AsyncClient, registered_user) -> None:
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {registered_user.access_token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(registered_user.user.id)
    assert body["email"] == registered_user.user.email


async def test_me_no_token_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_me_malformed_token_returns_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-real-jwt"}
    )

    assert response.status_code == 401


async def test_me_expired_token_returns_401(client: AsyncClient, registered_user) -> None:
    expired_token = create_access_token(
        subject=str(registered_user.user.id), expires_delta=timedelta(seconds=-1)
    )

    response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"}
    )

    assert response.status_code == 401
