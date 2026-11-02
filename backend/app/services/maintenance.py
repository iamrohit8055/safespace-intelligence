"""Service layer implementing infrastructure maintenance task management and event auditing."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.iam import User
from app.models.maintenance import MaintenanceTask, MaintenanceTaskEvent
from app.models.reporting import Report
from app.schemas.maintenance import (
    MaintenanceTaskAssignRequest,
    MaintenanceTaskCreateRequest,
    MaintenanceTaskTransitionRequest,
)
from app.services.notifications import create_notification

VALID_TRANSITIONS: dict[str, set[str]] = {
    "CREATED": {"ASSIGNED", "CANCELLED"},
    "ASSIGNED": {"ACCEPTED", "ASSIGNED", "CANCELLED"},
    "ACCEPTED": {"IN_PROGRESS", "BLOCKED", "CANCELLED"},
    "IN_PROGRESS": {"BLOCKED", "COMPLETED", "CANCELLED"},
    "BLOCKED": {"IN_PROGRESS", "CANCELLED"},
    "COMPLETED": set(),
    "CANCELLED": set(),
}


def create_maintenance_task(
    db: Session,
    payload: MaintenanceTaskCreateRequest,
    current_user: User,
) -> MaintenanceTask:
    """Create a new maintenance task for a verified infrastructure deficiency report."""
    # 1. Verify report exists and is in VERIFIED status
    report = db.execute(select(Report).where(Report.id == payload.report_id)).scalar_one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{payload.report_id}' not found.",
        )

    if report.status != "VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Maintenance tasks can only be created for VERIFIED reports. "
                f"Report '{payload.report_id}' is currently '{report.status}'."
            ),
        )

    # 2. Check for existing active tasks if allow_duplicate is false
    if not payload.allow_duplicate:
        active_task = db.execute(
            select(MaintenanceTask).where(
                MaintenanceTask.report_id == payload.report_id,
                MaintenanceTask.status.not_in(["COMPLETED", "CANCELLED"]),
            )
        ).first()
        if active_task is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"An active maintenance task already exists for report '{payload.report_id}'. "
                    f"Set allow_duplicate=true with justification to override."
                ),
            )
    else:
        if not payload.duplicate_override_reason:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="duplicate_override_reason is required when allow_duplicate is true.",
            )

    # 3. If assigned_to_user_id is provided, verify user exists
    initial_status = "ASSIGNED" if payload.assigned_to_user_id else "CREATED"
    if payload.assigned_to_user_id:
        assignee = db.execute(
            select(User).where(User.id == payload.assigned_to_user_id)
        ).scalar_one_or_none()
        if assignee is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Assigned user '{payload.assigned_to_user_id}' not found.",
            )

    priority_val = payload.priority.upper()
    if priority_val not in ("LOW", "MEDIUM", "HIGH", "URGENT"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid priority '{payload.priority}'. Must be LOW, MEDIUM, HIGH, or URGENT.",
        )

    task = MaintenanceTask(
        report_id=payload.report_id,
        assigned_to_user_id=payload.assigned_to_user_id,
        created_by_user_id=current_user.id,
        title=payload.title,
        description=payload.description,
        priority=priority_val,
        status=initial_status,
        due_date=payload.due_date,
        follow_up_required=payload.follow_up_required,
        allow_duplicate=payload.allow_duplicate,
        duplicate_override_reason=payload.duplicate_override_reason,
    )
    db.add(task)
    db.flush()

    # 4. Create initial event
    event = MaintenanceTaskEvent(
        task_id=task.id,
        actor_id=current_user.id,
        previous_status=None,
        new_status=initial_status,
        event_type="TASK_CREATED" if initial_status == "CREATED" else "TASK_ASSIGNED",
        notes=payload.description,
    )
    db.add(event)

    if task.assigned_to_user_id:
        create_notification(
            db,
            recipient_id=task.assigned_to_user_id,
            notification_type="MAINTENANCE_TASK_ASSIGNED",
            title="Maintenance Task Assigned",
            message=f"You have been assigned maintenance task '{task.title}'.",
            resource_type="maintenance_task",
            resource_id=task.id,
        )

    db.commit()
    db.refresh(task)
    return task


def assign_maintenance_task(
    db: Session,
    task_id: uuid.UUID,
    payload: MaintenanceTaskAssignRequest,
    current_user: User,
) -> MaintenanceTask:
    """Assign or reassign a maintenance task to a designated maintenance technician."""
    task = db.execute(
        select(MaintenanceTask).where(MaintenanceTask.id == task_id).with_for_update()
    ).scalar_one_or_none()

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance task '{task_id}' not found.",
        )

    if task.status in ("COMPLETED", "CANCELLED"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot assign task in terminal state '{task.status}'.",
        )

    assignee = db.execute(
        select(User).where(User.id == payload.assigned_to_user_id)
    ).scalar_one_or_none()
    if assignee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assigned technician '{payload.assigned_to_user_id}' not found.",
        )

    prev_status = task.status
    task.assigned_to_user_id = payload.assigned_to_user_id
    task.status = "ASSIGNED"

    event = MaintenanceTaskEvent(
        task_id=task.id,
        actor_id=current_user.id,
        previous_status=prev_status,
        new_status="ASSIGNED",
        event_type="TASK_ASSIGNED",
        notes=payload.notes or f"Assigned to user {assignee.id}",
    )
    db.add(event)

    create_notification(
        db,
        recipient_id=task.assigned_to_user_id,
        notification_type="MAINTENANCE_TASK_ASSIGNED",
        title="Maintenance Task Assigned",
        message=f"You have been assigned maintenance task '{task.title}'.",
        resource_type="maintenance_task",
        resource_id=task.id,
    )

    db.commit()
    db.refresh(task)
    return task


def transition_maintenance_task(
    db: Session,
    task_id: uuid.UUID,
    target_status: str,
    event_type: str,
    payload: MaintenanceTaskTransitionRequest | None,
    current_user: User,
    require_assignee_match: bool = False,
) -> MaintenanceTask:
    """Transition a maintenance task to a new lifecycle state under concurrency lock."""
    task = db.execute(
        select(MaintenanceTask).where(MaintenanceTask.id == task_id).with_for_update()
    ).scalar_one_or_none()

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance task '{task_id}' not found.",
        )

    if require_assignee_match and task.assigned_to_user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to update a task assigned to another technician.",
        )

    allowed = VALID_TRANSITIONS.get(task.status, set())
    if target_status not in allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Invalid transition from '{task.status}' to '{target_status}'.",
        )

    prev_status = task.status
    task.status = target_status

    if target_status == "COMPLETED":
        task.completed_at = datetime.now(UTC)

    notes = payload.notes if payload else None
    event = MaintenanceTaskEvent(
        task_id=task.id,
        actor_id=current_user.id,
        previous_status=prev_status,
        new_status=target_status,
        event_type=event_type,
        notes=notes,
    )
    db.add(event)

    # Notify task creator of status progression
    notif_type = (
        "MAINTENANCE_TASK_COMPLETED"
        if target_status == "COMPLETED"
        else "MAINTENANCE_TASK_STATUS_CHANGED"
    )
    create_notification(
        db,
        recipient_id=task.created_by_user_id,
        notification_type=notif_type,
        title=f"Maintenance Task {target_status.replace('_', ' ').title()}",
        message=f"Task '{task.title}' has transitioned to {target_status}.",
        resource_type="maintenance_task",
        resource_id=task.id,
    )

    db.commit()
    db.refresh(task)
    return task


def get_maintenance_task(
    db: Session,
    task_id: uuid.UUID,
    user: User | None = None,
    require_assignee: bool = False,
) -> MaintenanceTask:
    """Retrieve maintenance task details by ID with optional ownership enforcement."""
    task = (
        db.execute(
            select(MaintenanceTask)
            .options(
                joinedload(MaintenanceTask.report),
                joinedload(MaintenanceTask.assigned_to),
                joinedload(MaintenanceTask.created_by),
            )
            .where(MaintenanceTask.id == task_id)
        )
        .scalars()
        .first()
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Maintenance task '{task_id}' not found.",
        )

    if require_assignee and user and task.assigned_to_user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access restricted: task is not assigned to you.",
        )

    return task


def list_maintenance_tasks(
    db: Session,
    assigned_to_id: uuid.UUID | None = None,
    status_filter: str | None = None,
    priority_filter: str | None = None,
    report_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[MaintenanceTask], int]:
    """Query maintenance tasks with filtering, pagination, and deterministic sorting."""
    stmt = select(MaintenanceTask)

    if assigned_to_id is not None:
        stmt = stmt.where(MaintenanceTask.assigned_to_user_id == assigned_to_id)
    if status_filter:
        stmt = stmt.where(MaintenanceTask.status == status_filter.upper())
    if priority_filter:
        stmt = stmt.where(MaintenanceTask.priority == priority_filter.upper())
    if report_id is not None:
        stmt = stmt.where(MaintenanceTask.report_id == report_id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    items = list(
        db.execute(
            stmt.order_by(MaintenanceTask.created_at.desc(), MaintenanceTask.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return items, total


def get_task_history(
    db: Session,
    task_id: uuid.UUID,
) -> list[MaintenanceTaskEvent]:
    """Retrieve complete immutable event history for a maintenance task."""
    # Ensure task exists
    _ = get_maintenance_task(db, task_id)
    stmt = (
        select(MaintenanceTaskEvent)
        .where(MaintenanceTaskEvent.task_id == task_id)
        .order_by(MaintenanceTaskEvent.created_at.asc())
    )
    return list(db.execute(stmt).scalars().all())
