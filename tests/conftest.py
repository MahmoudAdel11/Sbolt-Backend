"""Shared pytest fixtures: test database lifecycle, session isolation, and the API client.

Test DB strategy
-----------------
Tests run against a real Postgres instance (not SQLite) via TEST_DATABASE_URL, because the
schema relies on Postgres-specific features (native enums for UserRole/RideStatus, `Numeric`
lat/lng columns) that don't translate faithfully to SQLite. Locally this points at a throwaway
database on the same Postgres server used for manual testing throughout development; in CI it
points at the `postgres:16` service container already defined in .github/workflows/ci.yml, so
no workflow changes are needed - just set TEST_DATABASE_URL as an extra env var there.

Migrations are applied once per test session (a session-scoped, autouse fixture), not once per
test, since alembic upgrade head against an already-current DB is wasted work repeated
dozens/hundreds of times. The engine itself is function-scoped: pytest-asyncio gives each async
test its own event loop by default, and an AsyncEngine/connection pool created on one loop cannot
be reused from another, so the engine (cheap to create) is rebuilt per test while the expensive
part - migrations - stays session-scoped.

Isolation is per-test transaction rollback: each test runs inside an outer transaction plus a
SAVEPOINT (`begin_nested`). The app's `get_db_session` override yields that same session; if
application code calls `session.commit()` (as `get_db_session` normally does), only the SAVEPOINT
is released - the outer transaction is rolled back unconditionally at the end of the test via a
`session.begin_nested()` restart hook. This is the standard SQLAlchemy 2.0 async pattern for fast,
fully-isolated tests without truncating tables or recreating the schema per test.
"""

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://yalla_go:yalla_go@localhost:5432/yalla_go_test",
)

# The app reads DATABASE_URL/SECRET_KEY via app.core.config.Settings at import time
# (app.main builds the FastAPI app at module scope). Set required env vars *before*
# importing anything from `app` so Settings() resolves against the test database.
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production-use-only")

from alembic.config import Config  # noqa: E402

from alembic import command  # noqa: E402
from app.core.rate_limit import limiter  # noqa: E402
from app.infrastructure.db.session import get_db_session  # noqa: E402
from app.main import app  # noqa: E402
from tests.factories import create_user  # noqa: E402


def _alembic_config() -> Config:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    return config


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture(scope="session", autouse=True)
def _apply_migrations() -> None:
    """Run alembic upgrade head once per test session, against the test database only."""
    command.upgrade(_alembic_config(), "head")


@pytest_asyncio.fixture
async def engine() -> AsyncGenerator[AsyncEngine]:
    """Function-scoped: an AsyncEngine's connection pool is tied to the event loop it was
    created on, and pytest-asyncio gives each test its own loop by default.
    """
    test_engine = create_async_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    try:
        yield test_engine
    finally:
        await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession]:
    """A session scoped to a single test, wrapped in a transaction that's always rolled back.

    A SAVEPOINT is used so that application code calling session.commit() (as
    get_db_session does in real request handling) doesn't end the isolation - the
    outer connection-level transaction is rolled back unconditionally afterward.
    """
    connection = await engine.connect()
    outer_transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )
    session = session_factory()

    try:
        yield session
    finally:
        await session.close()
        await outer_transaction.rollback()
        await connection.close()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """An httpx.AsyncClient wired to the FastAPI app, sharing db_session's transaction.

    The rate limiter is a module-level singleton keyed by remote address, which is
    constant across requests made through ASGITransport (there's no real client IP).
    Without a reset, request counts would accumulate across every test in the same
    process rather than resetting per-request as they would for distinct real clients,
    so it's cleared before each test to keep tests independent of run order/count.
    """
    limiter.reset()

    async def _override_get_db_session() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db_session] = _override_get_db_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client

    app.dependency_overrides.pop(get_db_session, None)


@pytest_asyncio.fixture
async def registered_user(db_session: AsyncSession):
    """A persisted rider with a real hashed password and a real JWT, for tests that need an
    authenticated user but aren't specifically testing the register/login flow itself.
    """
    return await create_user(db_session)


def auth_headers(token: str) -> dict[str, str]:
    """Shared across test files that need an Authorization header - not conftest-fixture-only,
    just a plain helper co-located here since 2+ test files already needed identical logic.
    """
    return {"Authorization": f"Bearer {token}"}
