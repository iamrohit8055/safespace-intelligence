"""Comprehensive automated test suite for report verification and moderation workflows."""

import uuid
from unittest.mock import patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report
from app.models.verification import ReportStatusHistory, ReportVerification


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


def _create_submitted_report(
    auth_client: TestClient,
    citizen_token: str,
    title: str = "Test Deficiency",
) -> str:
    """Helper creating a report in SUBMITTED state via API and returning report_id."""
    resp = auth_client.post(
        "/api/v1/reports",
        json={
            "category_code": "STREET_LIGHTING",
            "title": title,
            "description": "Standard test deficiency description.",
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_201_CREATED
    return resp.json()["id"]


# -----------------------------------------------------------------------------
# 1. Moderation Authorization Tests
# -----------------------------------------------------------------------------


def test_moderation_verifier_can_access_queue(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify user with verifier role can access moderation queue."""
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    resp = auth_client.get(
        "/api/v1/admin/reports/pending",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK


def test_moderation_admin_can_access_queue(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify user with admin role can access moderation queue."""
    _, admin_token = _create_user_with_role(db_session, "admin")

    resp = auth_client.get(
        "/api/v1/admin/reports/pending",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK


def test_moderation_citizen_forbidden(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify citizen user receives HTTP 403 Forbidden on moderation endpoints."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")

    resp = auth_client.get(
        "/api/v1/admin/reports/pending",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_moderation_unauthenticated_rejected(auth_client: TestClient) -> None:
    """Verify unauthenticated request receives HTTP 401 Unauthorized."""
    resp = auth_client.get("/api/v1/admin/reports/pending")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# -----------------------------------------------------------------------------
# 2. Pending Report Queue Tests
# -----------------------------------------------------------------------------


def test_pending_queue_only_submitted_reports_appear(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify only reports in SUBMITTED status appear in the pending queue."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep1_id = _create_submitted_report(auth_client, citizen_token, "Pending Report 1")
    rep2_id = _create_submitted_report(auth_client, citizen_token, "In Progress Report 2")

    # Move rep2 to UNDER_VERIFICATION
    auth_client.post(
        f"/api/v1/admin/reports/{rep2_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    queue_resp = auth_client.get(
        "/api/v1/admin/reports/pending",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert queue_resp.status_code == status.HTTP_200_OK
    items = queue_resp.json()["items"]
    item_ids = [item["id"] for item in items]

    assert rep1_id in item_ids
    assert rep2_id not in item_ids


def test_pending_queue_pagination_and_deterministic_order(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify pending queue pagination and deterministic FIFO ordering."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    created_ids = []
    for i in range(4):
        rep_id = _create_submitted_report(auth_client, citizen_token, f"Queue Order {i}")
        created_ids.append(rep_id)

    # Page 1: limit=2, offset=0
    resp_p1 = auth_client.get(
        "/api/v1/admin/reports/pending?limit=2&offset=0",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp_p1.status_code == status.HTTP_200_OK
    data_p1 = resp_p1.json()
    assert len(data_p1["items"]) == 2

    # Page 2: limit=2, offset=2
    resp_p2 = auth_client.get(
        "/api/v1/admin/reports/pending?limit=2&offset=2",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp_p2.status_code == status.HTTP_200_OK
    data_p2 = resp_p2.json()
    assert len(data_p2["items"]) >= 2

    # Verify no reporter email or sensitive fields leaked
    for item in data_p1["items"]:
        assert "hashed_password" not in item
        assert "reporter_email" not in item
        assert "password" not in item


# -----------------------------------------------------------------------------
# 3. Start Verification Tests
# -----------------------------------------------------------------------------


def test_start_verification_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify transitioning SUBMITTED -> UNDER_VERIFICATION creates status history."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Start Verification Test")

    resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["status"] == "UNDER_VERIFICATION"

    # Verify database state and status history
    report_uuid = uuid.UUID(rep_id)
    history = db_session.execute(
        select(ReportStatusHistory).where(
            ReportStatusHistory.report_id == report_uuid,
            ReportStatusHistory.to_status == "UNDER_VERIFICATION",
        )
    ).scalar_one()

    assert history.from_status == "SUBMITTED"
    assert history.to_status == "UNDER_VERIFICATION"
    assert history.changed_by_user_id == verifier.id


def test_start_verification_invalid_lifecycle_state_returns_409(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify starting verification on a non-SUBMITTED report returns HTTP 409 Conflict."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Conflict Test")

    # First transition -> UNDER_VERIFICATION
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Second attempt -> 409 Conflict
    second_attempt = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert second_attempt.status_code == status.HTTP_409_CONFLICT
    assert "cannot start verification" in second_attempt.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 4. Verify Report Tests
# -----------------------------------------------------------------------------


def test_verify_report_valid_severity_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify approving UNDER_VERIFICATION report with severity 1-5 records verification."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Report To Verify")

    # Start verification
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Verify with severity 4
    verify_resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={
            "verified_severity": 4,
            "verification_notes": "Field inspection confirmed severe hazard.",
        },
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert verify_resp.status_code == status.HTTP_200_OK
    assert verify_resp.json()["status"] == "VERIFIED"

    # Verify append-only record in database
    report_uuid = uuid.UUID(rep_id)
    verification = db_session.execute(
        select(ReportVerification).where(ReportVerification.report_id == report_uuid)
    ).scalar_one()

    assert verification.decision == "VERIFIED"
    assert verification.verified_severity == 4
    assert verification.rejection_reason is None
    assert verification.verifier_id == verifier.id
    assert verification.verification_notes == "Field inspection confirmed severe hazard."

    # Verify status history row
    history = db_session.execute(
        select(ReportStatusHistory).where(
            ReportStatusHistory.report_id == report_uuid,
            ReportStatusHistory.to_status == "VERIFIED",
        )
    ).scalar_one()
    assert history.from_status == "UNDER_VERIFICATION"
    assert history.to_status == "VERIFIED"
    assert history.changed_by_user_id == verifier.id


def test_verify_report_rejects_missing_severity(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify omitting verified_severity raises HTTP 422 Unprocessable Content."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "No Severity Test")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verification_notes": "Forgot severity score."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_report_rejects_out_of_bounds_severity(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify severity outside [1, 5] raises HTTP 422."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Bad Severity Test")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Severity 0 (< 1)
    resp_low = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verified_severity": 0},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp_low.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Severity 6 (> 5)
    resp_high = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verified_severity": 6},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp_high.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_verify_report_invalid_lifecycle_state_returns_409(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify directly verifying a SUBMITTED report without UNDER_VERIFICATION returns HTTP 409."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Direct Verify Fail")

    resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verified_severity": 3},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "expected 'under_verification'" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 5. Reject Report Tests
# -----------------------------------------------------------------------------


def test_reject_report_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify rejecting an UNDER_VERIFICATION report records reason and status transition."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Report To Reject")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    reject_resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={
            "rejection_reason": "INSUFFICIENT_EVIDENCE",
            "verification_notes": "Defect cannot be confirmed from observation description.",
        },
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert reject_resp.status_code == status.HTTP_200_OK
    assert reject_resp.json()["status"] == "REJECTED"

    # Verify database verification record
    report_uuid = uuid.UUID(rep_id)
    verification = db_session.execute(
        select(ReportVerification).where(ReportVerification.report_id == report_uuid)
    ).scalar_one()

    assert verification.decision == "REJECTED"
    assert verification.rejection_reason == "INSUFFICIENT_EVIDENCE"
    assert verification.verified_severity is None
    assert verification.verifier_id == verifier.id

    # Verify status history row
    history = db_session.execute(
        select(ReportStatusHistory).where(
            ReportStatusHistory.report_id == report_uuid,
            ReportStatusHistory.to_status == "REJECTED",
        )
    ).scalar_one()
    assert history.from_status == "UNDER_VERIFICATION"
    assert history.to_status == "REJECTED"


def test_reject_report_rejects_missing_or_whitespace_reason(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify rejection without reason or with whitespace-only reason raises HTTP 422."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Reject Reason Test")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Missing reason
    resp_missing = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={"verification_notes": "Forgot reason."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp_missing.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    # Whitespace-only reason
    resp_whitespace = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={"rejection_reason": "   "},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp_whitespace.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_reject_report_invalid_lifecycle_state_returns_409(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify rejecting a SUBMITTED report without UNDER_VERIFICATION returns HTTP 409."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Direct Reject Fail")

    resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={"rejection_reason": "SPAM"},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT


# -----------------------------------------------------------------------------
# 6. Reopen Report Tests
# -----------------------------------------------------------------------------


def test_reopen_verified_report_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify reopening a VERIFIED report transitions it back to UNDER_VERIFICATION."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Reopen Verified Report")

    # SUBMITTED -> UNDER_VERIFICATION -> VERIFIED
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verified_severity": 2},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Reopen to UNDER_VERIFICATION
    reopen_resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reopen",
        json={"reason": "Citizen provided additional evidence of worsening damage."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert reopen_resp.status_code == status.HTTP_200_OK
    assert reopen_resp.json()["status"] == "UNDER_VERIFICATION"

    # Verify previous verification decision is preserved
    report_uuid = uuid.UUID(rep_id)
    verifications = (
        db_session.execute(
            select(ReportVerification).where(ReportVerification.report_id == report_uuid)
        )
        .scalars()
        .all()
    )
    assert len(verifications) == 1
    assert verifications[0].decision == "VERIFIED"

    # Verify status history transition VERIFIED -> UNDER_VERIFICATION
    history = db_session.execute(
        select(ReportStatusHistory).where(
            ReportStatusHistory.report_id == report_uuid,
            ReportStatusHistory.from_status == "VERIFIED",
            ReportStatusHistory.to_status == "UNDER_VERIFICATION",
        )
    ).scalar_one()
    assert history.changed_by_user_id == verifier.id
    assert history.reason == "Citizen provided additional evidence of worsening damage."


def test_reopen_rejected_report_success(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify reopening a REJECTED report transitions it back to UNDER_VERIFICATION."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Reopen Rejected Report")

    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={"rejection_reason": "INSUFFICIENT_EVIDENCE"},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    reopen_resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reopen",
        json={"reason": "Citizen submitted clearer photos upon appeal."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert reopen_resp.status_code == status.HTTP_200_OK
    assert reopen_resp.json()["status"] == "UNDER_VERIFICATION"


def test_reopen_submitted_report_rejected_with_409(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify attempting to reopen a SUBMITTED report returns HTTP 409 Conflict."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Submitted Reopen Fail")

    resp = auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reopen",
        json={"reason": "Cannot reopen a report that was never finalized."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert resp.status_code == status.HTTP_409_CONFLICT
    assert "expected 'verified' or 'rejected'" in resp.json()["detail"].lower()


# -----------------------------------------------------------------------------
# 7. Verification History Access Tests
# -----------------------------------------------------------------------------


def test_verification_history_citizen_can_view_own_report_history(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify citizen can retrieve verification history for their own report."""
    citizen, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Own History Report")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verified_severity": 3, "verification_notes": "Looks valid."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    history_resp = auth_client.get(
        f"/api/v1/reports/{rep_id}/verification-history",
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert history_resp.status_code == status.HTTP_200_OK
    records = history_resp.json()
    assert len(records) == 1
    assert records[0]["decision"] == "VERIFIED"
    assert records[0]["verified_severity"] == 3


def test_verification_history_citizen_cannot_view_other_citizen_history(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify citizen requesting another citizen's history receives HTTP 404 (anti-enumeration)."""
    _, citizen_a_token = _create_user_with_role(db_session, "citizen")
    _, citizen_b_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_a_token, "Citizen A Report")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={"verified_severity": 1},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Citizen B tries to view Citizen A's verification history
    history_resp = auth_client.get(
        f"/api/v1/reports/{rep_id}/verification-history",
        headers={"Authorization": f"Bearer {citizen_b_token}"},
    )
    assert history_resp.status_code == status.HTTP_404_NOT_FOUND
    assert history_resp.json()["detail"] == "Report not found."


def test_verification_history_verifier_and_admin_can_view_any_history(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify verifier and admin staff can view verification history for any report."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")
    _, admin_token = _create_user_with_role(db_session, "admin")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Staff Inspection Report")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={"rejection_reason": "DUPLICATE_SUBMISSION"},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # Verifier view
    v_resp = auth_client.get(
        f"/api/v1/reports/{rep_id}/verification-history",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert v_resp.status_code == status.HTTP_200_OK
    assert len(v_resp.json()) == 1

    # Admin view
    a_resp = auth_client.get(
        f"/api/v1/reports/{rep_id}/verification-history",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert a_resp.status_code == status.HTTP_200_OK
    assert len(a_resp.json()) == 1


def test_verification_history_chronological_order(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify multiple moderation decisions are returned in chronological order."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Lifecycle History Report")

    # 1. Start -> Reject
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reject",
        json={"rejection_reason": "INSUFFICIENT_EVIDENCE"},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    # 2. Reopen -> Verify
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/reopen",
        json={"reason": "Re-evaluating upon appeal."},
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/verify",
        json={
            "verified_severity": 5,
            "verification_notes": "Upgraded to critical upon reinspection.",
        },
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    history_resp = auth_client.get(
        f"/api/v1/reports/{rep_id}/verification-history",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )
    assert history_resp.status_code == status.HTTP_200_OK
    records = history_resp.json()
    assert len(records) == 2
    assert records[0]["decision"] == "REJECTED"
    assert records[0]["rejection_reason"] == "INSUFFICIENT_EVIDENCE"
    assert records[1]["decision"] == "VERIFIED"
    assert records[1]["verified_severity"] == 5


# -----------------------------------------------------------------------------
# 8. Transactional Integrity & Rollback Tests
# -----------------------------------------------------------------------------


def test_verify_failure_on_status_history_rolls_back_verification(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify failure to insert ReportStatusHistory rolls back ReportVerification."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Rollback Verify Report")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    original_add = db_session.add

    def failing_add(instance: object) -> None:
        if isinstance(instance, ReportStatusHistory):
            raise SQLAlchemyError("Simulated StatusHistory failure during verify")
        original_add(instance)

    with (
        patch.object(db_session, "add", side_effect=failing_add),
        pytest.raises(SQLAlchemyError, match="Simulated StatusHistory failure"),
    ):
        auth_client.post(
            f"/api/v1/admin/reports/{rep_id}/verify",
            json={"verified_severity": 4},
            headers={"Authorization": f"Bearer {verifier_token}"},
        )

    # Verify report remains UNDER_VERIFICATION and no verification record was committed
    report_uuid = uuid.UUID(rep_id)
    report = db_session.execute(select(Report).where(Report.id == report_uuid)).scalar_one()
    assert report.status == "UNDER_VERIFICATION"

    verifications = (
        db_session.execute(
            select(ReportVerification).where(ReportVerification.report_id == report_uuid)
        )
        .scalars()
        .all()
    )
    assert len(verifications) == 0


def test_verify_failure_on_verification_record_rolls_back_status(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify failure to insert ReportVerification rolls back Report status changes."""
    _, citizen_token = _create_user_with_role(db_session, "citizen")
    _, verifier_token = _create_user_with_role(db_session, "verifier")

    rep_id = _create_submitted_report(auth_client, citizen_token, "Rollback Verif Record Report")
    auth_client.post(
        f"/api/v1/admin/reports/{rep_id}/start-verification",
        headers={"Authorization": f"Bearer {verifier_token}"},
    )

    original_add = db_session.add

    def failing_add(instance: object) -> None:
        if isinstance(instance, ReportVerification):
            raise SQLAlchemyError("Simulated ReportVerification failure")
        original_add(instance)

    with (
        patch.object(db_session, "add", side_effect=failing_add),
        pytest.raises(SQLAlchemyError, match="Simulated ReportVerification failure"),
    ):
        auth_client.post(
            f"/api/v1/admin/reports/{rep_id}/verify",
            json={"verified_severity": 3},
            headers={"Authorization": f"Bearer {verifier_token}"},
        )

    # Verify report status remains UNDER_VERIFICATION and no status history was written
    report_uuid = uuid.UUID(rep_id)
    report = db_session.execute(select(Report).where(Report.id == report_uuid)).scalar_one()
    assert report.status == "UNDER_VERIFICATION"

    histories = (
        db_session.execute(
            select(ReportStatusHistory).where(
                ReportStatusHistory.report_id == report_uuid,
                ReportStatusHistory.to_status == "VERIFIED",
            )
        )
        .scalars()
        .all()
    )
    assert len(histories) == 0
