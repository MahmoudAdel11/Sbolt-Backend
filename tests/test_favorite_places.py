from uuid import uuid4

from httpx import AsyncClient

from tests.conftest import auth_headers
from tests.factories import create_user

VALID_PLACE_PAYLOAD = {
    "label": "Home",
    "address": "123 Main St",
    "latitude": 30.05,
    "longitude": 31.23,
}


async def _create_place(client: AsyncClient, token: str, **overrides) -> dict:
    """Create a favorite place via the real endpoint - setup for tests that aren't
    specifically about the create endpoint itself.
    """
    response = await client.post(
        "/api/v1/favorite-places",
        headers=auth_headers(token),
        json={**VALID_PLACE_PAYLOAD, **overrides},
    )
    assert response.status_code == 201, response.json()
    return response.json()


# --- POST /favorite-places ----------------------------------------------------


async def test_create_favorite_place_success(client: AsyncClient, registered_user) -> None:
    response = await client.post(
        "/api/v1/favorite-places",
        headers=auth_headers(registered_user.access_token),
        json=VALID_PLACE_PAYLOAD,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["label"] == "Home"
    assert body["address"] == "123 Main St"
    assert body["latitude"] == 30.05
    assert body["longitude"] == 31.23
    assert body["user_id"] == str(registered_user.user.id)
    assert "id" in body
    assert "created_at" in body


async def test_create_duplicate_label_returns_conflict(
    client: AsyncClient, registered_user
) -> None:
    await _create_place(client, registered_user.access_token)

    response = await client.post(
        "/api/v1/favorite-places",
        headers=auth_headers(registered_user.access_token),
        json={**VALID_PLACE_PAYLOAD, "address": "Different address"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "conflict"


async def test_create_out_of_range_coordinates_returns_422(
    client: AsyncClient, registered_user
) -> None:
    response = await client.post(
        "/api/v1/favorite-places",
        headers=auth_headers(registered_user.access_token),
        json={**VALID_PLACE_PAYLOAD, "latitude": 999},
    )

    assert response.status_code == 422


# --- GET /favorite-places ------------------------------------------------------


async def test_list_returns_only_current_users_places(client: AsyncClient, db_session) -> None:
    owner = await create_user(db_session, email="owner@example.com")
    other = await create_user(db_session, email="other@example.com")

    await _create_place(client, owner.access_token, label="Home")
    await _create_place(client, owner.access_token, label="Work")
    await _create_place(client, other.access_token, label="Home")

    response = await client.get(
        "/api/v1/favorite-places", headers=auth_headers(owner.access_token)
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert {place["label"] for place in body} == {"Home", "Work"}
    assert all(place["user_id"] == str(owner.user.id) for place in body)


async def test_list_empty_for_user_with_no_places(client: AsyncClient, registered_user) -> None:
    response = await client.get(
        "/api/v1/favorite-places", headers=auth_headers(registered_user.access_token)
    )

    assert response.status_code == 200
    assert response.json() == []


# --- PATCH /favorite-places/{id} -----------------------------------------------


async def test_update_partial_single_field(client: AsyncClient, registered_user) -> None:
    place = await _create_place(client, registered_user.access_token)

    response = await client.patch(
        f"/api/v1/favorite-places/{place['id']}",
        headers=auth_headers(registered_user.access_token),
        json={"address": "456 New Address"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["address"] == "456 New Address"
    assert body["label"] == place["label"]
    assert body["latitude"] == place["latitude"]
    assert body["longitude"] == place["longitude"]


async def test_update_label_collides_with_own_other_place_returns_conflict(
    client: AsyncClient, registered_user
) -> None:
    await _create_place(client, registered_user.access_token, label="Home")
    work = await _create_place(client, registered_user.access_token, label="Work")

    response = await client.patch(
        f"/api/v1/favorite-places/{work['id']}",
        headers=auth_headers(registered_user.access_token),
        json={"label": "Home"},
    )

    assert response.status_code == 409
    assert response.json()["error_code"] == "conflict"


async def test_update_another_users_place_returns_forbidden(
    client: AsyncClient, db_session
) -> None:
    owner = await create_user(db_session, email="patch-owner@example.com")
    stranger = await create_user(db_session, email="patch-stranger@example.com")
    place = await _create_place(client, owner.access_token)

    response = await client.patch(
        f"/api/v1/favorite-places/{place['id']}",
        headers=auth_headers(stranger.access_token),
        json={"label": "Hijacked"},
    )

    assert response.status_code == 403


async def test_update_nonexistent_id_returns_404(client: AsyncClient, registered_user) -> None:
    response = await client.patch(
        f"/api/v1/favorite-places/{uuid4()}",
        headers=auth_headers(registered_user.access_token),
        json={"label": "Nope"},
    )

    assert response.status_code == 404


# --- DELETE /favorite-places/{id} ----------------------------------------------


async def test_delete_success_and_confirmed_gone(client: AsyncClient, registered_user) -> None:
    place = await _create_place(client, registered_user.access_token)

    delete_response = await client.delete(
        f"/api/v1/favorite-places/{place['id']}",
        headers=auth_headers(registered_user.access_token),
    )
    assert delete_response.status_code == 204

    list_response = await client.get(
        "/api/v1/favorite-places", headers=auth_headers(registered_user.access_token)
    )
    assert list_response.json() == []


async def test_delete_another_users_place_returns_forbidden(
    client: AsyncClient, db_session
) -> None:
    owner = await create_user(db_session, email="delete-owner@example.com")
    stranger = await create_user(db_session, email="delete-stranger@example.com")
    place = await _create_place(client, owner.access_token)

    response = await client.delete(
        f"/api/v1/favorite-places/{place['id']}", headers=auth_headers(stranger.access_token)
    )

    assert response.status_code == 403


async def test_delete_nonexistent_id_returns_404(client: AsyncClient, registered_user) -> None:
    response = await client.delete(
        f"/api/v1/favorite-places/{uuid4()}", headers=auth_headers(registered_user.access_token)
    )

    assert response.status_code == 404
