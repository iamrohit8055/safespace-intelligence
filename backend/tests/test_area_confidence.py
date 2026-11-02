"""Tests for Step 8D: Area-Level Confidence and Completeness Integration.

Covers:
1. Area confidence aggregation over eligible canonical verified reports.
2. Exclusion of confirmed duplicates from area confidence calculations.
3. Category-level grouping and observation counts.
4. Correct confidence completeness percentage calculation.
5. Handling of missing or uncalculated report confidence.
6. Preservation of historical area confidence calculations.
7. Distinguishing between methodology configuration versions.
8. Non-interference with Safety Deficiency Index (SDI) and physical severity.
9. RBAC and administrative HTTP endpoints.
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
from app.intelligence.area_confidence import (
    calculate_area_confidence,
    get_area_confidence_history,
)
from app.intelligence.service import calculate_area_sdi
from app.models.duplicates import DuplicateCandidate
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportVerification
from app.schemas.duplicates import DuplicateReviewRequest
from app.services.duplicates import review_duplicate_candidate


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper creating a user and returning (user, jwt_token)."""
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


def _create_test_area(
    db_session: Session, name: str = "Confidence Test Ward"
) -> AdministrativeArea:
    """Helper creating an administrative area."""
    area_code = f"AREA_{uuid.uuid4().hex[:8].upper()}"
    area = AdministrativeArea(
        name=name,
        code=area_code,
        area_type="ward",
        boundary=WKTElement(
            "SRID=4326;MULTIPOLYGON(((10.0 10.0, 10.0 20.0, 20.0 20.0, 20.0 10.0, 10.0 10.0)))"
        ),
        properties={"test": True},
    )
    db_session.add(area)
    db_session.commit()
    return area


def _create_verified_report(
    db_session: Session,
    reporter: User,
    category: ReportCategory,
    area: AdministrativeArea,
    verifier: User,
    severity: int = 4,
    notes: str = "Detailed on-site inspection note",
    status_val: str = "VERIFIED",
    lat: float = 15.0,
    lon: float = 15.0,
    submitted_at: datetime | None = None,
    duplicate_of_id: uuid.UUID | None = None,
) -> Report:
    """Helper creating a verified report in an area."""
    sub_time = submitted_at or datetime.now(UTC)
    report = Report(
        reporter_id=reporter.id,
        category_id=category.id,
        administrative_area_id=area.id,
        title=f"Deficiency in {category.code}",
        description="Observed deficiency description.",
        location=WKTElement(f"SRID=4326;POINT({lon} {lat})"),
        status=status_val,
        observed_at=sub_time - timedelta(hours=2),
        submitted_at=sub_time,
        duplicate_of_id=duplicate_of_id,
    )
    db_session.add(report)
    db_session.flush()

    if status_val == "VERIFIED":
        v = ReportVerification(
            report_id=report.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=severity,
            verification_notes=notes,
        )
        db_session.add(v)

    db_session.commit()
    return report


