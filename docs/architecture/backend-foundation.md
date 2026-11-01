# SafeSpace Intelligence — Backend Architecture Foundation

## 1. Architectural Philosophy: The Modular Monolith

SafeSpace Intelligence adopts a **modular monolith** architectural pattern for its backend service.

### Why Modular Monolith?

1. **Cognitive Load & Velocity:** In the early and foundational stages of platform development, microservices introduce premature distributed systems complexity—network latency, complex transactional semantics, distributed tracing, and orchestration overhead. A modular monolith provides the productivity of a unified codebase while enforcing strict module boundaries.
2. **Domain Boundary Cohesion:** SafeSpace Intelligence coordinates geospatial reports, verification workflows, Safety Deficiency Index (SDI) algorithmic computation, and authority maintenance tracking. These domains have strong relational consistency needs (e.g., geospatial queries joined with inspector verification logs and maintenance schedules). A shared PostgreSQL database with PostGIS handles spatial queries and cross-domain transactions efficiently.
3. **Future Microservices Readability:** By strictly adhering to layered separation and avoiding cross-module leaks, individual domains (such as the SDI Intelligence Engine or Background GIS Analysis) can be extracted into dedicated microservices in later phases if scale necessitates.

---

## 2. Application Layering

The codebase is structured into distinct, decoupled layers to maintain single responsibility and clean dependency flow:

```
┌────────────────────────────────────────────────────────┐
│                      Client Layer                      │
│        (Citizen Web/Mobile Apps, Admin Portals)        │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / JSON
┌───────────────────────────▼────────────────────────────┐
│                       API Layer                        │
│             FastAPI Routers (api/v1/*, health)         │
└───────────────────────────┬────────────────────────────┘
                            │ Validated Schemas (Pydantic v2)
┌───────────────────────────▼────────────────────────────┐
│                    Service Layer                       │
│    (Business logic, SDI calculations, verification)    │
└───────────────────────────┬────────────────────────────┘
                            │ Domain Entities / Repositories
┌───────────────────────────▼────────────────────────────┐
│                   Persistence Layer                    │
│   SQLAlchemy 2.x Declarative Models & Session Pool     │
└───────────────────────────┬────────────────────────────┘
                            │ psycopg 3 / SQL
┌───────────────────────────▼────────────────────────────┐
│                    Database Layer                      │
│               PostgreSQL 17 + PostGIS                  │
└────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

1. **API Endpoints (`app/api/` & `app/health/`):**
   - HTTP request parsing, status code handling, header negotiation.
   - Delegates business operations strictly to service/domain layers; no business logic in route functions.
2. **Core Foundation (`app/core/`):**
   - Centralized configuration via `pydantic-settings`.
   - Security primitives, token management, and centralized exception handling.
3. **Database Foundation (`app/database/`):**
   - Declarative `Base` (`DeclarativeBase`), engine configuration with pre-ping connection pool verification, and dependency-injected session management.
4. **Future Layers (Phases 2+):**
   - **Schemas (`app/schemas/`):** Pydantic v2 request/response validation schemas.
   - **Models (`app/models/`):** SQLAlchemy ORM models with PostGIS geometry types.
   - **Repositories (`app/repositories/`):** Encapsulated data access and spatial query operations.
   - **Services (`app/services/`):** Domain workflows (verification, report lifecycle).
   - **Engines (`app/engines/`):** SDI index algorithms, geospatial clustering, scoring heuristics.

---

## 3. Database Connection Flow & Lifecycle Management

Database connection management is designed to eliminate session leaks and maintain high availability:

```
Incoming Request
       │
       ▼
Depends(get_db) ────► SessionLocal() ────► Engine Connection Pool
       │                     │                        │
       │                     ▼                        │ (pool_pre_ping=True)
       │              Yield Session ──────────────────┘
       │                     │
       ▼                     ▼
Route Handler ◄─── Execute Query / ORM
       │
       ▼
Response Returned
       │
       ▼
finally: db.close() ──► Release Connection back to Pool
```

- **Pre-Ping Verification:** `pool_pre_ping=True` ensures that stale or dropped connections (e.g., during database container restarts or idle socket timeouts) are detected and transparently discarded before query execution.
- **Dependency Injection:** The `get_db` generator dependency guarantees that every HTTP request acquires a session and closes it in a `finally` block, preventing connection pooling exhaustion.
- **Synchronous Paradigm:** Synchronous SQLAlchemy 2.x with psycopg 3 is employed for predictable transactional boundaries, low cognitive overhead, and consistent PostGIS integration.

---

## 4. Migration Strategy with Alembic

SafeSpace Intelligence strictly enforces version-controlled migrations for all schema modifications:

- **No `create_all`:** `Base.metadata.create_all()` is forbidden in production and development to prevent untracked schema drift.
- **Environment Integration (`alembic/env.py`):**
  - Database connection strings are loaded directly from `app.core.config.get_settings()`, avoiding duplicate configuration in `alembic.ini`.
  - `target_metadata` links to `Base.metadata`, enabling Alembic autogeneration for model changes in subsequent phases.
- **PostGIS Bootstrapping:**
  - Migration `0001_enable_postgis.py` enables the `postgis` extension via `CREATE EXTENSION IF NOT EXISTS postgis;`.
  - Downgrade intentionally preserves the `postgis` extension (no-op) to avoid cascading data loss or breaking dependent spatial objects and extensions.

---

## 5. Docker Infrastructure & Security

PostgreSQL 17 and PostGIS are provisioned using Docker Compose:

- **Official PostGIS Image:** Uses `postgis/postgis:17-3.5`.
- **Health Checks:** Uses `pg_isready` with interval, timeout, and retry limits to allow orchestration tools to verify service readiness before dependent services connect.
- **Network Isolation:** Services communicate across an internal bridge network (`safespace_network`).
- **Security Hardening:** Host port mapping is bound explicitly to `127.0.0.1` (`127.0.0.1:${POSTGRES_PORT:-5432}:5432`) to prevent accidental public exposure on host network interfaces.
- **Persistence:** A named Docker volume (`safespace_postgres_data`) retains database state across container lifecycle events.

---

## 6. How Future Modules Should Be Added

When adding new domains (e.g., Reports, Verification, SDI Calculation) in subsequent phases:

1. **Database Models:**
   - Define ORM models in `app/models/<domain>.py` inheriting from `app.database.base.Base`.
   - Register models in `app/models/__init__.py` so Alembic detects them during autogeneration.
2. **Migrations:**
   - Generate a revision: `uv run alembic revision --autogenerate -m "create_<domain>_table"`.
   - Review and verify the generated migration script in `alembic/versions/`.
   - Apply: `uv run alembic upgrade head`.
3. **Schemas:**
   - Define request/response DTOs in `app/schemas/<domain>.py` with Pydantic v2.
4. **Service & Logic:**
   - Implement business logic in `app/services/<domain>_service.py`.
   - Keep route handlers thin; routes only parse requests, invoke services, and return schemas.
5. **API Routing:**
   - Create router in `app/api/v1/<domain>.py`.
   - Mount router into `app/api/v1/router.py` with appropriate prefix and tags.
6. **Tests:**
   - Add unit and integration tests under `tests/test_<domain>.py`.
