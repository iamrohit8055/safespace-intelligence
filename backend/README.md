# SafeSpace Intelligence — Backend Service

The backend service for SafeSpace Intelligence is built with **FastAPI**, **PostgreSQL 17**, **PostGIS**, **SQLAlchemy 2.x**, and **Alembic**, managed with **uv**.

---

## Architecture Overview

The backend uses a **modular monolith** architecture adhering to clean separation of concerns:

- `app/api/v1/`: Versioned API routing and endpoint declarations.
- `app/core/`: Configuration via `pydantic-settings`, security foundations, and centralized exception handling.
- `app/database/`: SQLAlchemy 2.x declarative Base, connection pooling, and session lifecycle management.
- `app/health/`: Application and database health verification routes.
- `alembic/`: Database migration environment and version-controlled migration scripts.
- `tests/`: Comprehensive Pytest test suite with isolated fixtures.

---

## Prerequisites

- **Python:** 3.12 (`uv` automatically manages the Python toolchain)
- **uv:** Package and virtual environment manager (`>= 0.12.0`)
- **Docker & Docker Compose:** For running PostgreSQL 17 + PostGIS

---

## Local Development Setup

### 1. Configure Environment Variables

Copy the template from the repository root:

```bash
cp ../.env.example .env
```

Ensure `.env` contains your database configuration and development secrets.

### 2. Install Dependencies

Using `uv`, sync the virtual environment and install all dependencies (including development tools):

```bash
uv sync --all-groups
```

### 3. Start Database Infrastructure

From the project root:

```bash
docker compose up -d postgres
```

Verify that PostgreSQL and PostGIS are operational:

```bash
docker compose exec postgres psql -U safespace_user -d safespace_db -c "SELECT PostGIS_Version();"
```

### 4. Run Database Migrations

Apply all database migrations up to `head`:

```bash
uv run alembic upgrade head
```

To roll back the last migration:

```bash
uv run alembic downgrade -1
```

> **Note:** The initial migration (`0001_enable_postgis`) enables PostGIS on upgrade and intentionally preserves the extension on downgrade (no-op) to avoid cascading deletion of shared spatial infrastructure.

### 5. Start the Development Server

Start the FastAPI application with auto-reload:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The interactive API documentation is available at:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **OpenAPI Schema:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Health Check Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | High-level application health and version info |
| `GET` | `/api/v1/health` | API v1 operational status |
| `GET` | `/api/v1/health/database` | Verifies active database connectivity (`SELECT 1`) |

---

## Running Tests

Execute the Pytest test suite:

```bash
uv run pytest
```

Execute tests with coverage report:

```bash
uv run pytest --cov=app
```

---

## Code Quality & Formatting

Linting and formatting are enforced with **Ruff**:

```bash
# Check for lint errors
uv run ruff check .

# Automatically apply safe fixes
uv run ruff check --fix .

# Check code formatting
uv run ruff format --check .

# Format code
uv run ruff format .
```
