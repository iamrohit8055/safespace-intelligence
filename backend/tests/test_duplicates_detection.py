"""Tests for Step 8A: Spatial Duplicate Candidate Detection.

Covers:
1. Spatial candidate detection with PostGIS metric geography.
2. Same-category nearby reports matching.
3. Category-aware exclusion (different categories do not match).
4. Spatial radius exclusion (> 50m excluded).
5. Time window exclusion (> 30 days excluded).
6. Already-linked duplicate exclusion (duplicate_of_id IS NOT NULL).
7. Self-match prevention.
8. Candidate pair ordering and idempotence.
9. Spatial indexes availability.
10. Reusable detection service and batch detection.
11. RBAC and protected endpoints.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from geoalchemy2.elements import WKTElement
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.database.base import Base
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.services.duplicates import (
    detect_candidates_for_report,
)


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper to create a user and return (user, jwt_token)."""
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


def _create_report(
    db_session: Session,
    reporter: User,
    category: ReportCategory,
    lat: float = 40.7484,
    lon: float = -73.9857,
    status_val: str = "SUBMITTED",
    submitted_at: datetime | None = None,
    duplicate_of_id: uuid.UUID | None = None,
) -> Report:
    """Helper creating a report with explicit coordinates, category, and timestamp."""
    sub_time = submitted_at or datetime.now(UTC)
    report = Report(
        reporter_id=reporter.id,
        category_id=category.id,
        title=f"Report in {category.code}",
        description="Physical deficiency report observation.",
        location=WKTElement(f"SRID=4326;POINT({lon} {lat})"),
        status=status_val,
        observed_at=sub_time - timedelta(hours=1),
        submitted_at=sub_time,
        duplicate_of_id=duplicate_of_id,
    )
    db_session.add(report)
    db_session.commit()
    return report


def test_same_category_nearby_reports_generate_candidate(db_session: Session) -> None:
    """Verify reports within 50m and 30 days of same category are detected as candidates."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    # Base report at Empire State Building
    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    # Nearby report ~15 meters away
    r2 = _create_report(db_session, citizen, lighting_cat, lat=40.74850, lon=-73.9856)

    candidates = detect_candidates_for_report(db_session, r1.id)
    assert len(candidates) >= 1

    cand = candidates[0]
    expected_first, expected_second = (r1.id, r2.id) if r1.id < r2.id else (r2.id, r1.id)
    assert cand.first_report_id == expected_first
    assert cand.second_report_id == expected_second
    assert cand.distance_metres > Decimal("0.0")
    assert cand.distance_metres < Decimal("50.0")
    assert cand.review_status == "PENDING"
    assert cand.rule_version == "v1.0.0"


def test_different_category_reports_do_not_match(db_session: Session) -> None:
    """Verify that nearby reports of different categories do NOT match."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    pothole_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "MAINTENANCE")
    ).scalar_one()

    # Exact same coordinates but different categories
    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    r2 = _create_report(db_session, citizen, pothole_cat, lat=40.74844, lon=-73.9857)

    candidates = detect_candidates_for_report(db_session, r1.id)
    matched_ids = {c.first_report_id for c in candidates} | {c.second_report_id for c in candidates}
    assert r2.id not in matched_ids


def test_reports_outside_spatial_radius_excluded(db_session: Session) -> None:
    """Verify that reports beyond the spatial radius (50m) are excluded."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    # Report ~200 meters away (lat offset by 0.002 ~ 222m)
    r2 = _create_report(db_session, citizen, lighting_cat, lat=40.75044, lon=-73.9857)

    candidates = detect_candidates_for_report(db_session, r1.id)
    matched_ids = {c.first_report_id for c in candidates} | {c.second_report_id for c in candidates}
    assert r2.id not in matched_ids


def test_reports_outside_time_window_excluded(db_session: Session) -> None:
    """Verify that reports outside the configurable time window (30 days) are excluded."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    now = datetime.now(UTC)
    r1 = _create_report(
        db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857, submitted_at=now
    )
    # Report 40 days older
    r2 = _create_report(
        db_session,
        citizen,
        lighting_cat,
        lat=40.74845,
        lon=-73.9857,
        submitted_at=now - timedelta(days=40),
    )

    candidates = detect_candidates_for_report(db_session, r1.id)
    matched_ids = {c.first_report_id for c in candidates} | {c.second_report_id for c in candidates}
    assert r2.id not in matched_ids


