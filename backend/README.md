# SafeSpace Intelligence — Backend Service

The backend service for SafeSpace Intelligence is built with **FastAPI**, **PostgreSQL 17**, **PostGIS**, **SQLAlchemy 2.x**, and **Alembic**, managed with **uv**.

---

## Architecture Overview

The backend uses a **modular monolith** architecture adhering to clean separation of concerns:

- `app/api/v1/`: Versioned API routing and endpoint declarations.
- `app/core/`: Configuration via `pydantic-settings`, security foundations, and centralized exception handling.
- `app/database/`: SQLAlchemy 2.x declarative Base, connection pooling, and session lifecycle management.
- `app/models/`: Domain-driven SQLAlchemy 2.x declarative models (`iam`, `geography`, `reporting`, `verification`).
- `app/health/`: Application and database health verification routes.
- `alembic/`: Database migration environment and version-controlled migration scripts.
- `tests/`: Comprehensive Pytest test suite with isolated fixtures.

---

## Database Architecture & Core Models

The SafeSpace Intelligence core database schema is organized across four distinct functional domains:

### 1. Identity & Access Management (`app/models/iam.py`)
- **`roles` (`Role`)**: System authorization personas (`citizen`, `verifier`, `maintenance`, `admin`). Uses `SMALLINT` identity primary keys.
- **`users` (`User`)**: User accounts with Argon2id password hashes, audit flags (`is_active`, `is_verified`), and case-insensitive lower email uniqueness. Uses `UUID` primary keys (`gen_random_uuid()`).
- **`user_roles` (`UserRole`)**: Association table establishing composite primary key `(user_id, role_id)` with `assigned_by` audit trail.

### 2. Geospatial Jurisdictions (`app/models/geography.py`)
- **`administrative_areas` (`AdministrativeArea`)**: Hierarchical municipal jurisdiction boundaries (`municipality`, `district`, `ward`, `zone`) using PostGIS `MultiPolygon` (EPSG:4326), valid geometry checks, self-parenting prevention, and spatial GiST indexing (`idx_admin_areas_boundary_gist`). Uses `UUID` primary keys.

### 3. Public-Space Reporting (`app/models/reporting.py`)
- **`report_categories` (`ReportCategory`)**: Pure taxonomy definitions (`STREET_LIGHTING`, `PEDESTRIAN_PATHWAYS`, `VISIBILITY`, `PUBLIC_ASSISTANCE`, `MAINTENANCE`). Uses `SMALLINT` identity primary keys. Excludes scoring weights to decouple taxonomy from methodology revisions.
- **`reports` (`Report`)**: Geographically tagged deficiency observations using PostGIS `Point` (EPSG:4326) with coordinate bounds validation `[-180, 180] x [-90, 90]`, self-duplicate prevention, and valid initial statuses (`SUBMITTED`, `UNDER_VERIFICATION`, `VERIFIED`, `REJECTED`, `ARCHIVED`). Indexed with planar GiST (`idx_reports_location_gist`), functional geography GiST (`idx_reports_location_geog_gist`), and operational composite/partial B-Trees (`idx_reports_status_submitted_at`, `idx_reports_admin_area_category`, `idx_reports_reporter_submitted`, `idx_reports_duplicate_of`). Uses `UUID` primary keys.
- **`report_media` (`ReportMedia`)**: Photographic evidence metadata strictly limited to image formats (`image/jpeg`, `image/png`, `image/webp`). Enforces positive pixel dimensions (`width > 0`, `height > 0` when non-null), SHA-256 hex checksum validation, max 15 MB file size, and strict deduplication constraints per report. Excludes video files, HEIC, and raw EXIF blobs. Uses `UUID` primary keys.

### 4. Verification & Audit History (`app/models/verification.py`)
- **`report_verifications` (`ReportVerification`)**: Moderation outcomes (`VERIFIED`, `REJECTED`, `FLAGGED`, `MARKED_DUPLICATE`) with check-constraint enforced conditional severity (1–5) and rejection reasoning. Uses `UUID` primary keys.
- **`report_status_history` (`ReportStatusHistory`)**: Immutable audit ledger capturing state transitions (`SUBMITTED`, `UNDER_VERIFICATION`, `VERIFIED`, `REJECTED`, `ARCHIVED`). Uses `BIGINT` identity primary keys. `from_status` is nullable **only** on the initial transition to `SUBMITTED`.