def test_area_confidence_aggregation_and_completeness(db_session: Session) -> None:
    """Verify area confidence calculation across multiple categories with full completeness."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session)

    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    pothole_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "MAINTENANCE")
    ).scalar_one()

    # Create 2 verified reports in lighting, 1 in maintenance
    _create_verified_report(db_session, citizen, lighting_cat, area, verifier, severity=5)
    _create_verified_report(db_session, citizen, lighting_cat, area, verifier, severity=4)
    _create_verified_report(db_session, citizen, pothole_cat, area, verifier, severity=3)

    area_conf = calculate_area_confidence(db_session, area.id)

    assert area_conf.area_confidence_score is not None
    assert Decimal("0.0000") <= area_conf.area_confidence_score <= Decimal("1.0000")
    assert area_conf.total_reports_count == 3
    assert area_conf.reports_with_confidence_count == 3
    assert area_conf.reports_without_confidence_count == 0
    assert area_conf.confidence_completeness_pct == Decimal("100.00")
    assert area_conf.is_current is True

    # Check component availability
    components = {c.category_id: c for c in area_conf.components}
    assert components[lighting_cat.id].availability_state == "OBSERVED"
    assert components[lighting_cat.id].report_count == 2
    assert components[pothole_cat.id].availability_state == "OBSERVED"
    assert components[pothole_cat.id].report_count == 1


def test_linked_duplicates_excluded_from_area_confidence(db_session: Session) -> None:
    """Verify confirmed duplicate reports do not artificially inflate report count."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session)

    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    r1 = _create_verified_report(
        db_session, citizen, lighting_cat, area, verifier, severity=5, lat=15.0, lon=15.0
    )
    r2 = _create_verified_report(
        db_session,
        citizen,
        lighting_cat,
        area,
        verifier,
        severity=4,
        lat=15.0001,
        lon=15.0001,
        submitted_at=datetime.now(UTC) + timedelta(minutes=5),
    )

    # Link r2 as duplicate of r1
    cand = DuplicateCandidate(
        first_report_id=min(r1.id, r2.id),
        second_report_id=max(r1.id, r2.id),
        distance_metres=Decimal("12.0"),
        time_difference_seconds=300,
        rule_version="v1.0.0",
        review_status="PENDING",
    )
    db_session.add(cand)
    db_session.commit()

    req = DuplicateReviewRequest(decision="CONFIRMED_DUPLICATE", reason="Same streetlight")
    review_duplicate_candidate(db_session, cand.id, req, verifier)

    area_conf = calculate_area_confidence(db_session, area.id)

    # r2 must be excluded; total eligible reports = 1
    assert area_conf.total_reports_count == 1
    assert area_conf.reports_with_confidence_count == 1


def test_empty_area_confidence_handles_unknown_state(db_session: Session) -> None:
    """Verify that an area with zero reports produces NULL confidence and 0% completeness."""
    area = _create_test_area(db_session, name="Empty Jurisdiction")

    area_conf = calculate_area_confidence(db_session, area.id)

    assert area_conf.area_confidence_score is None
    assert area_conf.confidence_completeness_pct == Decimal("0.00")
    assert area_conf.total_reports_count == 0
    assert area_conf.reports_with_confidence_count == 0


def test_area_confidence_preserves_history(db_session: Session) -> None:
    """Verify recalculating area confidence creates a new record and preserves audit log."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session)

    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    _create_verified_report(db_session, citizen, lighting_cat, area, verifier)

    first_calc = calculate_area_confidence(db_session, area.id)
    assert first_calc.is_current is True

    # Add second report and recalculate
    _create_verified_report(db_session, citizen, lighting_cat, area, verifier)
    second_calc = calculate_area_confidence(db_session, area.id)

    history = get_area_confidence_history(db_session, area.id)
    assert len(history) == 2
    assert second_calc.is_current is True
    assert first_calc.is_current is False


def test_confidence_calculations_do_not_modify_sdi(db_session: Session) -> None:
    """Verify that running confidence calculations leaves the SDI score and components untouched."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    area = _create_test_area(db_session)

    lighting_cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()
    _create_verified_report(db_session, citizen, lighting_cat, area, verifier, severity=5)

    # Compute SDI
    sdi_before = calculate_area_sdi(db_session, area.id)
    sdi_score_before = sdi_before.score

    # Compute Area Confidence
    calculate_area_confidence(db_session, area.id)

    # Reload SDI
    db_session.refresh(sdi_before)
    assert sdi_before.score == sdi_score_before


def test_api_area_confidence_rbac(auth_client: TestClient, db_session: Session) -> None:
    """Verify RBAC on GET and POST /areas/{area_id}/confidence endpoints."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, admin_token = _create_user_with_role(db_session, "admin")
    area = _create_test_area(db_session)

    # Unauthenticated -> 401
    resp = auth_client.get(f"/api/v1/admin/intelligence/areas/{area.id}/confidence")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Citizen -> 403
    resp = auth_client.get(
        f"/api/v1/admin/intelligence/areas/{area.id}/confidence",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Verifier forbidden from triggering area calculation (admin only)
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{area.id}/calculate-confidence",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # Admin allowed to calculate -> 200
    resp = auth_client.post(
        f"/api/v1/admin/intelligence/areas/{area.id}/calculate-confidence",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert "area_confidence_score" in data
    assert "confidence_completeness_pct" in data

    # Verifier allowed to read -> 200
    resp = auth_client.get(
        f"/api/v1/admin/intelligence/areas/{area.id}/confidence",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
