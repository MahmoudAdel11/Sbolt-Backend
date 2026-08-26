from datetime import UTC, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy import delete, select

from app.core.jwt import create_access_token, decode_access_token
from app.core.security import hash_token
from app.infrastructure.db.models.refresh_token import RefreshTokenModel
from app.infrastructure.db.models.user import UserModel
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
    assert body["user"]["email"] == "jane@example.com"
    assert body["user"]["full_name"] == "Jane Doe"
    assert body["user"]["phone_number"] == "+201234567890"
    assert body["user"]["is_active"] is True
    assert body["user"]["driver_profile"] is None
    assert "id" in body["user"]
    assert "created_at" in body["user"]
    assert "hashed_password" not in body["user"]
    assert "password" not in body["user"]
    # Registration now logs the user straight in - tokens come back alongside
    # the profile rather than requiring a separate /auth/login call.
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    assert "refresh_token" in body


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
    assert response.json()["user"]["driver_profile"] is None


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
    assert response.json()["user"]["driver_profile"] is None


async def test_register_as_driver_creates_driver_profile(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "new-driver@example.com",
            "password": "supersecret123",
            "full_name": "New Driver",
            "register_as_driver": True,
            "scooter_type": "comfort",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["driver_profile"] is not None
    assert body["user"]["driver_profile"]["is_online"] is False  # drivers start offline
    assert body["user"]["driver_profile"]["scooter_type"] == "comfort"


async def test_register_as_driver_without_scooter_type_returns_422(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "driver-no-scooter@example.com",
            "password": "supersecret123",
            "full_name": "No Scooter",
            "register_as_driver": True,
        },
    )

    assert response.status_code == 422


async def test_register_as_rider_without_scooter_type_succeeds(client: AsyncClient) -> None:
    """scooter_type is only required when register_as_driver is true - a rider
    registration must not be blocked by its absence."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rider-no-scooter@example.com",
            "password": "supersecret123",
            "full_name": "Rider No Scooter",
        },
    )

    assert response.status_code == 201


async def test_register_as_driver_with_invalid_scooter_type_returns_422(
    client: AsyncClient,
) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "bad-scooter@example.com",
            "password": "supersecret123",
            "full_name": "Bad Scooter",
            "register_as_driver": True,
            "scooter_type": "not-a-real-tier",
        },
    )

    assert response.status_code == 422


async def test_register_access_token_works_immediately(client: AsyncClient) -> None:
    """Real proof of auto-login: the returned access_token must actually authenticate
    a follow-up request, not just be present as a field."""
    register_response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "auto-login@example.com",
            "password": "supersecret123",
            "full_name": "Auto Login",
        },
    )
    assert register_response.status_code == 201
    access_token = register_response.json()["access_token"]

    me_response = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {access_token}"}
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == "auto-login@example.com"


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
    assert "refresh_token" in body

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


# --- POST /auth/refresh --------------------------------------------------------


async def _refresh_token_row(db_session, raw_token: str) -> RefreshTokenModel:
    result = await db_session.execute(
        select(RefreshTokenModel).where(RefreshTokenModel.token_hash == hash_token(raw_token))
    )
    return result.scalar_one()


async def test_refresh_with_valid_token_issues_new_access_token_and_extends_expiry(
    client: AsyncClient, db_session
) -> None:
    test_user: CreatedUser = await create_user(db_session, email="refresh-success@example.com")
    expires_at_before = (await _refresh_token_row(db_session, test_user.refresh_token)).expires_at

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_user.refresh_token}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert "access_token" in body
    payload = decode_access_token(body["access_token"])
    assert payload["sub"] == str(test_user.user.id)

    expires_at_after = (await _refresh_token_row(db_session, test_user.refresh_token)).expires_at
    assert expires_at_after > expires_at_before


async def test_refresh_with_unknown_token_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": "not-a-real-refresh-token"}
    )

    assert response.status_code == 401


async def test_refresh_with_expired_token_returns_401(client: AsyncClient, db_session) -> None:
    test_user: CreatedUser = await create_user(db_session, email="refresh-expired@example.com")
    model = await _refresh_token_row(db_session, test_user.refresh_token)
    model.expires_at = datetime.now(UTC) - timedelta(days=1)
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_user.refresh_token}
    )

    assert response.status_code == 401


async def test_refresh_after_user_deleted_returns_401(client: AsyncClient, db_session) -> None:
    """The users -> refresh_tokens FK is ON DELETE CASCADE, so deleting the user also
    deletes their refresh_tokens row - the request still correctly 401s, though via the
    "token not found" branch rather than RefreshAccessTokenUseCase's "user no longer
    exists" check (that check remains as defense-in-depth for a row that outlives its
    user through some other path, but isn't exercised by this particular scenario)."""
    test_user: CreatedUser = await create_user(db_session, email="refresh-user-gone@example.com")

    await db_session.execute(delete(UserModel).where(UserModel.id == test_user.user.id))
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_user.refresh_token}
    )

    assert response.status_code == 401


async def test_refresh_twice_with_same_token_both_succeed_and_each_extends_expiry(
    client: AsyncClient, db_session
) -> None:
    """Proves sliding-only behavior: the same refresh_token value keeps working across
    consecutive refreshes, and each call pushes expires_at further out rather than the
    second call silently failing after the first "uses up" the token."""
    test_user: CreatedUser = await create_user(db_session, email="refresh-sliding@example.com")

    first_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_user.refresh_token}
    )
    assert first_response.status_code == 200
    expiry_after_first = (await _refresh_token_row(db_session, test_user.refresh_token)).expires_at

    second_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_user.refresh_token}
    )
    assert second_response.status_code == 200
    expiry_after_second = (await _refresh_token_row(db_session, test_user.refresh_token)).expires_at

    assert expiry_after_second > expiry_after_first


# --- POST /auth/logout ----------------------------------------------------------


async def test_logout_deletes_refresh_token_row(client: AsyncClient, db_session) -> None:
    test_user: CreatedUser = await create_user(db_session, email="logout-success@example.com")

    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": test_user.refresh_token}
    )

    assert response.status_code == 204

    result = await db_session.execute(
        RefreshTokenModel.__table__.select().where(
            RefreshTokenModel.token_hash == hash_token(test_user.refresh_token)
        )
    )
    assert result.scalar_one_or_none() is None


async def test_refresh_after_logout_returns_401(client: AsyncClient, db_session) -> None:
    test_user: CreatedUser = await create_user(db_session, email="logout-then-refresh@example.com")

    logout_response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": test_user.refresh_token}
    )
    assert logout_response.status_code == 204

    refresh_response = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": test_user.refresh_token}
    )

    assert refresh_response.status_code == 401


async def test_logout_with_unknown_token_is_a_no_op(client: AsyncClient) -> None:
    """Logout with a token that doesn't exist (already logged out, or never valid)
    isn't an error - there's nothing to delete, and the desired end state (no live
    session for that token) already holds."""
    response = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": "never-existed-token"}
    )

    assert response.status_code == 204