### 5. Intelligence Engine & Versioned Scoring (`app/models/intelligence.py`)
- **`scoring_configurations` (`ScoringConfiguration`)**: Versioned SDI methodologies (`version`, `name`, `description`, `is_active`, `methodology_metadata`). Uses `SMALLINT` identity primary keys.
- **`scoring_configuration_weights` (`ScoringConfigurationWeight`)**: Decoupled category weights (`assigned_weight` summing to 1.0000) linking methodologies to the `report_categories` taxonomy.
- **`area_scores` (`AreaScore`)**: Calculated composite SDI results for administrative areas (`score`, `completeness_pct`, `participating_categories_count`, `eligible_reports_count`, `is_current`, `calculation_timestamp`). Protected by partial unique index `uq_area_scores_current` where `is_current = True`. Uses `UUID` primary keys.
- **`score_components` (`ScoreComponent`)**: Granular category deficiency contributions (`category_score`, `assigned_weight`, `normalized_weight`, `weighted_contribution`, `report_count`, `availability_state`). Uses `BIGINT` identity primary keys.
- **`report_confidence` (`ReportConfidence`)**: Multi-factor observation evidence reliability metrics (`evidence_confidence_score`, `is_current`, factor evaluation metrics). Uses `UUID` primary keys.
- **`area_confidence_scores` (`AreaConfidenceScore`)**: Aggregated area-level credibility and completeness metrics (`area_confidence_score`, `confidence_completeness_pct`, `is_current`). Protected by partial unique index `uq_area_confidence_current` where `is_current = True`. Uses `UUID` primary keys.
- **`area_confidence_components` (`AreaConfidenceComponent`)**: Granular per-category observation sample counts and mean confidence metrics. Uses `BIGINT` identity primary keys.

### 6. Inspection Priority Engine (`app/models/priority.py`)
- **`priority_configurations` (`PriorityConfiguration`)**: Versioned weighting configurations for operational municipal inspection planning (`sdi_weight`, `urgency_weight`, `unresolved_reports_weight`, `confidence_gap_weight`, `methodology_metadata`, `is_active`). Uses `SMALLINT` identity primary keys.
- **`area_priority_scores` (`AreaPriorityScore`)**: Multi-factor operational inspection priority rankings (`priority_score`, `priority_tier`, `sdi_score`, `observation_urgency_score`, `unresolved_reports_score`, `confidence_gap_score`, `is_current`, `calculated_at`). Protected by partial unique index `uq_area_priority_current` where `is_current = True`. Uses `UUID` primary keys.

### 7. Maintenance Management (`app/models/maintenance.py`)
- **`maintenance_tasks` (`MaintenanceTask`)**: Operational repair tasks for verified deficiency reports (`title`, `description`, `status`, `priority`, `assigned_to_id`, `created_by_id`, `allow_duplicate`, `duplicate_override_reason`). Protected by partial unique index `uq_maintenance_active_report_task` ensuring a single active task per report unless overridden by administrator. Uses `UUID` primary keys.
- **`maintenance_task_events` (`MaintenanceTaskEvent`)**: Immutable audit history of maintenance task status transitions (`from_status`, `to_status`, `notes`, `created_at`, `created_by_id`). Uses `BIGINT` identity primary keys.

### 8. Notifications (`app/models/notifications.py`)
- **`notifications` (`Notification`)**: User-targeted transactional alerts (`user_id`, `event_type`, `title`, `message`, `data`, `is_read`, `created_at`). Uses `UUID` primary keys.

### Transactional Report Submission Requirement
When a citizen submits a new report:
1. The initial `Report` record (with `status='SUBMITTED'`) and its initial `ReportStatusHistory` record (`from_status=None`, `to_status='SUBMITTED'`) **must be inserted in the exact same database transaction**.
2. If either insert fails, the transaction is rolled back in its entirety, preventing orphaned reports or status history gaps.
3. Hard deletions are restricted (`ON DELETE RESTRICT`) on both status history and verifications to maintain an unbroken audit trail.

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

> **Note:**
> - `0001_enable_postgis`: Enables PostGIS extension on upgrade and intentionally preserves the extension on downgrade (no-op) to avoid cascading deletion of shared spatial infrastructure.
> - `0002_core_database_architecture`: Creates the nine core domain tables, constraints, foreign keys, and indexes.
> - `0003_seed_initial_roles_and_categories`: Seeds baseline standard roles (`citizen`, `verifier`, `maintenance`, `admin`) and baseline deficiency categories (`STREET_LIGHTING`, `PEDESTRIAN_PATHWAYS`, `VISIBILITY`, `PUBLIC_ASSISTANCE`, `MAINTENANCE`). On downgrade, removes only seeded records while respecting foreign-key restrictions (`ON DELETE RESTRICT`).
> - `0004_intelligence_engine_sdi`: Creates tables for SDI calculation (`scoring_configurations`, `scoring_configuration_weights`, `area_scores`, `score_components`) and seeds baseline SDI methodology `v1.0.0`.
> - `0005_intelligence_confidence`: Creates tables for multidimensional evidence confidence and area-level credibility metrics (`report_confidence`, `area_confidence_scores`, `area_confidence_components`).
> - `0006_phase2_complete_architecture`: Creates tables for municipal inspection priority (`priority_configurations`, `area_priority_scores`), maintenance management (`maintenance_tasks`, `maintenance_task_events`), and in-app notifications (`notifications`), seeding baseline priority methodology `v1.0.0`.

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

## Identity & Access Management (IAM)

SafeSpace Intelligence implements a secure, stateless authentication and authorization subsystem built on industry-standard cryptographic practices.

