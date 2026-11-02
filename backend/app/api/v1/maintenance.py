"""Maintenance personnel API endpoints for assigned work order lifecycle management."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.iam import User
from app.schemas.maintenance import (
    MaintenanceTaskListResponse,
    MaintenanceTaskResponse,
    MaintenanceTaskTransitionRequest,
)
from app.services.maintenance import (
    list_maintenance_tasks,
    transition_maintenance_task,
)

maintenance_router = APIRouter()
maintenance_only = require_roles("maintenance")


@maintenance_router.get(
    "/tasks/my",
    response_model=MaintenanceTaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List assigned maintenance tasks for current technician",
    description="Returns a paginated list of tasks assigned to the authenticated technician.",
)
def get_my_tasks(
    current_user: Annotated[User, Depends(maintenance_only)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by status")
    ] = None,
    priority_filter: Annotated[
        str | None, Query(alias="priority", description="Filter by priority")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> MaintenanceTaskListResponse:
    """List tasks assigned to the current technician."""
    items, total = list_maintenance_tasks(
        db,
        assigned_to_id=current_user.id,
        status_filter=status_filter,
        priority_filter=priority_filter,
        limit=limit,
        offset=offset,
    )
    return MaintenanceTaskListResponse(
        items=[MaintenanceTaskResponse.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@maintenance_router.post(
    "/tasks/{task_id}/accept",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Accept an assigned maintenance task",
    description="Transitions an ASSIGNED task to ACCEPTED status.",
)
def accept_task_endpoint(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(maintenance_only)],
    db: Annotated[Session, Depends(get_db)],
    payload: MaintenanceTaskTransitionRequest | None = None,
) -> MaintenanceTaskResponse:
    """Accept assigned maintenance task."""
    task = transition_maintenance_task(
        db,
        task_id,
        target_status="ACCEPTED",
        event_type="TASK_ACCEPTED",
        payload=payload,
        current_user=current_user,
        require_assignee_match=True,
    )
    return MaintenanceTaskResponse.model_validate(task)


@maintenance_router.post(
    "/tasks/{task_id}/start",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Start work on a maintenance task",
    description="Transitions an ACCEPTED or BLOCKED task to IN_PROGRESS status.",
)
def start_task_endpoint(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(maintenance_only)],
    db: Annotated[Session, Depends(get_db)],
    payload: MaintenanceTaskTransitionRequest | None = None,
) -> MaintenanceTaskResponse:
    """Start work on maintenance task."""
    task = transition_maintenance_task(
        db,
        task_id,
        target_status="IN_PROGRESS",
        event_type="TASK_STARTED",
        payload=payload,
        current_user=current_user,
        require_assignee_match=True,
    )
    return MaintenanceTaskResponse.model_validate(task)


@maintenance_router.post(
    "/tasks/{task_id}/block",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Block a maintenance task due to impediments",
    description="Transitions an ACCEPTED or IN_PROGRESS task to BLOCKED status.",
)
def block_task_endpoint(
    task_id: uuid.UUID,
    payload: MaintenanceTaskTransitionRequest,
    current_user: Annotated[User, Depends(maintenance_only)],
    db: Annotated[Session, Depends(get_db)],
) -> MaintenanceTaskResponse:
    """Block maintenance task."""
    task = transition_maintenance_task(
        db,
        task_id,
        target_status="BLOCKED",
        event_type="TASK_BLOCKED",
        payload=payload,
        current_user=current_user,
        require_assignee_match=True,
    )
    return MaintenanceTaskResponse.model_validate(task)


@maintenance_router.post(
    "/tasks/{task_id}/complete",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete a maintenance repair task",
    description="Transitions an IN_PROGRESS task to COMPLETED status and records timestamp.",
)
def complete_task_endpoint(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(maintenance_only)],
    db: Annotated[Session, Depends(get_db)],
    payload: MaintenanceTaskTransitionRequest | None = None,
) -> MaintenanceTaskResponse:
    """Complete maintenance task."""
    task = transition_maintenance_task(
        db,
        task_id,
        target_status="COMPLETED",
        event_type="TASK_COMPLETED",
        payload=payload,
        current_user=current_user,
        require_assignee_match=True,
    )
    return MaintenanceTaskResponse.model_validate(task)
