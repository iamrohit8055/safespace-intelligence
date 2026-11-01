# SafeSpace Intelligence

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com)
[![PostgreSQL 17](https://img.shields.io/badge/PostgreSQL-17-336791.svg)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-3.5-green.svg)](https://postgis.net/)
[![uv](https://img.shields.io/badge/uv-managed-blueviolet.svg)](https://github.com/astral-sh/uv)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

SafeSpace Intelligence is a location-based public-space infrastructure auditing platform. It empowers citizens and communities to identify, report, and prioritize infrastructure deficiencies—such as poor street lighting, damaged pedestrian pathways, obstructed visibility, missing public assistance facilities, and neglected public-space maintenance.

The backend ingests verified observations, computes a **Safety Deficiency Index (SDI)**, generates algorithmic recommendations, and provides municipal authorities with data-driven infrastructure prioritization workflows.

---

## Technology Stack

| Component | Technology | Description |
|---|---|---|
| **Language** | Python 3.12 | Modern syntax, typed, high performance |
| **Framework** | FastAPI | High-performance asynchronous API framework |
| **Database** | PostgreSQL 17 | Relational persistence engine |
| **Geospatial Extension** | PostGIS 3.5 | Spatial indexing and geometry operations |
| **ORM** | SQLAlchemy 2.x | Synchronous 2.0-style database abstraction |
| **Database Driver** | psycopg 3 (binary) | Next-generation PostgreSQL DBAPI driver |
| **Migrations** | Alembic | Version-controlled database schema migrations |
| **Validation** | Pydantic v2 | High-throughput data parsing and schema validation |
| **Configuration** | pydantic-settings | Environment-based 12-factor configuration |
| **Package Manager** | uv | Ultra-fast Python package and project manager |
| **Testing** | Pytest + HTTPX | Automated test runner with test client |
| **Code Quality** | Ruff | Ultra-fast linter and formatter |
| **Containers** | Docker & Docker Compose | Containerized database and services |

---

## Repository Structure

```text
safespace-intelligence/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                  # FastAPI application entrypoint & factory
│   │   │
│   │   ├── api/                     # API routing and versions
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       └── router.py        # API v1 route aggregator
│   │   │
│   │   ├── core/                    # Core configuration and error handling
│   │   │   ├── __init__.py
│   │   │   ├── config.py            # Pydantic Settings management
│   │   │   └── exceptions.py        # Centralized exception handlers
│   │   │
│   │   ├── database/                # Database engine & session layer
│   │   │   ├── __init__.py
│   │   │   ├── base.py              # SQLAlchemy DeclarativeBase
│   │   │   └── session.py           # SessionLocal, connection pooling, get_db
│   │   │
│   │   └── health/                  # Health check endpoints
│   │       ├── __init__.py
│   │       └── routes.py            # /health, /api/v1/health, /api/v1/health/database
│   │
│   ├── tests/                       # Automated test suite
│   │   ├── __init__.py
│   │   ├── conftest.py              # Pytest fixtures and test environment setup
│   │   └── test_health.py           # Health endpoint and error handling tests
│   │
│   ├── alembic/                     # Database migrations
│   │   ├── env.py                   # Migration environment setup
│   │   ├── script.py.mako           # Migration script template
│   │   └── versions/
│   │       └── 0001_enable_postgis.py # PostGIS extension enablement
│   ├── alembic.ini                  # Alembic configuration
│   ├── pyproject.toml               # Python project configuration and dependencies
│   └── README.md                    # Backend-specific documentation
│
├── infrastructure/
│   └── docker/
│       └── README.md                # Infrastructure guide
│
├── docs/
│   └── architecture/
│       └── backend-foundation.md    # Architecture and technical design document
│
├── .env.example                     # Environment configuration template
├── .gitignore                       # Git ignore rules
├── docker-compose.yml               # PostgreSQL 17 + PostGIS container definition
└── README.md                        # Project root documentation
```

---

## Prerequisites

Ensure the following tools are installed on your host system:

1. **Python 3.12** or **uv** (uv automatically installs and manages Python 3.12 if not present).
2. **Docker & Docker Compose** (for running PostgreSQL 17 + PostGIS).
3. **Git** for version control.

---

## Local Setup Instructions

### 1. Clone & Configure Environment

```bash
# Clone the repository
git clone <repository-url>
cd safespace-intelligence

# Create your local .env configuration from the template
cp .env.example .env
```

Review `.env` and configure your credentials. The defaults are pre-configured for local containerized development.

### 2. Dependency Management with `uv`

All dependencies are defined in `backend/pyproject.toml` and managed by `uv`.

```bash
cd backend

# Sync virtual environment and install all dependencies (including dev tools)
uv sync --all-groups
```

---

## Docker Infrastructure Commands

Start the containerized PostgreSQL 17 + PostGIS service:

```bash
# From the repository root
docker compose up -d postgres

# Check container status
docker compose ps

# View database logs
docker compose logs -f postgres

# Verify PostGIS version in the running container
docker compose exec postgres psql -U safespace_user -d safespace_db -c "SELECT PostGIS_Version();"

# Stop the database container
docker compose down
```

---

## Database Migrations

Database schema changes are managed exclusively through **Alembic**:

```bash
cd backend

# Apply all migrations to latest version
uv run alembic upgrade head

# Roll back the most recent migration
uv run alembic downgrade -1

# Generate a new autogenerated migration (in future phases)
uv run alembic revision --autogenerate -m "description_of_change"
```

---

## Running the Backend

Start the FastAPI application with live reload:

```bash
cd backend
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The server will be available at `http://localhost:8000`.

### Interactive API Documentation

When the server is running in development mode, visit:
- **Interactive Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative ReDoc UI:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Raw OpenAPI Schema:** [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

---

## Health Check Endpoints

| Method | URL | Description | Expected Status |
|---|---|---|---|
| `GET` | `/health` | Root application health check | `200 OK` |
| `GET` | `/api/v1/health` | API v1 status and version metadata | `200 OK` |
| `GET` | `/api/v1/health/database` | Database connectivity query check (`SELECT 1`) | `200 OK` (or `503` if DB unreachable) |

---

## Running Tests

Execute the automated test suite with Pytest:

```bash
cd backend
uv run pytest
```

Run tests with verbose output and coverage:

```bash
uv run pytest -v
```

---

## Code Quality & Formatting

Check code with Ruff:

```bash
cd backend

# Run linter
uv run ruff check .

# Run linter with autofix
uv run ruff check --fix .

# Check formatting
uv run ruff format --check .

# Apply formatting
uv run ruff format .
```

---

## Architecture Documentation

For deep technical insights on the architectural choices, connection lifecycles, and roadmap for adding future domain modules, see [docs/architecture/backend-foundation.md](docs/architecture/backend-foundation.md).