### 1. Architecture & Security Mechanisms
- **Password Hashing:** Passwords are hashed using **Argon2id** (`argon2-cffi`), the winner of the Password Hashing Competition. Plaintext passwords must be between 8 and 128 characters to resist brute-force while mitigating algorithmic DoS attacks.
- **Stateless Tokens:** Access tokens are signed using **JWT (JSON Web Tokens)** with the **HS256** algorithm (`pyjwt`).
- **Standard Claims:** JWT tokens include `sub` (user UUID), `iat` (issued-at timestamp in UTC), and `exp` (expiration timestamp in UTC).
- **Bearer Authentication:** Authenticated requests provide the token via the `Authorization: Bearer <token>` header, parsed and validated by FastAPI dependency injection (`app.api.deps.get_current_user`).

### 2. Configuration Parameters
The IAM subsystem is configured through environment variables managed in `app.core.config.Settings`:

| Variable | Type | Default | Description |
|---|---|---|---|
| `JWT_SECRET_KEY` | `str` | `"insecure-dev-secret-key-change-in-production"` | Secret signing key for HS256. Validated at startup in `production` environment to require $\ge 32$ non-default characters. |
| `JWT_ALGORITHM` | `str` | `"HS256"` | JWT digital signature algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `int` | `60` | Token lifetime duration in minutes (default: 1 hour). |

### 3. Authentication Endpoints

All authentication endpoints are mounted under `/api/v1/auth`:

| Method | Path | Summary | Auth Required | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register citizen account | No | Registers a new user with email, password, and optional full name. Atomically inserts into `users` and assigns `citizen` role in `user_roles`. Self-assignment of privileged roles (`admin`, `verifier`, `maintenance`) is strictly prevented. Returns `409 Conflict` if the email is already registered. |
| `POST` | `/api/v1/auth/login` | Authenticate credentials | No | Validates email and password against Argon2id hash. Returns `200 OK` with a signed Bearer JWT token upon success, and updates `last_login_at`. Returns a generic `401 Unauthorized` on invalid credentials or inactive accounts. |
| `GET` | `/api/v1/auth/me` | Current user profile | Bearer Token | Resolves the authenticated user from the Bearer token and returns user details (`id`, `email`, `full_name`, `is_active`, `is_verified`, `roles`, `created_at`). Rejects inactive or removed accounts with `401 Unauthorized`. |

### 4. Role-Based Access Control (RBAC)

Authorization is enforced via the `require_roles(*allowed_roles)` dependency factory located in `app.api.deps`:
- **Role Verification:** Extracts the user's assigned roles from the database and checks for intersection with permitted roles.
- **Access Denial:** Returns `HTTP 403 Forbidden` with detail `"Access forbidden: You do not possess the required role permissions."` if the user lacks the required role.
- **Example Usage:**
  ```python
  from typing import Annotated
  from fastapi import APIRouter, Depends
  from app.api.deps import require_roles
  from app.models.iam import User

  router = APIRouter()
  admin_only = require_roles("admin")


  @router.delete("/reports/{report_id}")
  def purge_report(
      report_id: str,
      current_user: Annotated[User, Depends(admin_only)],
  ): ...
  ```

---

## Report Management

The Report Management subsystem handles citizen-submitted infrastructure deficiency observations, spatial containment queries via PostGIS, and audit status tracking.

### 1. Architecture Overview
- **Service Layer Separation:** Business logic, category validation, spatial resolution, and transactional status history tracking reside cleanly within `app/services/reports.py`.
- **Geospatial Processing:** Coordinates are validated within WGS 84 boundaries ($[-180, 180] \times [-90, 90]$) and stored as PostGIS `geometry(Point, 4326)` ($X = \text{longitude}$, $Y = \text{latitude}$).
- **Spatial Jurisdiction Assignment:** Incoming report coordinates are evaluated using PostGIS `ST_Covers` against municipal boundaries in `administrative_areas`. Overlapping areas resolve hierarchically by granularity (`ward` $\to$ `zone` $\to$ `district` $\to$ `municipality`) with `code ASC` as a tie-breaker. Coordinates outside all boundaries remain unassigned (`administrative_area_id = NULL`).
- **Atomic Status History:** When a citizen submits a report, the initial `Report` record (`status = 'SUBMITTED'`) and its initial `ReportStatusHistory` audit entry (`from_status = NULL`, `to_status = 'SUBMITTED'`) are written and committed in the exact same database transaction.
- **Data Protection & Sanitization:** Public endpoints sanitize output, exposing only necessary observational data. Internal notes, raw storage paths, and other citizens' reports are strictly inaccessible. Attempting to view another citizen's report yields `404 Not Found`.

### 2. Endpoints

All reporting endpoints are mounted under `/api/v1/reports`:

| Method | Path | Summary | Auth Required | Description |
|---|---|---|---|---|
| `POST` | `/api/v1/reports` | Submit report | Citizen JWT | Submits a new deficiency observation. Resolves category, verifies bounds, assigns administrative area via `ST_Covers`, and writes initial status history. Returns `201 Created`. |
| `GET` | `/api/v1/reports` | List citizen reports | Citizen JWT | Returns a paginated list of reports submitted by the calling citizen, ordered deterministically by `submitted_at DESC`, `id DESC`. |
| `GET` | `/api/v1/reports/{report_id}` | Get report detail | Citizen JWT | Retrieves sanitized report details. Returns `404 Not Found` if nonexistent or owned by another user. |

