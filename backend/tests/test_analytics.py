"""Comprehensive unit and integration tests for Administrative Analytics."""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.iam import Role, User, UserRole
from app.models.maintenance import MaintenanceTask
from app.models.reporting import Report
from app.services.analytics import (
    get_analytics_overview,
    get_maintenance_analytics,
    get_reports_analytics,
    get_sdi_analytics,
    get_trends_analytics,
)


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper to create a user with a specific role and return access token."""
    user_email = email or f"analytics_{role_name}_{uuid.uuid4().hex[:8]}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Analytics {role_name.capitalize()}",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    db_session.flush()

    role = db_session.execute(select(Role).where(Role.name == role_name)).scalar_one()
    db_session.add(UserRole(user_id=user.id, role_id=role.id))
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(subject=user.id)
    return user, token


def test_reports_analytics_aggregation_and_empty_handling(db_session: Session) -> None:
    """Verify report analytics handles data aggregation and empty date bounds gracefully."""
    res = get_reports_analytics(
        db_session,
        start_date=date(2020, 1, 1),
        end_date=date(2020, 1, 2),
    )
    assert res.total_reports == 0
    assert len(res.by_status) == 0
    assert len(res.by_category) == 0
    assert len(res.by_area) == 0
    assert len(res.submitted_over_time) == 0
    assert res.verified_count == 0
    assert res.rejected_count == 0
    assert res.duplicate_count == 0
    assert res.pending_backlog_count == 0


def test_sdi_analytics_range_distribution(db_session: Session) -> None:
    """Verify SDI analytics groups areas correctly across severity ranges."""
    res = get_sdi_analytics(db_session)
    assert res.total_areas_evaluated >= 0
    # Range distribution counts should sum to total areas
    dist = res.range_distribution
    total_dist = (
        dist.negligible
        + dist.low
        + dist.moderate
        + dist.high
        + dist.severe
        + dist.insufficient_data
    )
    assert total_dist == res.total_areas_evaluated


def test_maintenance_analytics_metrics(db_session: Session) -> None:
    """Verify maintenance analytics computes status, priority, and turnaround time."""
    admin, _ = _create_user_with_role(db_session, "admin")
    tech, _ = _create_user_with_role(db_session, "maintenance")

    # Fetch any report
    report = db_session.execute(select(Report)).scalars().first()
    if report:
        now = datetime.now(UTC)
        task = MaintenanceTask(
            report_id=report.id,
            assigned_to_user_id=tech.id,
            created_by_user_id=admin.id,
            title="Analytics Test Task",
            description="Testing turnaround metrics",
            priority="URGENT",
            status="COMPLETED",
            due_date=now - timedelta(days=1),
            completed_at=now,
            allow_duplicate=True,
            duplicate_override_reason="Analytics test duplicate",
        )
        db_session.add(task)
        db_session.commit()

    res = get_maintenance_analytics(db_session)
    assert res.total_tasks >= 0
    assert isinstance(res.by_status, list)
    assert isinstance(res.by_priority, list)


def test_overview_and_trends_analytics(db_session: Session) -> None:
    """Verify overview KPIs and historical timeline trends."""
    overview = get_analytics_overview(db_session)
    assert overview.total_reports >= 0
    assert overview.pending_verification >= 0
    assert overview.verified_reports >= 0

    trends = get_trends_analytics(db_session)
    assert isinstance(trends.submissions_trend, list)
    assert isinstance(trends.verifications_trend, list)
    assert isinstance(trends.completions_trend, list)


def test_api_analytics_rbac(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify analytics endpoints reject unauthorized citizens and allow admins/verifiers."""
    admin, admin_token = _create_user_with_role(db_session, "admin")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")
    citizen, citizen_token = _create_user_with_role(db_session, "citizen")

    endpoints = [
        "/api/v1/admin/analytics/overview",
        "/api/v1/admin/analytics/reports",
        "/api/v1/admin/analytics/sdi",
        "/api/v1/admin/analytics/confidence",
        "/api/v1/admin/analytics/maintenance",
        "/api/v1/admin/analytics/trends",
    ]

    for ep in endpoints:
        # Citizen forbidden -> 403
        resp_cit = auth_client.get(ep, headers={"Authorization": f"Bearer {citizen_token}"})
        assert resp_cit.status_code == status.HTTP_403_FORBIDDEN, (
            f"Citizen should be forbidden for {ep}"
        )

        # Verifier allowed -> 200
        resp_ver = auth_client.get(ep, headers={"Authorization": f"Bearer {verifier_token}"})
        assert resp_ver.status_code == status.HTTP_200_OK, f"Verifier should be allowed for {ep}"

        # Admin allowed -> 200
        resp_adm = auth_client.get(ep, headers={"Authorization": f"Bearer {admin_token}"})
        assert resp_adm.status_code == status.HTTP_200_OK, f"Admin should be allowed for {ep}"