def test_already_linked_duplicates_excluded(db_session: Session) -> None:
    """Verify reports with duplicate_of_id set are excluded from candidate detection."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r_parent = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    # r_child already linked to r_parent
    r_child = _create_report(
        db_session,
        citizen,
        lighting_cat,
        lat=40.74846,
        lon=-73.9857,
        duplicate_of_id=r_parent.id,
    )
    # New report nearby
    r_new = _create_report(db_session, citizen, lighting_cat, lat=40.74845, lon=-73.9857)

    candidates = detect_candidates_for_report(db_session, r_new.id)
    matched_ids = {c.first_report_id for c in candidates} | {c.second_report_id for c in candidates}
    # r_child must NOT be matched because duplicate_of_id is not null
    assert r_child.id not in matched_ids
    # r_parent CAN match r_new
    assert r_parent.id in matched_ids


def test_self_matches_are_prevented(db_session: Session) -> None:
    """Verify that a report cannot match itself as a candidate."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    candidates = detect_candidates_for_report(db_session, r1.id)
    for c in candidates:
        assert c.first_report_id != c.second_report_id


def test_candidate_pair_insertion_is_idempotent(db_session: Session) -> None:
    """Verify that executing candidate detection multiple times does not insert duplicate pairs."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    r2 = _create_report(db_session, citizen, lighting_cat, lat=40.74846, lon=-73.9857)

    first_run = detect_candidates_for_report(db_session, r1.id)
    second_run = detect_candidates_for_report(db_session, r1.id)
    reverse_run = detect_candidates_for_report(db_session, r2.id)

    assert len(first_run) == 1
    assert len(second_run) == 1
    assert len(reverse_run) == 1
    assert first_run[0].id == second_run[0].id == reverse_run[0].id


def test_spatial_indexes_available() -> None:
    """Verify that spatial GiST indexes on reports are present in model metadata."""
    reports_table = Base.metadata.tables["reports"]
    index_names = {idx.name for idx in reports_table.indexes}
    assert "idx_reports_location_gist" in index_names
    assert "idx_reports_location_geog_gist" in index_names


def test_api_list_candidates_rbac(auth_client: TestClient, db_session: Session) -> None:
    """Verify RBAC permissions on GET /duplicate-candidates."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, admin_token = _create_user_with_role(db_session, "admin")

    # Unauthenticated -> 401
    resp = auth_client.get("/api/v1/admin/intelligence/duplicate-candidates")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Citizen -> 403
    resp = auth_client.get(
        "/api/v1/admin/intelligence/duplicate-candidates",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Verifier -> 200
    resp = auth_client.get(
        "/api/v1/admin/intelligence/duplicate-candidates",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK

    # Admin -> 200
    resp = auth_client.get(
        "/api/v1/admin/intelligence/duplicate-candidates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK


def test_api_trigger_batch_detection_admin_only(
    auth_client: TestClient, db_session: Session
) -> None:
    """Verify that only admin can trigger batch duplicate detection."""
    citizen, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, admin_token = _create_user_with_role(db_session, "admin")

    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    _create_report(db_session, citizen, lighting_cat, lat=40.74844, lon=-73.9857)
    _create_report(db_session, citizen, lighting_cat, lat=40.74848, lon=-73.9857)

    payload = {"configuration_version": "v1.0.0"}

    # Verifier forbidden from triggering batch
    resp = auth_client.post(
        "/api/v1/admin/intelligence/duplicate-candidates/detect",
        json=payload,
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin allowed
    resp = auth_client.post(
        "/api/v1/admin/intelligence/duplicate-candidates/detect",
        json=payload,
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "candidates_evaluated" in data
    assert "new_candidates_created" in data
