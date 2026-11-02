"""Comprehensive unit and integration tests for Municipal Inspection Priority Engine."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.intelligence.priority import (
    calculate_area_inspection_priority,
    get_active_priority_config,
    get_area_priority_history,
)
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.intelligence import AreaScore, ScoringConfiguration
from app.models.priority import AreaPriorityScore
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportVerification


def _create_user_with_role(
    db: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper to create a user with a specific role and return access token."""
    user_email = email or f"priority_{role_name}_{datetime.now(UTC).timestamp()}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Priority {role_name.capitalize()}",
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.flush()

    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one()
    user_role = UserRole(user_id=user.id, role_id=role.id)
    db.add(user_role)
    db.commit()
    db.refresh(user)

    token = create_access_token(subject=user.id)
    return user, token


def _create_area(db: Session, name: str, code: str) -> AdministrativeArea:
    """Helper to create an administrative area for testing."""
    area = AdministrativeArea(
        name=name,
        code=code,
        area_type="ward",
        boundary="SRID=4326;MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
    )
    db.add(area)
    db.commit()
    db.refresh(area)
    return area


def _create_report(
    db: Session,
    area_id,
    reporter: User,
    category: ReportCategory,
    status_val: str = "VERIFIED",
    observed_at: datetime | None = None,
) -> Report:
    """Helper to create a report in an administrative area."""
    now = datetime.now(UTC)
    report = Report(
        reporter_id=reporter.id,
        category_id=category.id,
        administrative_area_id=area_id,
        title="Test Defect for Priority",
        description="Detailed description for testing inspection priority.",
        location="SRID=4326;POINT(0.5 0.5)",
        status=status_val,
        observed_at=observed_at or (now - timedelta(days=5)),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def test_get_active_priority_config(db_session: Session) -> None:
    """Verify default active inspection priority configuration v1.0.0 exists."""
    config = get_active_priority_config(db_session)
    assert config.version == "v1.0.0"
    assert config.sdi_weight == Decimal("0.3500")
    assert config.urgency_weight == Decimal("0.2500")
    assert config.unresolved_reports_weight == Decimal("0.2000")
    assert config.confidence_gap_weight == Decimal("0.2000")


def test_insufficient_data_for_uninspected_empty_area(db_session: Session) -> None:
    """Verify an empty jurisdiction with no reports and no prior SDI yields INSUFFICIENT_DATA."""
    area = _create_area(db_session, "Empty Jurisdiction", "EMPTY_WARD_01")
    score = calculate_area_inspection_priority(db_session, area.id)

    assert score.priority_level == "INSUFFICIENT_DATA"
    assert score.priority_score is None
    assert score.never_inspected is True
    assert score.unresolved_reports_count == 0
    assert score.calculation_metadata["recommendation"] == "BASELINE_INSPECTION"


def test_priority_calculation_with_sdi_and_unresolved_reports(db_session: Session) -> None:
    """Verify priority score combines SDI severity, observation staleness, and volume."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    area = _create_area(db_session, "High Severity Ward", "SEV_WARD_01")

    # Seed an AreaScore (SDI = 4.00 / 5.00)
    scoring_config = db_session.execute(select(ScoringConfiguration)).scalars().first()
    area_sdi = AreaScore(
        administrative_area_id=area.id,
        configuration_id=scoring_config.id,
        score=Decimal("4.00"),
        completeness_pct=Decimal("80.00"),
        participating_categories_count=4,
        total_categories_count=5,
        eligible_reports_count=5,
        is_current=True,
    )
    db_session.add(area_sdi)

    # Create 3 verified reports with observations from 15 days ago
    obs_time = datetime.now(UTC) - timedelta(days=15)
    for _ in range(3):
        r = _create_report(db_session, area.id, citizen, cat, "VERIFIED", observed_at=obs_time)
        v = ReportVerification(
            report_id=r.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=4,
        )
        db_session.add(v)
    db_session.commit()

    score = calculate_area_inspection_priority(db_session, area.id)

    assert score.priority_score is not None
    assert score.priority_score > Decimal("50.00")
    assert score.priority_level in ("MEDIUM", "HIGH", "CRITICAL")
    assert score.unresolved_reports_count == 3
    assert score.never_inspected is False


def test_low_confidence_with_high_sdi_prioritizes_inspection(db_session: Session) -> None:
    """Verify that low evidence confidence for high SDI yields high verification gap urgency."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    area = _create_area(db_session, "Uncertain Defect Ward", "UNCERT_WARD_01")

    scoring_config = db_session.execute(select(ScoringConfiguration)).scalars().first()
    # High SDI = 4.50
    area_sdi = AreaScore(
        administrative_area_id=area.id,
        configuration_id=scoring_config.id,
        score=Decimal("4.50"),
        completeness_pct=Decimal("20.00"),
        participating_categories_count=1,
        total_categories_count=5,
        eligible_reports_count=1,
        is_current=True,
    )
    db_session.add(area_sdi)

    # 1 unverified report submitted 25 days ago
    _create_report(
        db_session,
        area.id,
        citizen,
        cat,
        "SUBMITTED",
        observed_at=datetime.now(UTC) - timedelta(days=25),
    )

    score = calculate_area_inspection_priority(db_session, area.id)

    # Confidence gap should be 75.0 (since no confidence score exists)
    components = score.calculation_metadata["components"]
    assert components["confidence_gap"]["score"] == 75.0
    assert score.priority_score is not None
    assert score.priority_score >= Decimal("60.00")
    assert score.priority_level in ("HIGH", "CRITICAL")


def test_priority_history_preservation(db_session: Session) -> None:
    """Verify recalculating priority archives prior score and appends new audit record."""
    area = _create_area(db_session, "Audit Ward", "AUDIT_WARD_01")

    first_calc = calculate_area_inspection_priority(db_session, area.id)
    assert first_calc.is_current is True

    second_calc = calculate_area_inspection_priority(db_session, area.id)
    assert second_calc.is_current is True

    db_session.refresh(first_calc)
    assert first_calc.is_current is False

    history, total = get_area_priority_history(db_session, area.id)
    assert total >= 2
    assert len(history) >= 2
    assert history[0].id == second_calc.id
    assert history[0].is_current is True


def test_priority_history_deterministic_ordering_with_equal_timestamps(
    db_session: Session,
) -> None:
    """Verify deterministic ordering when multiple records share identical timestamps:
    1. Active current record is returned first regardless of UUID.
    2. Archived records with identical timestamps are ordered by UUID descending.
    """
    area = _create_area(db_session, "Tiebreaker Ward", "TIE_WARD_01")
    config = get_active_priority_config(db_session)

    fixed_time = datetime(2026, 11, 2, 12, 0, 0, tzinfo=UTC)

    # Prepare three UUIDs with known sort order: u_low < u_mid < u_high
    u_low = uuid.UUID("10000000-0000-0000-0000-000000000001")
    u_mid = uuid.UUID("50000000-0000-0000-0000-000000000001")
    u_high = uuid.UUID("90000000-0000-0000-0000-000000000001")

    # Current record given the lowest UUID to verify is_current precedes UUID sort
    current_rec = AreaPriorityScore(
        id=u_low,
        area_id=area.id,
        configuration_id=config.id,
        priority_score=Decimal("50.00"),
        priority_level="MEDIUM",
        calculation_metadata={},
        is_current=True,
        calculation_timestamp=fixed_time,
    )
    # Archived record with mid UUID
    archived_mid = AreaPriorityScore(
        id=u_mid,
        area_id=area.id,
        configuration_id=config.id,
        priority_score=Decimal("40.00"),
        priority_level="LOW",
        calculation_metadata={},
        is_current=False,
        calculation_timestamp=fixed_time,
    )
    # Archived record with high UUID
    archived_high = AreaPriorityScore(
        id=u_high,
        area_id=area.id,
        configuration_id=config.id,
        priority_score=Decimal("30.00"),
        priority_level="LOW",
        calculation_metadata={},
        is_current=False,
        calculation_timestamp=fixed_time,
    )

    db_session.add_all([current_rec, archived_mid, archived_high])
    db_session.commit()

    history, total = get_area_priority_history(db_session, area.id)
    assert total == 3
    assert len(history) == 3

    # 1. Current record is returned first even though its UUID is the lowest
    assert history[0].id == u_low
    assert history[0].is_current is True

    # 2. Archived records with equal timestamps are broken by UUID DESC: u_high > u_mid
    assert history[1].id == u_high
    assert history[1].is_current is False

    assert history[2].id == u_mid
    assert history[2].is_current is False


def test_api_calculate_priority_rbac(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify RBAC on calculate-priority endpoint: admin allowed, verifier & citizen forbidden."""
    area = _create_area(db_session, "RBAC Ward", "RBAC_WARD_01")
    _, admin_token = _create_user_with_role(db_session, "admin")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, citizen_token = _create_user_with_role(db_session, "citizen")

    url = f"/api/v1/admin/intelligence/areas/{area.id}/calculate-priority"

    # Citizen -> 403
    resp_cit = auth_client.post(url, headers={"Authorization": f"Bearer {citizen_token}"})
    assert resp_cit.status_code == status.HTTP_403_FORBIDDEN

    # Verifier -> 403 (calculate is admin only)
    resp_ver = auth_client.post(url, headers={"Authorization": f"Bearer {verifier_token}"})
    assert resp_ver.status_code == status.HTTP_403_FORBIDDEN

    # Admin -> 200
    resp_adm = auth_client.post(url, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp_adm.status_code == status.HTTP_200_OK
    assert resp_adm.json()["priority_level"] == "INSUFFICIENT_DATA"


def test_api_list_area_priorities(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify listing ranked area priorities with filters."""
    area = _create_area(db_session, "Listing Ward", "LIST_WARD_01")
    calculate_area_inspection_priority(db_session, area.id)

    _, admin_token = _create_user_with_role(db_session, "admin")

    url = "/api/v1/admin/intelligence/priority/areas?priority_level=INSUFFICIENT_DATA"
    resp = auth_client.get(url, headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["total"] >= 1
    assert any(item["area_id"] == str(area.id) for item in data["items"])
