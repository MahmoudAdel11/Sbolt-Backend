# Yalla Go — Backend

Backend service for the Yalla Go ride-hailing application, built with FastAPI following Clean Architecture.

## Tech Stack

- **Framework:** FastAPI
- **Language:** Python 3.13+
- **Database:** PostgreSQL
- **ORM:** SQLAlchemy 2.x (async)
- **Migrations:** Alembic
- **Validation:** Pydantic v2
- **Auth:** JWT
- **Testing:** pytest, pytest-asyncio, httpx

## Architecture

The codebase is organized into four layers. Dependencies only point inward — outer layers depend on inner layers, never the reverse.

```
app/
├── api/              # API layer: routers, request/response wiring, DI, exception handlers
│   └── v1/           # Versioned routes (api/v1/routes/*)
├── application/       # Application layer: use cases / orchestration (business workflows)
├── domain/            # Domain layer: entities, value objects, repository interfaces
├── infrastructure/     # Infrastructure layer: DB, external services, repository implementations
└── core/              # Cross-cutting: settings, logging, exceptions
```

**Rule:** routes never contain business logic. A route only parses the request, calls a use case, and shapes the response. Business rules live in `application/` and `domain/`; persistence details live in `infrastructure/`.

## Project Setup

### 1. Prerequisites

- Python 3.13+
- PostgreSQL running locally (or reachable via `DATABASE_URL`)

### 2. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# edit .env — set DATABASE_URL and SECRET_KEY at minimum
```

### 4. Run database migrations

```bash
alembic upgrade head
```

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Visit `http://localhost:8000/api/v1/health` to confirm the service is up, and `http://localhost:8000/docs` for interactive API docs.

## Running with Docker

```bash
cp .env.example .env
# edit .env — SECRET_KEY at minimum; DATABASE_URL is overridden by
# docker-compose.yml to point at the db service, so leave it as-is
docker compose up --build
```

The API is reachable at `http://localhost:8000/api/v1/health`.

**Migrations run automatically on container start** (see `docker-entrypoint.sh`: `alembic upgrade head` runs before `uvicorn` starts). This was chosen over a manual `alembic upgrade head` step because `docker compose up` is meant to be a single-command bootstrap for the whole stack — a forgotten manual migration step would leave the API crash-looping against a schema-less database with no obvious cause. `alembic upgrade head` is idempotent, so re-running it on every container restart is safe.

To apply migrations manually against the running containers instead (e.g. to inspect output separately):

```bash
docker compose exec api alembic upgrade head
```

## Creating a new migration

```bash
alembic revision --autogenerate -m "add users table"
alembic upgrade head
```

Autogenerate detects new models only if they're imported in `alembic/env.py` (see the comment near `target_metadata`).

## Running tests

```bash
pytest
```
