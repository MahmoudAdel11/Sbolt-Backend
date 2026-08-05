"""Smoke test proving the fixture chain (db_session -> client -> app) works end-to-end.
Not a real feature test - Phase 8 test cases build on top of this fixture foundation.
"""

from httpx import AsyncClient


async def test_health_check(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
