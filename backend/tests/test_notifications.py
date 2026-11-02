"""Comprehensive unit and integration tests for In-App Notification Foundation."""

import uuid

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.iam import Role, User, UserRole
from app.models.reporting import ReportCategory
from app.schemas.reports import ReportCreateRequest
from app.schemas.verification import VerifyReportRequest
from app.services.notifications import (
    create_notification,
    get_user_unread_count,
    list_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)
from app.services.reports import create_citizen_report
from app.services.verification import start_report_verification, verify_report


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper to create a user with a specific role and return access token."""
    user_email = email or f"notif_{role_name}_{uuid.uuid4().hex[:8]}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Notification {role_name.capitalize()}",
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


def test_create_and_deduplicate_notification(db_session: Session) -> None:
    """Verify notification creation and deduplication of recent unread alerts."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    res_id = uuid.uuid4()

    n1 = create_notification(
        db_session,
        recipient_id=citizen.id,
        notification_type="REPORT_SUBMITTED",
        title="Report Submitted",
        message="Your report has been submitted.",
        resource_type="report",
        resource_id=res_id,
    )
    db_session.commit()

    # Attempt duplicate
    n2 = create_notification(
        db_session,
        recipient_id=citizen.id,
        notification_type="REPORT_SUBMITTED",
        title="Report Submitted",
        message="Your report has been submitted.",
        resource_type="report",
        resource_id=res_id,
    )
    db_session.commit()

    assert n1.id == n2.id
    count = get_user_unread_count(db_session, citizen.id)
    assert count == 1


def test_mark_read_and_read_all(db_session: Session) -> None:
    """Verify single read and read-all behavior for a user."""
    citizen, _ = _create_user_with_role(db_session, "citizen")

    n1 = create_notification(
        db_session,
        recipient_id=citizen.id,
        notification_type="SYSTEM_ALERT",
        title="Alert 1",
        message="Message 1",
    )
    create_notification(
        db_session,
        recipient_id=citizen.id,
        notification_type="SYSTEM_ALERT",
        title="Alert 2",
        message="Message 2",
    )
    db_session.commit()

    assert get_user_unread_count(db_session, citizen.id) == 2

    # Mark single read
    updated_n1 = mark_notification_as_read(db_session, n1.id, citizen.id)
    assert updated_n1.is_read is True
    assert updated_n1.read_at is not None
    assert get_user_unread_count(db_session, citizen.id) == 1

    # Mark all read
    updated_count = mark_all_notifications_as_read(db_session, citizen.id)
    assert updated_count == 1
    assert get_user_unread_count(db_session, citizen.id) == 0


def test_notification_ownership_isolation(db_session: Session) -> None:
    """Verify a user cannot read or access another user's notifications."""
    from fastapi import HTTPException

    u1, _ = _create_user_with_role(db_session, "citizen")
    u2, _ = _create_user_with_role(db_session, "citizen")

    notif = create_notification(
        db_session,
        recipient_id=u1.id,
        notification_type="SYSTEM_ALERT",
        title="Private Alert",
        message="Should not be accessible by user 2",
    )
    db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        mark_notification_as_read(db_session, notif.id, u2.id)
    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND


def test_report_lifecycle_generates_notifications(db_session: Session) -> None:
    """Verify report submission and verification generate notifications for citizen."""
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")

    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    # 1. Citizen submits report
    payload = ReportCreateRequest(
        category_id=cat.id,
        title="Dark Alley Luminaire",
        description="Luminaire out on alleyway.",
        latitude=40.7128,
        longitude=-74.0060,
    )
    report = create_citizen_report(db_session, payload, citizen)

    # Verify REPORT_SUBMITTED notification
    items, _, unread = list_user_notifications(db_session, citizen.id)
    assert unread == 1
    assert items[0].notification_type == "REPORT_SUBMITTED"
    assert items[0].resource_id == report.id

    # 2. Verifier starts verification
    start_report_verification(db_session, report.id, verifier)
    items, _, unread = list_user_notifications(db_session, citizen.id)
    assert unread == 2
    types = [item.notification_type for item in items]
    assert "REPORT_VERIFICATION_STARTED" in types

    # 3. Verifier approves report
    verify_report(
        db_session,
        report.id,
        VerifyReportRequest(verified_severity=3, verification_notes="Verified defective bulb"),
        verifier,
    )
    items, _, unread = list_user_notifications(db_session, citizen.id)
    assert unread == 3
    types = [item.notification_type for item in items]
    assert "REPORT_VERIFIED" in types


def test_api_notification_endpoints(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify notifications endpoints via API client."""
    citizen, token = _create_user_with_role(db_session, "citizen")

    n = create_notification(
        db_session,
        recipient_id=citizen.id,
        notification_type="TEST_EVENT",
        title="API Notification Test",
        message="Testing HTTP delivery",
    )
    db_session.commit()

    headers = {"Authorization": f"Bearer {token}"}

    # 1. Get unread count
    resp = auth_client.get("/api/v1/notifications/unread-count", headers=headers)
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["unread_count"] == 1

    # 2. List notifications
    resp_list = auth_client.get("/api/v1/notifications", headers=headers)
    assert resp_list.status_code == status.HTTP_200_OK
    assert resp_list.json()["total"] == 1
    assert resp_list.json()["items"][0]["id"] == str(n.id)

    # 3. Mark read
    resp_read = auth_client.post(f"/api/v1/notifications/{n.id}/read", headers=headers)
    assert resp_read.status_code == status.HTTP_200_OK
    assert resp_read.json()["is_read"] is True

    # 4. Read all
    resp_all = auth_client.post("/api/v1/notifications/read-all", headers=headers)
    assert resp_all.status_code == status.HTTP_200_OK
    assert resp_all.json()["unread_count"] == 0
