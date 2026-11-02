"""Comprehensive automated test suite for citizen report submission, listing, and detail APIs."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportStatusHistory


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper creating a user with a specific role and returning (user, jwt_token)."""
    user_email = email or f"{role_name}_{uuid.uuid4().hex[:8]}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Test {role_name.capitalize()} User",
        is_active=True,
    )
    db_session.add(user)
    db_session.flush()

    role = db_session.execute(select(Role).where(Role.name == role_name)).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()

    token = create_access_token(subject=user.id)
    return user, token


# -----------------------------------------------------------------------------
# 1. Citizen Report Submission Tests
# -----------------------------------------------------------------------------


def test_submit_valid_report_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify an authenticated citizen can submit a valid report and history is created."""
    citizen, token = _create_user_with_role(db_session, "citizen")

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Broken street light on Main St",
        "description": "The lamp post is completely dark, causing serious pedestrian risk.",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "address_text": "123 Main Street, City Center",
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED

    data = response.json()
    assert "id" in data
    assert data["reporter_id"] == str(citizen.id)
    assert data["title"] == payload["title"]
    assert data["description"] == payload["description"]
    assert data["latitude"] == pytest.approx(40.7128, abs=1e-4)
    assert data["longitude"] == pytest.approx(-74.0060, abs=1e-4)
    assert data["address_text"] == payload["address_text"]
    assert data["status"] == "SUBMITTED"
    assert data["category"]["code"] == "STREET_LIGHTING"
    assert data["category"]["name"] is not None

    # Verify atomic ReportStatusHistory record creation in database
    report_id = uuid.UUID(data["id"])
    history_rows = (
        db_session.execute(
            select(ReportStatusHistory).where(ReportStatusHistory.report_id == report_id)
        )
        .scalars()
        .all()
    )
    assert len(history_rows) == 1
    history = history_rows[0]
    assert history.from_status is None
    assert history.to_status == "SUBMITTED"
    assert history.changed_by_user_id == citizen.id
    assert history.reason == "Initial citizen report submission"


def test_submit_with_category_id_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify report submission accepts valid numeric category_id."""
    _, token = _create_user_with_role(db_session, "citizen")
    category = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "PEDESTRIAN_PATHWAYS")
    ).scalar_one()

    payload = {
        "category_id": category.id,
        "title": "Cracked sidewalk slab",
        "description": "Uneven concrete causing trip hazards near the bus stop.",
        "latitude": 37.7749,
        "longitude": -122.4194,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["category"]["id"] == category.id
    assert data["category"]["code"] == "PEDESTRIAN_PATHWAYS"


def test_submit_rejects_spoofed_reporter_id(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify client cannot supply a spoofed reporter_id in the request payload."""
    _, token = _create_user_with_role(db_session, "citizen")
    spoofed_id = str(uuid.uuid4())

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Attempted spoof report",
        "description": "Trying to submit under another user UUID.",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "reporter_id": spoofed_id,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_rejects_spoofed_status(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify client cannot elevate report status directly in request."""
    _, token = _create_user_with_role(db_session, "citizen")

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Attempted status elevation",
        "description": "Trying to bypass verification to VERIFIED.",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "status": "VERIFIED",
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_rejects_spoofed_admin_area_id(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify client cannot specify an administrative area ID directly."""
    _, token = _create_user_with_role(db_session, "citizen")

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Attempted admin area spoof",
        "description": "Trying to manually assign administrative area.",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "administrative_area_id": str(uuid.uuid4()),
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_rejects_invalid_category_id(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify nonexistent numeric category ID returns 404, and out of range returns 422."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Nonexistent ID within smallint range -> 404
    payload = {
        "category_id": 9999,
        "title": "Invalid category ID",
        "description": "Category ID does not exist in taxonomy.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

    # Out of smallint range (> 32767) -> 422
    payload_overflow = {
        "category_id": 99999,
        "title": "Overflow category ID",
        "description": "Exceeds smallint bounds.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }
    resp_overflow = auth_client.post(
        "/api/v1/reports",
        json=payload_overflow,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_overflow.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_rejects_invalid_category_code(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify nonexistent category code is rejected with HTTP 404."""
    _, token = _create_user_with_role(db_session, "citizen")

    payload = {
        "category_code": "NON_EXISTENT_CATEGORY",
        "title": "Invalid category code",
        "description": "Category code does not exist in taxonomy.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_submit_rejects_inactive_category(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify category with is_active=False cannot accept reports."""
    _, token = _create_user_with_role(db_session, "citizen")

    inactive_cat = ReportCategory(
        code=f"INACTIVE_{uuid.uuid4().hex[:6].upper()}",
        name="Deprecated Category",
        description="This category was decommissioned.",
        is_active=False,
    )
    db_session.add(inactive_cat)
    db_session.commit()

    payload = {
        "category_code": inactive_cat.code,
        "title": "Submission to inactive category",
        "description": "Should be rejected because category is inactive.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "inactive" in response.json()["detail"].lower()


def test_submit_rejects_out_of_bounds_coordinates(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify coordinates outside WGS 84 bounds [-90, 90] x [-180, 180] are rejected."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Latitude > 90
    resp1 = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "Invalid lat high",
            "description": "Latitude above 90.",
            "latitude": 91.5,
            "longitude": 0.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Latitude < -90
    resp2 = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "Invalid lat low",
            "description": "Latitude below -90.",
            "latitude": -91.5,
            "longitude": 0.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Longitude > 180
    resp3 = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "Invalid lon high",
            "description": "Longitude above 180.",
            "latitude": 0.0,
            "longitude": 181.5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Longitude < -180
    resp4 = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "Invalid lon low",
            "description": "Longitude below -180.",
            "latitude": 0.0,
            "longitude": -181.5,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp4.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_rejects_missing_required_fields(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify omission of title, description, or category identifier raises HTTP 422."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Missing category
    resp1 = auth_client.post(
        "/api/v1/reports",
        json={
            "title": "Missing category",
            "description": "No category provided at all.",
            "latitude": 40.0,
            "longitude": -74.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Missing title
    resp2 = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "description": "No title provided.",
            "latitude": 40.0,
            "longitude": -74.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Title too short (< 3 chars)
    resp3 = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "No",
            "description": "Description text.",
            "latitude": 40.0,
            "longitude": -74.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_submit_rejects_unauthenticated(auth_client: TestClient) -> None:
    """Verify unauthenticated submission is rejected with HTTP 401."""
    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Unauthenticated report",
        "description": "Should fail because no token provided.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }
    response = auth_client.post("/api/v1/reports", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_submit_rejects_non_citizen(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify non-citizen user (e.g. verifier only) receives HTTP 403 Forbidden."""
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Report by verifier",
        "description": "Verifier without citizen role cannot submit reports.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_submit_rejects_future_observed_at(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify report submission with future observed_at timestamp is rejected with 422."""
    from datetime import UTC, datetime, timedelta

    _, token = _create_user_with_role(db_session, "citizen")
    future_time = (datetime.now(UTC) + timedelta(days=2)).isoformat()

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": "Future defect",
        "description": "Report with observation date in the future.",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "observed_at": future_time,
    }

    response = auth_client.post(
        "/api/v1/reports",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


# -----------------------------------------------------------------------------
# 2. PostGIS Geometry & Spatial Resolution Tests
# -----------------------------------------------------------------------------


def test_postgis_geometry_storage_and_srid(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify location is stored with SRID 4326, X as longitude, and Y as latitude."""
    _, token = _create_user_with_role(db_session, "citizen")

    test_lon = -73.9857
    test_lat = 40.7484

    resp = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "VISIBILITY",
            "title": "Overgrown tree obscuring sightline",
            "description": "Vegetation blocks view of oncoming traffic.",
            "latitude": test_lat,
            "longitude": test_lon,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    report_id = uuid.UUID(resp.json()["id"])

    # Query PostGIS directly via SQL catalog functions
    row = db_session.execute(
        text(
            "SELECT ST_SRID(location), GeometryType(location), ST_X(location), ST_Y(location) "
            "FROM reports WHERE id = :id"
        ),
        {"id": report_id},
    ).one()

    srid, geom_type, x_coord, y_coord = row
    assert srid == 4326
    assert geom_type == "POINT"
    assert x_coord == pytest.approx(test_lon, abs=1e-5)
    assert y_coord == pytest.approx(test_lat, abs=1e-5)


def test_postgis_administrative_area_assignment_via_st_covers(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify ST_Covers assigns administrative area when point lies within boundary."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Create a test Ward covering longitude [10.0, 20.0] and latitude [10.0, 20.0]
    ward_code = f"WARD_{uuid.uuid4().hex[:6]}"
    ward = AdministrativeArea(
        name="Central Commercial Ward",
        code=ward_code,
        area_type="ward",
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 20.0, 20.0 20.0, 20.0 10.0, 10.0 10.0)))"
        ),
        properties={"zone": "commercial"},
    )
    db_session.add(ward)
    db_session.commit()

    # Submit report inside the ward: (15.0, 15.0)
    resp = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "MAINTENANCE",
            "title": "Broken bench in public square",
            "description": "Public bench has broken slats.",
            "latitude": 15.0,
            "longitude": 15.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_201_CREATED

    data = resp.json()
    assert data["administrative_area"] is not None
    assert data["administrative_area"]["id"] == str(ward.id)
    assert data["administrative_area"]["code"] == ward_code
    assert data["administrative_area"]["area_type"] == "ward"


def test_postgis_unmatched_coordinates_remain_unassigned(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify reports outside all administrative boundaries remain unassigned (NULL)."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Coordinate far away from any administrative boundary fixture
    resp = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "PUBLIC_ASSISTANCE",
            "title": "Missing call box on rural road",
            "description": "No emergency infrastructure present.",
            "latitude": 55.0,
            "longitude": -150.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_201_CREATED

    data = resp.json()
    assert data["administrative_area"] is None

    # Verify NULL in database
    report_id = uuid.UUID(data["id"])
    db_report = db_session.execute(select(Report).where(Report.id == report_id)).scalar_one()
    assert db_report.administrative_area_id is None


def test_postgis_hierarchical_granularity_prioritizes_ward_over_district(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify overlapping boundaries assign the most granular area (ward before district)."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Create larger District covering [0.0, 30.0] x [0.0, 30.0]
    district_code = f"DIST_{uuid.uuid4().hex[:6]}"
    district = AdministrativeArea(
        name="Greater Northern District",
        code=district_code,
        area_type="district",
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((0.0 0.0, 0.0 30.0, 30.0 30.0, 30.0 0.0, 0.0 0.0)))"
        ),
        properties={},
    )
    db_session.add(district)
    db_session.flush()

    # Create inner Ward covering [10.0, 20.0] x [10.0, 20.0]
    ward_code = f"WARD_{uuid.uuid4().hex[:6]}"
    ward = AdministrativeArea(
        name="Inner Urban Ward",
        code=ward_code,
        area_type="ward",
        parent_id=district.id,
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 20.0, 20.0 20.0, 20.0 10.0, 10.0 10.0)))"
        ),
        properties={},
    )
    db_session.add(ward)
    db_session.commit()

    # Submit at (15.0, 15.0) which is covered by BOTH district and ward
    resp = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "Light issue in overlapping zone",
            "description": "Checking hierarchy resolution.",
            "latitude": 15.0,
            "longitude": 15.0,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == status.HTTP_201_CREATED

    data = resp.json()
    assert data["administrative_area"] is not None
    # Must resolve to the Ward (more granular) rather than District
    assert data["administrative_area"]["id"] == str(ward.id)
    assert data["administrative_area"]["area_type"] == "ward"


# -----------------------------------------------------------------------------
# 3. Citizen Report Listing Tests
# -----------------------------------------------------------------------------


def test_list_reports_citizen_sees_only_own_reports(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify a citizen only sees their own reports and never another user's reports."""
    citizen_a, token_a = _create_user_with_role(db_session, "citizen")
    citizen_b, token_b = _create_user_with_role(db_session, "citizen")

    # Citizen A submits 2 reports
    for i in range(2):
        auth_client.post(
            "/api/v1/reports",
            json={
                "category_code": "STREET_LIGHTING",
                "title": f"Citizen A report {i}",
                "description": "Report by citizen A.",
                "latitude": 40.0,
                "longitude": -74.0,
            },
            headers={"Authorization": f"Bearer {token_a}"},
        )

    # Citizen B submits 1 report
    auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "VISIBILITY",
            "title": "Citizen B report",
            "description": "Report by citizen B.",
            "latitude": 38.0,
            "longitude": -77.0,
        },
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # Citizen A list
    resp_a = auth_client.get(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert resp_a.status_code == status.HTTP_200_OK
    data_a = resp_a.json()
    assert data_a["total"] == 2
    assert len(data_a["items"]) == 2
    for item in data_a["items"]:
        assert item["reporter_id"] == str(citizen_a.id)

    # Citizen B list
    resp_b = auth_client.get(
        "/api/v1/reports",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == status.HTTP_200_OK
    data_b = resp_b.json()
    assert data_b["total"] == 1
    assert len(data_b["items"]) == 1
    assert data_b["items"][0]["reporter_id"] == str(citizen_b.id)


def test_list_reports_pagination(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify limit and offset pagination works accurately and deterministically."""
    _, token = _create_user_with_role(db_session, "citizen")

    # Create 5 reports
    created_ids = []
    for i in range(5):
        resp = auth_client.post(
            "/api/v1/reports",
            json={
                "category_code": "PEDESTRIAN_PATHWAYS",
                "title": f"Pothole report {i}",
                "description": f"Detailed description for pothole {i}.",
                "latitude": 40.0 + (i * 0.01),
                "longitude": -74.0 - (i * 0.01),
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        created_ids.append(resp.json()["id"])

    # Page 1: limit=2, offset=0
    resp_p1 = auth_client.get(
        "/api/v1/reports?limit=2&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p1.status_code == status.HTTP_200_OK
    data_p1 = resp_p1.json()
    assert data_p1["total"] == 5
    assert len(data_p1["items"]) == 2
    assert data_p1["limit"] == 2
    assert data_p1["offset"] == 0

    # Page 2: limit=2, offset=2
    resp_p2 = auth_client.get(
        "/api/v1/reports?limit=2&offset=2",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p2.status_code == status.HTTP_200_OK
    data_p2 = resp_p2.json()
    assert data_p2["total"] == 5
    assert len(data_p2["items"]) == 2
    assert data_p2["offset"] == 2

    # Page 3: limit=2, offset=4
    resp_p3 = auth_client.get(
        "/api/v1/reports?limit=2&offset=4",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp_p3.status_code == status.HTTP_200_OK
    data_p3 = resp_p3.json()
    assert data_p3["total"] == 5
    assert len(data_p3["items"]) == 1

    # Ensure no overlap across pages
    ids_p1 = [item["id"] for item in data_p1["items"]]
    ids_p2 = [item["id"] for item in data_p2["items"]]
    ids_p3 = [item["id"] for item in data_p3["items"]]
    assert set(ids_p1).isdisjoint(set(ids_p2))
    assert set(ids_p2).isdisjoint(set(ids_p3))


def test_list_reports_invalid_pagination_bounds(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify out-of-bounds pagination parameters are rejected with HTTP 422."""
    _, token = _create_user_with_role(db_session, "citizen")

    # limit < 1
    resp1 = auth_client.get(
        "/api/v1/reports?limit=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # limit > 100
    resp2 = auth_client.get(
        "/api/v1/reports?limit=101",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # offset < 0
    resp3 = auth_client.get(
        "/api/v1/reports?offset=-1",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_list_reports_unauthenticated_rejected(auth_client: TestClient) -> None:
    """Verify unauthenticated listing request receives HTTP 401."""
    response = auth_client.get("/api/v1/reports")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# -----------------------------------------------------------------------------
# 4. Citizen Report Detail Tests
# -----------------------------------------------------------------------------


def test_get_report_detail_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify a citizen can retrieve sanitized details of their own report."""
    citizen, token = _create_user_with_role(db_session, "citizen")

    create_resp = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "VISIBILITY",
            "title": "Park path obstructed by debris",
            "description": "Fallen branch blocks public walkway.",
            "latitude": 41.8781,
            "longitude": -87.6298,
            "address_text": "Millennium Park Walkway",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_resp.status_code == status.HTTP_201_CREATED
    report_id = create_resp.json()["id"]

    detail_resp = auth_client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_resp.status_code == status.HTTP_200_OK

    detail = detail_resp.json()
    assert detail["id"] == report_id
    assert detail["reporter_id"] == str(citizen.id)
    assert detail["title"] == "Park path obstructed by debris"
    assert detail["latitude"] == pytest.approx(41.8781, abs=1e-4)
    assert detail["longitude"] == pytest.approx(-87.6298, abs=1e-4)
    assert detail["status"] == "SUBMITTED"
    assert "submitted_at" in detail
    assert "updated_at" in detail


def test_get_report_detail_nonexistent_returns_404(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify random nonexistent UUID returns HTTP 404."""
    _, token = _create_user_with_role(db_session, "citizen")
    random_id = uuid.uuid4()

    response = auth_client.get(
        f"/api/v1/reports/{random_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Report not found."


def test_get_report_detail_other_citizen_report_returns_404(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify accessing another citizen's report returns 404 (prevents disclosure)."""
    _, token_a = _create_user_with_role(db_session, "citizen")
    _, token_b = _create_user_with_role(db_session, "citizen")

    # Citizen A creates a report
    resp_a = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": "Private observation",
            "description": "Should not be readable by citizen B.",
            "latitude": 40.0,
            "longitude": -74.0,
        },
        headers={"Authorization": f"Bearer {token_a}"},
    )
    report_id = resp_a.json()["id"]

    # Citizen B tries to access Citizen A's report
    resp_b = auth_client.get(
        f"/api/v1/reports/{report_id}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp_b.status_code == status.HTTP_404_NOT_FOUND
    assert resp_b.json()["detail"] == "Report not found."


def test_get_report_detail_invalid_uuid_returns_422(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify malformed report UUID in URL path is rejected with HTTP 422."""
    _, token = _create_user_with_role(db_session, "citizen")

    response = auth_client.get(
        "/api/v1/reports/not-a-valid-uuid",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_get_report_detail_unauthenticated_rejected(auth_client: TestClient) -> None:
    """Verify unauthenticated detail request receives HTTP 401."""
    random_id = uuid.uuid4()
    response = auth_client.get(f"/api/v1/reports/{random_id}")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# -----------------------------------------------------------------------------
# 5. Transactional Integrity & Rollback Test
# -----------------------------------------------------------------------------


def test_status_history_failure_rolls_back_report_creation(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify failure to insert ReportStatusHistory rolls back Report creation atomically."""
    citizen, token = _create_user_with_role(db_session, "citizen")
    unique_title = f"Transactional Rollback Test {uuid.uuid4().hex[:8]}"

    payload = {
        "category_code": "STREET_LIGHTING",
        "title": unique_title,
        "description": "This report should be completely rolled back on error.",
        "latitude": 40.7128,
        "longitude": -74.0060,
    }

    original_add = db_session.add

    def failing_add(instance: object) -> None:
        if isinstance(instance, ReportStatusHistory):
            raise SQLAlchemyError("Simulated ReportStatusHistory insertion database failure")
        original_add(instance)

    with (
        patch.object(db_session, "add", side_effect=failing_add),
        pytest.raises(SQLAlchemyError, match="Simulated ReportStatusHistory"),
    ):
        auth_client.post(
            "/api/v1/reports",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    # Verify that the report was NOT committed to the database
    db_report = db_session.execute(
        select(Report).where(Report.title == unique_title)
    ).scalar_one_or_none()
    assert db_report is None
