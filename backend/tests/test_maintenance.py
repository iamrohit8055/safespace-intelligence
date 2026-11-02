"""Comprehensive unit and integration tests for Infrastructure Maintenance Management."""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportVerification
from app.schemas.maintenance import (
    MaintenanceTaskAssignRequest,
    MaintenanceTaskCreateRequest,
    MaintenanceTaskTransitionRequest,
)
from app.services.maintenance import (
    assign_maintenance_task,
    create_maintenance_task,
    get_task_history,
    transition_maintenance_task,
)


def _create_user_with_role(
    db_session: Session,
    role_name: str,
    email: str | None = None,
) -> tuple[User, str]:
    """Helper to create a user with a specific role and return access token."""
    user_email = email or f"maint_{role_name}_{uuid.uuid4().hex[:8]}@safespace.org"
    user = User(
        email=user_email,
        hashed_password=hash_password("SecurePassword123!"),
        full_name=f"Maintenance {role_name.capitalize()}",
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


def _create_verified_report(
    db_session: Session,
    reporter: User,
    verifier: User,
    status_val: str = "VERIFIED",
) -> Report:
    """Helper to create a report with a specified status."""
    cat = db_session.execute(
        select(ReportCategory).where(ReportCategory.code == "STREET_LIGHTING")
    ).scalar_one()

    area = db_session.execute(select(AdministrativeArea)).scalars().first()
    if not area:
        area = AdministrativeArea(
            name="Maint Test Ward",
            code="MAINT_WARD_01",
            area_type="ward",
            boundary="SRID=4326;MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)))",
        )
        db_session.add(area)
        db_session.commit()
        db_session.refresh(area)

    report = Report(
        reporter_id=reporter.id,
        category_id=cat.id,
        administrative_area_id=area.id,
        title="Defective Street Lamp",
        description="Flickering luminaire requiring maintenance.",
        location="SRID=4326;POINT(0.5 0.5)",
        status=status_val,
        observed_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    if status_val == "VERIFIED":
        verification = ReportVerification(
            report_id=report.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=4,
            verification_notes="Confirmed burnt ballast.",
        )
        db_session.add(verification)

    db_session.commit()
    db_session.refresh(report)
    return report


def test_create_maintenance_task_success(db_session: Session) -> None:
    """Verify admin can create a maintenance task for a verified report."""
    admin, _ = _create_user_with_role(db_session, "admin")
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    tech, _ = _create_user_with_role(db_session, "maintenance")

    report = _create_verified_report(db_session, citizen, verifier, status_val="VERIFIED")

    payload = MaintenanceTaskCreateRequest(
        report_id=report.id,
        assigned_to_user_id=tech.id,
        title="Repair street lamp ballast",
        description="Replace 150W ballast on pole #42",
        priority="HIGH",
        follow_up_required=True,
    )

    task = create_maintenance_task(db_session, payload, admin)

    assert task.report_id == report.id
    assert task.assigned_to_user_id == tech.id
    assert task.status == "ASSIGNED"
    assert task.priority == "HIGH"
    assert task.follow_up_required is True

    # Verify event was recorded
    events = get_task_history(db_session, task.id)
    assert len(events) == 1
    assert events[0].new_status == "ASSIGNED"
    assert events[0].event_type == "TASK_ASSIGNED"


def test_create_task_unverified_report_rejected(db_session: Session) -> None:
    """Verify creating a maintenance task on an unverified report raises 400."""
    from fastapi import HTTPException

    admin, _ = _create_user_with_role(db_session, "admin")
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")

    report = _create_verified_report(db_session, citizen, verifier, status_val="SUBMITTED")

    payload = MaintenanceTaskCreateRequest(
        report_id=report.id,
        title="Attempt unverified task",
        description="Should be rejected because report is not verified.",
        priority="LOW",
    )

    with pytest.raises(HTTPException) as exc_info:
        create_maintenance_task(db_session, payload, admin)
    assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST
    assert "VERIFIED" in exc_info.value.detail


def test_prevent_duplicate_active_task_without_override(db_session: Session) -> None:
    """Verify duplicate active task for same report is rejected unless overridden."""
    from fastapi import HTTPException

    admin, _ = _create_user_with_role(db_session, "admin")
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")

    report = _create_verified_report(db_session, citizen, verifier, status_val="VERIFIED")

    p1 = MaintenanceTaskCreateRequest(
        report_id=report.id,
        title="First task",
        description="First work order on report.",
        priority="MEDIUM",
    )
    create_maintenance_task(db_session, p1, admin)

    # Second task without allow_duplicate
    p2 = MaintenanceTaskCreateRequest(
        report_id=report.id,
        title="Second task",
        description="Second duplicate work order without override.",
        priority="MEDIUM",
    )
    with pytest.raises(HTTPException) as exc_info:
        create_maintenance_task(db_session, p2, admin)
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT

    # Second task WITH allow_duplicate and override reason
    p3 = MaintenanceTaskCreateRequest(
        report_id=report.id,
        title="Second task approved",
        description="Electrical team secondary inspection.",
        priority="MEDIUM",
        allow_duplicate=True,
        duplicate_override_reason="Separate structural work required concurrently.",
    )
    task2 = create_maintenance_task(db_session, p3, admin)
    assert task2.allow_duplicate is True


def test_maintenance_lifecycle_transitions(db_session: Session) -> None:
    """Verify full state transition sequence from CREATED to COMPLETED."""
    admin, _ = _create_user_with_role(db_session, "admin")
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    tech, _ = _create_user_with_role(db_session, "maintenance")

    report = _create_verified_report(db_session, citizen, verifier, status_val="VERIFIED")

    # 1. Create (unassigned -> CREATED)
    task = create_maintenance_task(
        db_session,
        MaintenanceTaskCreateRequest(
            report_id=report.id,
            title="Pavement repair",
            description="Repair pothole",
            priority="HIGH",
        ),
        admin,
    )
    assert task.status == "CREATED"

    # 2. Assign -> ASSIGNED
    task = assign_maintenance_task(
        db_session,
        task.id,
        MaintenanceTaskAssignRequest(assigned_to_user_id=tech.id, notes="Assigned to tech"),
        admin,
    )
    assert task.status == "ASSIGNED"
    assert task.assigned_to_user_id == tech.id

    # 3. Accept -> ACCEPTED
    task = transition_maintenance_task(
        db_session,
        task.id,
        target_status="ACCEPTED",
        event_type="TASK_ACCEPTED",
        payload=None,
        current_user=tech,
        require_assignee_match=True,
    )
    assert task.status == "ACCEPTED"

    # 4. Start -> IN_PROGRESS
    task = transition_maintenance_task(
        db_session,
        task.id,
        target_status="IN_PROGRESS",
        event_type="TASK_STARTED",
        payload=None,
        current_user=tech,
        require_assignee_match=True,
    )
    assert task.status == "IN_PROGRESS"

    # 5. Block -> BLOCKED
    task = transition_maintenance_task(
        db_session,
        task.id,
        target_status="BLOCKED",
        event_type="TASK_BLOCKED",
        payload=MaintenanceTaskTransitionRequest(notes="Inclement weather delayed concrete curing"),
        current_user=tech,
        require_assignee_match=True,
    )
    assert task.status == "BLOCKED"

    # 6. Resume -> IN_PROGRESS
    task = transition_maintenance_task(
        db_session,
        task.id,
        target_status="IN_PROGRESS",
        event_type="TASK_STARTED",
        payload=MaintenanceTaskTransitionRequest(notes="Weather cleared; resuming work"),
        current_user=tech,
        require_assignee_match=True,
    )
    assert task.status == "IN_PROGRESS"

    # 7. Complete -> COMPLETED
    task = transition_maintenance_task(
        db_session,
        task.id,
        target_status="COMPLETED",
        event_type="TASK_COMPLETED",
        payload=MaintenanceTaskTransitionRequest(
            notes="Pavement patch successfully set and tested"
        ),
        current_user=tech,
        require_assignee_match=True,
    )
    assert task.status == "COMPLETED"
    assert task.completed_at is not None

    # Verify event audit ledger
    history = get_task_history(db_session, task.id)
    assert len(history) == 7
    event_statuses = [h.new_status for h in history]
    assert event_statuses == [
        "CREATED",
        "ASSIGNED",
        "ACCEPTED",
        "IN_PROGRESS",
        "BLOCKED",
        "IN_PROGRESS",
        "COMPLETED",
    ]


def test_invalid_lifecycle_transition_raises_conflict(db_session: Session) -> None:
    """Verify invalid transition (e.g. directly from CREATED to COMPLETED) raises 409."""
    from fastapi import HTTPException

    admin, _ = _create_user_with_role(db_session, "admin")
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")

    report = _create_verified_report(db_session, citizen, verifier, status_val="VERIFIED")

    task = create_maintenance_task(
        db_session,
        MaintenanceTaskCreateRequest(
            report_id=report.id,
            title="Direct jump test",
            description="Testing invalid jump",
            priority="LOW",
        ),
        admin,
    )

    with pytest.raises(HTTPException) as exc_info:
        transition_maintenance_task(
            db_session,
            task.id,
            target_status="COMPLETED",
            event_type="TASK_COMPLETED",
            payload=None,
            current_user=admin,
        )
    assert exc_info.value.status_code == status.HTTP_409_CONFLICT


def test_technician_cannot_modify_other_technician_task(db_session: Session) -> None:
    """Verify a technician cannot accept or modify a task assigned to another technician."""
    from fastapi import HTTPException

    admin, _ = _create_user_with_role(db_session, "admin")
    citizen, _ = _create_user_with_role(db_session, "citizen")
    verifier, _ = _create_user_with_role(db_session, "verifier")
    tech1, _ = _create_user_with_role(db_session, "maintenance")
    tech2, _ = _create_user_with_role(db_session, "maintenance")

    report = _create_verified_report(db_session, citizen, verifier, status_val="VERIFIED")

    task = create_maintenance_task(
        db_session,
        MaintenanceTaskCreateRequest(
            report_id=report.id,
            assigned_to_user_id=tech1.id,
            title="Tech 1 exclusive task",
            description="Only tech 1 should accept this",
            priority="MEDIUM",
        ),
        admin,
    )

    with pytest.raises(HTTPException) as exc_info:
        transition_maintenance_task(
            db_session,
            task.id,
            target_status="ACCEPTED",
            event_type="TASK_ACCEPTED",
            payload=None,
            current_user=tech2,
            require_assignee_match=True,
        )
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


def test_api_maintenance_endpoints_rbac(
    auth_client: TestClient,
    db_session: Session,
) -> None:
    """Verify RBAC on maintenance endpoints."""
    admin, admin_token = _create_user_with_role(db_session, "admin")
    tech, tech_token = _create_user_with_role(db_session, "maintenance")
    citizen, citizen_token = _create_user_with_role(db_session, "citizen")
    verifier, verifier_token = _create_user_with_role(db_session, "verifier")

    report = _create_verified_report(db_session, citizen, verifier, status_val="VERIFIED")

    create_url = "/api/v1/admin/maintenance/tasks"
    payload = {
        "report_id": str(report.id),
        "assigned_to_user_id": str(tech.id),
        "title": "API RBAC Test Task",
        "description": "Testing RBAC permissions",
        "priority": "HIGH",
    }

    # Citizen forbidden -> 403
    resp_cit = auth_client.post(
        create_url, json=payload, headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert resp_cit.status_code == status.HTTP_403_FORBIDDEN

    # Tech forbidden from creating -> 403
    resp_tech = auth_client.post(
        create_url, json=payload, headers={"Authorization": f"Bearer {tech_token}"}
    )
    assert resp_tech.status_code == status.HTTP_403_FORBIDDEN

    # Admin allowed -> 201
    resp_adm = auth_client.post(
        create_url, json=payload, headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert resp_adm.status_code == status.HTTP_201_CREATED
    task_id = resp_adm.json()["id"]

    # Technician views their own tasks -> 200
    my_tasks_url = "/api/v1/maintenance/tasks/my"
    resp_my = auth_client.get(my_tasks_url, headers={"Authorization": f"Bearer {tech_token}"})
    assert resp_my.status_code == status.HTTP_200_OK
    assert any(t["id"] == task_id for t in resp_my.json()["items"])

    # Technician accepts task -> 200
    accept_url = f"/api/v1/maintenance/tasks/{task_id}/accept"
    resp_acc = auth_client.post(
        accept_url,
        json={"notes": "Accepting job"},
        headers={"Authorization": f"Bearer {tech_token}"},
    )
    assert resp_acc.status_code == status.HTTP_200_OK
    assert resp_acc.json()["status"] == "ACCEPTED"