### 3. Request & Response Examples

#### Submit a Report (`POST /api/v1/reports`)
**Headers:**
```http
Authorization: Bearer <citizen_jwt_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "category_code": "STREET_LIGHTING",
  "title": "Broken street light on Main St",
  "description": "The lamp post is completely dark, causing serious pedestrian risk.",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "address_text": "123 Main Street, City Center"
}
```

**Response (`201 Created`):**
```json
{
  "id": "b6c82bc2-5df4-4ced-a09c-5ae8d8a1719d",
  "reporter_id": "36298e13-eea5-4c15-a416-b9f43e8fa58e",
  "category": {
    "id": 1,
    "code": "STREET_LIGHTING",
    "name": "Street Lighting"
  },
  "administrative_area": {
    "id": "8d3e2304-4df2-4754-bca5-b3e6e872c832",
    "name": "Downtown Ward",
    "code": "WARD-01",
    "area_type": "ward"
  },
  "title": "Broken street light on Main St",
  "description": "The lamp post is completely dark, causing serious pedestrian risk.",
  "latitude": 40.7128,
  "longitude": -74.006,
  "address_text": "123 Main Street, City Center",
  "status": "SUBMITTED",
  "observed_at": "2026-11-02T02:00:00Z",
  "submitted_at": "2026-11-02T02:00:01Z",
  "updated_at": "2026-11-02T02:00:01Z"
}
```

#### List Reports (`GET /api/v1/reports?limit=20&offset=0`)
**Response (`200 OK`):**
```json
{
  "items": [
    {
      "id": "b6c82bc2-5df4-4ced-a09c-5ae8d8a1719d",
      "reporter_id": "36298e13-eea5-4c15-a416-b9f43e8fa58e",
      "category": {
        "id": 1,
        "code": "STREET_LIGHTING",
        "name": "Street Lighting"
      },
      "administrative_area": null,
      "title": "Broken street light on Main St",
      "description": "The lamp post is completely dark, causing serious pedestrian risk.",
      "latitude": 40.7128,
      "longitude": -74.006,
      "address_text": "123 Main Street, City Center",
      "status": "SUBMITTED",
      "observed_at": "2026-11-02T02:00:00Z",
      "submitted_at": "2026-11-02T02:00:01Z",
      "updated_at": "2026-11-02T02:00:01Z"
    }
  ],
  "total": 1,
  "limit": 20,
  "offset": 0
}
```

### 4. Media Upload Limitations
To protect against storage reference forgery and arbitrary path tampering, direct citizen submission of storage keys, bucket names, and media references is **strictly prohibited**. Media association is deferred to a dedicated media upload pipeline milestone that will provide signed upload URLs, server-side MIME verification, and SHA-256 checksum validation.

---

## Report Verification & Moderation

The Verification and Moderation subsystem provides an auditable, append-only inspection workflow for municipal verifiers and administrators to review citizen observations.

### 1. Lifecycle Finite State Machine (FSM)

Reports progress through strict, valid state transitions enforced transactionally in the service layer:

```
     +---------------+
     |   SUBMITTED   |
     +---------------+
             |
             | start-verification (SELECT ... FOR UPDATE)
             v
   +--------------------+
+->| UNDER_VERIFICATION |<-+
|  +--------------------+  |
|        |          |      |
| verify |          | reject
|        v          v      |
|  +----------+  +----------+
|  | VERIFIED |  | REJECTED |
|  +----------+  +----------+
|        |          |
+--------+-- reopen +------+
```

| Current Status | Target Status | Operation | Requirements |
|---|---|---|---|
| `SUBMITTED` | `UNDER_VERIFICATION` | `POST .../start-verification` | Concurrency-safe row lock (`FOR UPDATE`). |
| `UNDER_VERIFICATION` | `VERIFIED` | `POST .../verify` | Mandatory physical severity score ($1–5$). Optional notes. |
| `UNDER_VERIFICATION` | `REJECTED` | `POST .../reject` | Mandatory categorical reason ($\le 50$ chars). Optional notes. |
| `VERIFIED` | `UNDER_VERIFICATION` | `POST .../reopen` | Mandatory justification reason. Preserves historical decisions. |
| `REJECTED` | `UNDER_VERIFICATION` | `POST .../reopen` | Mandatory justification reason. Preserves historical decisions. |

Invalid transitions (e.g. attempting to verify a `SUBMITTED` report or reopen an unfinalized report) return `HTTP 409 Conflict`.

### 2. Moderation & History Endpoints

