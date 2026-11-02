"""Comprehensive security, authorization, and operational hardening regression tests."""

import uuid
from datetime import UTC, datetime

from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper to create a user with a specific role and return access token."""
    user_email = email or f"sec_{role_name}_{uuid.uuid4().hex[:8]}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Security {role_name.capitalize()}",
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


def test_unauthenticated_requests_return_401(auth_client: TestClient) -> None:
    """Verify endpoints across all domains strictly reject unauthenticated requests."""
    endpoints = [
        ("GET", "/api/v1/reports"),
        ("POST", "/api/v1/reports"),
        ("GET", "/api/v1/notifications"),
        ("GET", "/api/v1/notifications/unread-count"),
        ("GET", "/api/v1/maintenance/tasks/my"),
        ("GET", "/api/v1/admin/maintenance/tasks"),
        ("GET", "/api/v1/admin/analytics/overview"),
        ("GET", "/api/v1/admin/intelligence/priority/configurations"),
    ]

    for method, url in endpoints:
        resp = auth_client.request(method, url)
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED, f"{method} {url} should be 401"


def test_citizen_forbidden_from_privileged_endpoints(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify citizen role receives 403 Forbidden on moderator, maintenance, and admin routes."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    headers = {"Authorization": f"Bearer {citizen_token}"}

    forbidden_endpoints = [
        ("GET", "/api/v1/admin/reports/pending"),
        ("GET", "/api/v1/admin/maintenance/tasks"),
        ("POST", "/api/v1/admin/maintenance/tasks"),
        ("GET", "/api/v1/admin/analytics/overview"),
        ("GET", "/api/v1/admin/analytics/reports"),
        ("GET", "/api/v1/admin/intelligence/scoring-configurations"),
        ("GET", "/api/v1/admin/intelligence/priority/configurations"),
        ("GET", "/api/v1/maintenance/tasks/my"),
    ]

    for method, url in forbidden_endpoints:
        resp = auth_client.request(method, url, headers=headers)
        assert resp.status_code == status.HTTP_403_FORBIDDEN, (
            f"Citizen should get 403 on {method} {url}"
        )


def test_pagination_bounds_enforced_across_endpoints(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify page size bounds (>100 limit, negative offset) are rejected with 422."""
    _, admin_token = _create_user_with_role(db_session, "admin")
    headers = {"Authorization": f"Bearer {admin_token}"}

    # Limit too large (> 100)
    resp1 = auth_client.get("/api/v1/admin/maintenance/tasks?limit=101", headers=headers)
    assert resp1.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Offset negative (< 0)
    resp2 = auth_client.get("/api/v1/admin/maintenance/tasks?offset=-1", headers=headers)
    assert resp2.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Priority pagination limit too large (> 100)
    resp3 = auth_client.get("/api/v1/admin/intelligence/priority/areas?limit=150", headers=headers)
    assert resp3.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Notifications limit too large (> 100)
    resp4 = auth_client.get("/api/v1/notifications?limit=200", headers=headers)
    assert resp4.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_citizen_cannot_read_another_citizen_report(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify a citizen cannot retrieve details of a report submitted by another citizen."""
    citizen1, token1 = _create_user_with_role(db_session, "citizen")
    citizen2, token2 = _create_user_with_role(db_session, "citizen")

    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    area = db_session.execute(select(AdministrativeArea)).scalars().first()

    r1 = Report(
        reporter_id=citizen1.id,
        category_id=cat.id,
        administrative_area_id=area.id if area else None,
        title="Citizen 1 Private Observation",
        description="Private report description.",
        location="SRID=4326;POINT(-74.0060 40.7128)",
        status="SUBMITTED",
        observed_at=datetime.now(UTC),
    )
    db_session.add(r1)
    db_session.commit()
    db_session.refresh(r1)

    # Citizen 1 can access
    resp1 = auth_client.get(
        f"/api/v1/reports/{r1.id}", headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp1.status_code == status.HTTP_200_OK

    # Citizen 2 receives 404 (not 200, protecting privacy)
    resp2 = auth_client.get(
        f"/api/v1/reports/{r1.id}", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp2.status_code == status.HTTP_404_NOT_FOUND
