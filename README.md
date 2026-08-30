# Sbolt — Backend

FastAPI backend for **Sbolt**, a scooter-hailing platform. For the full project overview, screenshots, and demo, see the [iOS repository](https://github.com/MahmoudAdel11/Sbolt-iOS).

## Tech Stack

| | |
|---|---|
| Framework | FastAPI (Python) |
| Database | PostgreSQL |
| ORM | SQLAlchemy (async) |
| Migrations | Alembic |
| Auth | JWT — short-lived access tokens + DB-backed, sliding-expiration refresh tokens |
| Architecture | Clean Architecture (API / Application / Domain / Infrastructure) |
| Testing | pytest, real HTTP round-trip integration tests against a live Postgres instance |

## Architecture Highlights

- **Repository Pattern** with protocol-based abstractions, mirrored on the iOS client — no business logic tied to a specific ORM call.
- **Row-level database locking** on ride acceptance, preventing two drivers from claiming the same ride simultaneously.
- **Sliding-expiration refresh tokens**: a DB-backed session (not a second stateless JWT) — sliding expiration requires extending an existing session in place, which a JWT's baked-in expiry can't do without minting a new token anyway.
- **Tier-hierarchy filtering**: available-ride queries filter by the driver's own scooter tier via a simple rank comparison, with zero extra database queries.
- Clear separation between rider-facing and driver-facing response shapes — a rider never receives a driver's phone number or email, for example.

## Getting Started

### Prerequisites
- Python 3.13+
- PostgreSQL running locally (or via Docker)

### Setup

```bash
# Clone and enter the project
git clone https://github.com/MahmoudAdel11/Sbolt-Backend.git
cd Sbolt-Backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# edit .env with your local database credentials

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`, with interactive docs at `http://localhost:8000/docs`.

### Running with Docker

```bash
docker-compose up
```

### Running Tests

```bash
pytest
```

## Project Structure

```
app/
├── api/            # Route handlers, request/response schemas, dependencies
├── application/     # Use cases (business logic orchestration)
├── domain/          # Entities, enums, core business rules
└── infrastructure/  # Database models, repository implementations
```

## Known Limitations (tracked, not hidden)

- No live geocoding — the client (iOS) resolves and sends human-readable addresses; the backend only stores what it's given.
- No admin panel for tier pricing (currently hardcoded constants in `pricing.py`).
- Driver scooter type is self-declared at registration with no verification step.

---

Built as the backend half of the Sbolt project — see the [iOS repo](https://github.com/MahmoudAdel11/Sbolt-iOS) for the full app.