| Method | Path | Summary | Auth Required | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/admin/reports/pending` | Inspection queue | Verifier / Admin | Returns a paginated FIFO queue of reports in `SUBMITTED` status (`submitted_at ASC`, `id ASC`). |
| `POST` | `/api/v1/admin/reports/{report_id}/start-verification` | Begin review | Verifier / Admin | Atomically transitions report to `UNDER_VERIFICATION` with `SELECT ... FOR UPDATE` row locking. |
| `POST` | `/api/v1/admin/reports/{report_id}/verify` | Approve report | Verifier / Admin | Assigns physical severity ($1–5$), transitions to `VERIFIED`, and writes append-only verification and status history rows. |
| `POST` | `/api/v1/admin/reports/{report_id}/reject` | Reject report | Verifier / Admin | Records categorical rejection reason, transitions to `REJECTED`, and writes append-only verification and status history rows. |
| `POST` | `/api/v1/admin/reports/{report_id}/reopen` | Reopen report | Verifier / Admin | Reopens a `VERIFIED` or `REJECTED` report back to `UNDER_VERIFICATION` with an audit reason without modifying prior records. |
| `GET` | `/api/v1/reports/{report_id}/verification-history` | View history | Authenticated | Retrieves chronological moderation decisions. Citizens can view only their own reports; verifiers/admins can view any. |

### 3. Append-Only Verification History & Severity Semantics
- **Severity Semantics:** `verified_severity` represents the assessed physical gravity of the infrastructure deficiency ($1 = \text{minor}$, $5 = \text{critical}$). It is distinct from evidence confidence and is stored separately in `report_verifications.verified_severity`.
- **Append-Only Immutability:** Prior `report_verifications` rows are never mutated or deleted on reopen. Every moderation outcome records a new discrete row timestamped in UTC.
- **Audit Ledger:** Every status transition writes a corresponding row to `report_status_history` capturing `from_status`, `to_status`, `changed_by_user_id`, and `reason`.

### 4. Duplicate Report Handling
Manual duplicate linking (`duplicate_of_id`) is supported by the underlying schema. Automated spatial deduplication, clustering, and duplicate moderation decisions (`MARKED_DUPLICATE`) are deferred to future intelligence engine milestones.

---

## Intelligence Engine & Safety Deficiency Index (SDI)

SafeSpace Intelligence features an automated, mathematically sound, reproducible intelligence engine that calculates the **Safety Deficiency Index (SDI)** for administrative areas.

> [!IMPORTANT]
> **Strict Semantic Boundary:** The Safety Deficiency Index (SDI) strictly measures **public-space physical infrastructure deficiencies** (such as defective street lights, fractured pedestrian pavements, line-of-sight obstructions, missing call boxes, and trash/litter accumulation). It **must NEVER** be interpreted or described as crime probability, personal safety probability, or criminal prediction.

### 1. Mathematical Scoring Foundation

1. **Category Deficiency Score:**
   For any category with eligible verified reports, the category deficiency score is derived directly from the arithmetic mean of verified physical severities ($\overline{\text{severity}} \in [1, 5]$):
   $$\text{Category Score} = \left(\frac{\overline{\text{severity}}}{5.0}\right) \times 100.00$$
   This ensures category scores are strictly bounded within $[20.00, 100.00]$ using `ROUND_HALF_UP` decimal arithmetic.

2. **Missing Data & Weight Re-Normalization:**
   Categories lacking eligible verified reports (or failing minimum observation thresholds) are marked as `INSUFFICIENT_DATA` with `category_score = None`. Unobserved categories are **never imputed as zero**.
   The engine dynamically re-normalizes assigned weights over observed categories:
   $$w_i' = \frac{w_i}{\sum_{j \in \text{observed}} w_j}$$
   $$\text{SDI} = \frac{\sum_{i \in \text{observed}} (\text{score}_i \times w_i)}{\sum_{j \in \text{observed}} w_j} = \sum_{i \in \text{observed}} (\text{score}_i \times w_i')$$

3. **Data Completeness:**
   Data completeness is calculated as the sum of nominal configuration weights belonging to observed categories:
   $$\text{Completeness (\%)} = \left(\sum_{i \in \text{observed}} w_i\right) \times 100.00$$

4. **Zero Coverage Handling:**
   If an administrative area has no eligible verified reports across all categories, $\text{SDI} = \text{None}$, completeness is $0.00\%$, and a human-readable reason (`"Insufficient eligible observations to compute representative SDI"`) is recorded.

### 2. Area Aggregation & Eligibility Filters

The intelligence engine query selects verified observations adhering to strict criteria:
- **Status Filter:** Report status must be strictly `'VERIFIED'`.
- **Area Association:** Report `administrative_area_id` matches the target area.
- **Deduplication:** Excludes reports flagged as duplicates (`duplicate_of_id IS NULL`).
- **Latest Verified Severity:** If a report underwent multiple verification cycles via reopening, only the most recent verification record's `verified_severity` is used.

### 3. Intelligence Endpoints

| Method | Path | Summary | Auth Required | Description |
|---|---|---|---|---|
| `GET` | `/api/v1/admin/intelligence/scoring-configurations` | List methodologies | Verifier / Admin | Lists versioned scoring configurations, category weights, and methodology metadata. |
| `POST` | `/api/v1/admin/intelligence/areas/{area_id}/calculate` | Compute area SDI | Admin | Atomically executes SDI calculation for an area, archives prior active scores (`is_current=False`), and records component breakdown. |
| `GET` | `/api/v1/admin/intelligence/areas/{area_id}/sdi` | Get current SDI | Verifier / Admin | Retrieves the active current SDI score and itemized category components for an area. |
| `GET` | `/api/v1/admin/intelligence/areas/{area_id}/history` | Calculation audit log | Verifier / Admin | Retrieves chronological history of all SDI calculations for an area ordered newest first. |
| `GET` | `/api/v1/admin/intelligence/duplicate-candidates` | List duplicate candidates | Verifier / Admin | Retrieves paginated candidate pairs detected by spatial and temporal proximity. |
| `GET` | `/api/v1/admin/intelligence/reports/{report_id}/duplicate-candidates` | Get report candidates | Verifier / Admin | Retrieves or detects duplicate candidate pairs involving the specified report. |
| `POST` | `/api/v1/admin/intelligence/duplicate-candidates/detect` | Batch candidate detection | Admin | Runs spatial PostGIS geography proximity detection across an administrative area or globally. |
| `POST` | `/api/v1/admin/intelligence/duplicate-candidates/{candidate_id}/review` | Review duplicate pair | Verifier / Admin | Records moderation decision (`CONFIRMED_DUPLICATE`, `NOT_DUPLICATE`, `NEEDS_REVIEW`) and links duplicates via `duplicate_of_id`. |
| `GET` | `/api/v1/admin/intelligence/reports/{report_id}/duplicate-history` | Duplicate review history | Verifier / Admin | Retrieves chronological duplicate moderation and linking audit trail for a report. |
| `GET` | `/api/v1/admin/intelligence/confidence-configurations` | List confidence configs | Verifier / Admin | Retrieves active versioned evidence confidence methodology and factor definitions. |
| `GET` | `/api/v1/admin/intelligence/reports/{report_id}/confidence` | Get report confidence | Verifier / Admin | Retrieves active evidence confidence assessment and multi-factor breakdown. |
| `POST` | `/api/v1/admin/intelligence/reports/{report_id}/calculate-confidence` | Calculate report confidence | Verifier / Admin | Evaluates multi-factor evidence reliability and records versioned assessment. |
| `GET` | `/api/v1/admin/intelligence/reports/{report_id}/confidence-history` | Report confidence history | Verifier / Admin | Retrieves complete chronological history of report confidence assessments. |
| `GET` | `/api/v1/admin/intelligence/areas/{area_id}/confidence` | Get area confidence | Verifier / Admin | Retrieves active area-level confidence score, completeness %, and category breakdown. |
| `POST` | `/api/v1/admin/intelligence/areas/{area_id}/calculate-confidence` | Calculate area confidence | Admin | Aggregates eligible canonical reports and calculates category-balanced confidence. |
| `GET` | `/api/v1/admin/intelligence/areas/{area_id}/confidence-history` | Area confidence history | Verifier / Admin | Retrieves complete chronological audit log of area confidence calculations. |

---

## Advanced Intelligence Engine Architecture (Phase 2, Step 8)

The Advanced Intelligence subsystems provide automated spatial duplicate candidate detection, auditable human-in-the-loop duplicate review and linking, individual report evidence confidence assessments, and aggregated area-level confidence and completeness metrics.

### Conceptual Separation of Intelligence Metrics

The platform enforces strict mathematical and conceptual boundaries:
- **Safety Deficiency Index (SDI):** An objective measurement of observed physical infrastructure deficiency gravity ($0.00$ to $100.00$). Higher indicates greater infrastructure deficiency.
- **Verified Severity:** The human-inspected gravity of a single physical deficiency on an integer scale ($1$ to $5$).
- **Evidence Confidence:** The objective measurement of supporting documentation reliability ($0.0000$ to $1.0000$). Measures whether the reported evidence is trustworthy and complete. Kept strictly separate from deficiency severity.
- **SDI Completeness:** The percentage of recognized infrastructure deficiency categories observed in an administrative jurisdiction ($0.00\%$ to $100.00\%$).
- **Confidence Completeness:** The percentage of eligible canonical reports in an area having usable evidence confidence assessments ($0.00\%$ to $100.00\%$).

### 1. Step 8A: Spatial Duplicate Candidate Detection
- **Geospatial Distance:** Utilizes PostGIS `ST_DWithin` and `ST_Distance` on geodesic `geography(Point, 4326)` to guarantee metric distance calculations (in metres).
- **Candidate Matching Rules:**
  1. Identical report category (`r1.category_id == r2.category_id`).
  2. Spatial proximity within configured radius (baseline: $50.00\text{ m}$).
  3. Temporal proximity within configured time window (baseline: $30\text{ days}$).
  4. Active lifecycle states only (`SUBMITTED`, `UNDER_VERIFICATION`, `VERIFIED`).
  5. Excludes self-matches and already linked duplicate reports (`duplicate_of_id IS NOT NULL`).
  6. Enforces canonical pair ordering (`first_report_id < second_report_id`) to ensure pair uniqueness and idempotent detection.

### 2. Step 8B: Duplicate Review and Canonical Linking
- **Moderation Workflow:** Authorized verifiers or administrators evaluate candidate pairs and record one of three outcomes:
  - `CONFIRMED_DUPLICATE`: Establishes a link where one report becomes a duplicate of the canonical report.
  - `NOT_DUPLICATE`: Verifies that the reports describe distinct physical infrastructure deficiencies.
  - `NEEDS_REVIEW`: Retains the candidate in moderation for field re-inspection.
- **Canonical Selection Policy (SDI Preservation):**
  1. Never select an `ARCHIVED` or `REJECTED` report as canonical.
  2. Prefer a currently `VERIFIED` eligible report whenever one exists. This prevents an earlier unverified `SUBMITTED` report from suppressing a later `VERIFIED` report from SDI calculation.
  3. If multiple `VERIFIED` reports exist, select the earliest submitted report.
  4. If no `VERIFIED` report exists, select the earliest eligible report.
  5. Deterministic tie-breaker: UUID string comparison.
  6. Reviewers may optionally specify an explicit canonical report ID, subject to the same eligibility and status rules.
- **Integrity Invariants:**
  - Canonical report cannot itself be a duplicate (`canonical.duplicate_of_id IS NULL`).
  - Circular relationships and self-links are strictly forbidden.
  - Re-points downstream duplicate references to the new canonical parent to prevent multi-hop chains.
  - All relationship updates and audit records in `duplicate_review_history` are committed within an atomic row-locked transaction (`SELECT ... FOR UPDATE`).
- **SDI Integration:** Confirmed duplicates (`duplicate_of_id IS NOT NULL`) are immediately excluded from all subsequent SDI calculations, while the verified canonical report remains counted.

### 3. Step 8C: Individual Report Evidence Confidence
- **Methodology Versioning:** Configured via `confidence_configurations` and `confidence_configuration_factors` (baseline: `v1.0.0`).
- **Factor Evaluation & Integrity Rules:**
  1. `VERIFICATION_COMPLETENESS` (weight: $0.3000$): Marked `UNAVAILABLE`. Free-form note character length is not an objectively defensible measure of verification thoroughness without structured rubrics or checklists. Excluded from the available-factor denominator.
  2. `EVIDENCE_FRESHNESS` (weight: $0.2500$, measurable): Evaluates observation timeliness latency between `observed_at` and `submitted_at`. `observed_at` is enforced to be $\le$ `submitted_at` upon submission. Shorter latency reflects higher temporal fidelity.
  3. `INDEPENDENT_CORROBORATION` (weight: $0.2500$, measurable): Evaluates independent corroboration strictly through confirmed linked duplicates (`duplicate_of_id`) submitted by distinct reporters (the report author's own submissions are strictly excluded). Automatically detected proximity candidates (`DuplicateCandidate`) are **never** counted as corroboration prior to human moderation.
  4. `EVIDENCE_AVAILABILITY` (weight: $0.1000$): Marked `UNAVAILABLE` because photographic evidence upload is deferred.
  5. `EVIDENCE_QUALITY` (weight: $0.1000$): Marked `UNAVAILABLE` because photographic evidence upload is deferred.
- **Dynamic Re-Normalization Formula:**
  $$\text{Evidence Confidence} = \frac{\sum_{f \in \text{observed}} (\text{score}_f \times \text{weight}_f)}{\sum_{f \in \text{observed}} \text{weight}_f}$$
  Missing or deferred factors are dynamically re-normalized over observed weights rather than penalized as zero. For baseline `v1.0.0`, with 2 measurable factors of weight $0.2500$ each, the available weight sum is $0.5000$, yielding normalized weights of $0.5000$ each (summing to $1.0000$).
- **Append-Only Preservation:** Prior confidence records are archived (`is_current=False`) without mutating `report_verifications` or `verified_severity`.

### 4. Step 8D: Area-Level Confidence and Completeness
- **Aggregation Eligibility:** Evaluates only active, canonical, verified reports (`administrative_area_id == area_id`, `status == 'VERIFIED'`, `duplicate_of_id IS NULL`).
- **Category-Balanced Confidence:**
  $$\text{Area Confidence Score} = \frac{\sum_{c \in \text{observed}} \text{Category Mean Confidence}_c}{|\text{Observed Categories}|}$$
  Prevents an area with many duplicates in a single category from skewing jurisdiction-wide confidence.
- **Sample Size Transparency:** Area confidence breakdowns include `category_code`, `category_name`, `report_count`, and `confident_report_count` for each category, enabling consumers to interpret statistical support and avoid equating single-report confidence with multi-report sample confidence.
- **Confidence Completeness:**
  $$\text{Confidence Completeness (\%)} = \left(\frac{\text{Eligible Reports with Usable Confidence}}{\text{Total Eligible Canonical Reports}}\right) \times 100.00$$
- **History Preservation:** Every area recalculation persists an immutable snapshot in `area_confidence_scores` and itemized category breakdown in `area_confidence_components`. SDI calculations remain completely untouched.

### 5. Step 9: Municipal Inspection Priority Engine
- **Conceptual Separation:**
  - *SDI:* Measures infrastructure physical deficiency severity (0.00–5.00).
  - *Evidence Confidence:* Measures the reliability/verifiability of observations (0.0000–1.0000).
  - *Inspection Priority:* Determines the operational ranking and urgency of areas requiring field municipal inspection (0.00–100.00).
- **Multi-Factor Weighted Formulation:**
  - `sdi_weight` ($0.3500$): Scaled deficiency severity ($(\text{SDI} / 5.0) \times 100.0$).
  - `urgency_weight` ($0.2500$): Latency of oldest uninspected defect observation relative to configured threshold (30 days).
  - `unresolved_reports_weight` ($0.2000$): Volume of distinct active unresolved reports capped at 20.
  - `confidence_gap_weight` ($0.2000$): Penalty for uncertainty ($(1.0 - \text{confidence}) \times 100.0$). High severity with low confidence increases inspection urgency.
- **Priority Tiers:**
  - `CRITICAL` ($\ge 80.00$)
  - `HIGH` ($\ge 60.00$)
  - `MEDIUM` ($\ge 40.00$)
  - `LOW` ($< 40.00$)
  - `INSUFFICIENT_DATA`: Explicitly designated for areas without observations or history, recommending baseline reconnaissance.
- **Append-Only Auditing:** Versioned via `priority_configurations` and historical snapshots in `area_priority_scores` with partial unique index `uq_area_priority_current`.

### 6. Step 10: Infrastructure Maintenance Management
- **Work Order Lifecycle:** Tracks verified defect repair workflows:
  $$\text{CREATED} \rightarrow \text{ASSIGNED} \rightarrow \text{ACCEPTED} \rightarrow \text{IN\_PROGRESS} \rightarrow \text{COMPLETED}$$
  Supports `BLOCKED` (with recorded justification) and `CANCELLED`.
- **Integrity Invariants:**
  - Maintenance tasks can **only** be created for reports in `VERIFIED` status.
  - Enforces a single active task per report (`uq_maintenance_active_report_task`) unless overridden by an administrator with a documented reason.
  - Completing repairs does not erase original citizen reports or verification histories.
  - Every state transition is written to an immutable audit ledger (`maintenance_task_events`) within a row-locked transaction (`SELECT ... FOR UPDATE`).

### 7. Step 11: Database-Backed Administrative Analytics
- **Aggregation Engine:** High-performance SQL queries computing operational metrics:
  - *Reports Analytics:* Volume by status, taxonomy category, jurisdiction, and timeline trends.
  - *SDI Analytics:* Jurisdiction breakdown across severity tiers (Negligible, Low, Moderate, High, Severe).
  - *Confidence Analytics:* Confidence averages, completeness distributions, and category sample sizes.
  - *Maintenance Analytics:* Turnaround durations, overdue work orders, and technician workloads.
  - *Overview & Trends:* Executive dashboards and temporal comparison graphs.

### 8. Step 12: In-App Notification Foundation
- **Database-Backed Alerts:** Generates transactional alerts for lifecycle events:
  - Citizen: `REPORT_SUBMITTED`, `REPORT_VERIFICATION_STARTED`, `REPORT_VERIFIED`, `REPORT_REJECTED`.
  - Maintenance Personnel: `MAINTENANCE_TASK_ASSIGNED`.
  - Administrator: `MAINTENANCE_TASK_STATUS_CHANGED`, `MAINTENANCE_TASK_COMPLETED`.
- **Privacy & Deduplication:** Strict ownership checks (users only view/mark their own alerts) and automatic unread alert deduplication.

---

## Running Tests

Execute the full test suite:

```bash
uv run pytest
```

Execute only the Inspection Priority Engine test suite (Step 9):

```bash
uv run pytest tests/test_priority.py
```

Execute only the Maintenance Management test suite (Step 10):

```bash
uv run pytest tests/test_maintenance.py
```

Execute only the Administrative Analytics test suite (Step 11):

```bash
uv run pytest tests/test_analytics.py
```

Execute only the Notification Foundation test suite (Step 12):

```bash
uv run pytest tests/test_notifications.py
```

Execute only the Security Hardening test suite (Step 13):

```bash
uv run pytest tests/test_security_hardening.py
```

Execute only the Intelligence Engine test suite:

```bash
uv run pytest tests/test_intelligence.py
```

Execute only the Spatial Duplicate Candidate Detection test suite (Step 8A):

```bash
uv run pytest tests/test_duplicates_detection.py
```

Execute only the Duplicate Review and Linking test suite (Step 8B):

```bash
uv run pytest tests/test_duplicates_review.py
```

Execute only the Individual Report Evidence Confidence test suite (Step 8C):

```bash
uv run pytest tests/test_report_confidence.py
```

Execute only the Area-Level Confidence and Completeness test suite (Step 8D):

```bash
uv run pytest tests/test_area_confidence.py
```

Execute only the Report Verification and Moderation test suite:

```bash
uv run pytest tests/test_verification.py
```

Execute only the Report Management test suite:

```bash
uv run pytest tests/test_reports.py
```

Execute only the IAM test suite:

```bash
uv run pytest tests/test_auth.py
```

Execute only the core database models and constraint test suite:

```bash
uv run pytest tests/test_database_models.py
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
