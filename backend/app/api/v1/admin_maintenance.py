"""Administrative API endpoints for creating, assigning, and monitoring maintenance tasks."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.iam import Role, User
from app.schemas.maintenance import (
    MaintenanceTaskAssignRequest,
    MaintenanceTaskCreateRequest,
    MaintenanceTaskEventResponse,
    MaintenanceTaskListResponse,
    MaintenanceTaskResponse,
    MaintenanceTaskTransitionRequest,
)
from app.services.maintenance import (
    assign_maintenance_task,
    create_maintenance_task,
    get_maintenance_task,
    get_task_history,
    list_maintenance_tasks,
    transition_maintenance_task,
)

admin_maintenance_router = APIRouter()
admin_only = require_roles("admin")
admin_or_verifier = require_roles("admin", "verifier")


@admin_maintenance_router.get(
    "/technicians",
    status_code=status.HTTP_200_OK,
    summary="List available maintenance technicians",
    description="Returns users assigned the maintenance role for work order task assignment.",
)
def list_technicians_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict[str, Any]]:
    """List all active technician accounts."""
    stmt = (
        select(User)
        .join(User.roles)
        .where(Role.name == "maintenance", User.is_active.is_(True))
        .order_by(User.full_name.asc())
    )
    users = db.execute(stmt).scalars().unique().all()
    return [{"id": str(u.id), "email": u.email, "full_name": u.full_name} for u in users]


@admin_maintenance_router.post(
    "/tasks",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance task for verified report",
    description="Creates a work order repair task associated with a verified deficiency report.",
)
def create_task_endpoint(
    payload: MaintenanceTaskCreateRequest,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> MaintenanceTaskResponse:
    """Create a new maintenance task."""
    task = create_maintenance_task(db, payload, current_user)
    return MaintenanceTaskResponse.model_validate(task)


@admin_maintenance_router.get(
    "/tasks",
    response_model=MaintenanceTaskListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all maintenance tasks with filtering",
    description="Returns a paginated list of maintenance tasks with optional filters.",
)
def list_tasks_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by status")
    ] = None,
    priority_filter: Annotated[
        str | None, Query(alias="priority", description="Filter by priority")
    ] = None,
    assigned_to_id: Annotated[
        uuid.UUID | None, Query(description="Filter by technician ID")
    ] = None,
    report_id: Annotated[uuid.UUID | None, Query(description="Filter by report UUID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> MaintenanceTaskListResponse:
    """List maintenance tasks."""
    items, total = list_maintenance_tasks(
        db,
        assigned_to_id=assigned_to_id,
        status_filter=status_filter,
        priority_filter=priority_filter,
        report_id=report_id,
        limit=limit,
        offset=offset,
    )
    return MaintenanceTaskListResponse(
        items=[MaintenanceTaskResponse.model_validate(t) for t in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_maintenance_router.get(
    "/tasks/{task_id}",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Get maintenance task details",
    description="Retrieves full details of a specific maintenance task.",
)
def get_task_endpoint(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
) -> MaintenanceTaskResponse:
    """Get task details."""
    task = get_maintenance_task(db, task_id)
    return MaintenanceTaskResponse.model_validate(task)


@admin_maintenance_router.post(
    "/tasks/{task_id}/assign",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Assign maintenance task to technician",
    description="Assigns or reassigns a maintenance task to a designated technician.",
)
def assign_task_endpoint(
    task_id: uuid.UUID,
    payload: MaintenanceTaskAssignRequest,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> MaintenanceTaskResponse:
    """Assign maintenance task."""
    task = assign_maintenance_task(db, task_id, payload, current_user)
    return MaintenanceTaskResponse.model_validate(task)


@admin_maintenance_router.post(
    "/tasks/{task_id}/cancel",
    response_model=MaintenanceTaskResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel maintenance task",
    description="Cancels an active maintenance task with an administrative reason.",
)
def cancel_task_endpoint(
    task_id: uuid.UUID,
    payload: MaintenanceTaskTransitionRequest,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> MaintenanceTaskResponse:
    """Cancel maintenance task."""
    task = transition_maintenance_task(
        db,
        task_id,
        target_status="CANCELLED",
        event_type="TASK_CANCELLED",
        payload=payload,
        current_user=current_user,
    )
    return MaintenanceTaskResponse.model_validate(task)


@admin_maintenance_router.get(
    "/tasks/{task_id}/history",
    response_model=list[MaintenanceTaskEventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get maintenance task audit event history",
    description="Retrieves chronological immutable audit log for a maintenance task.",
)
def get_task_history_endpoint(
    task_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
) -> list[MaintenanceTaskEventResponse]:
    """Get task audit events."""
    events = get_task_history(db, task_id)
    return [MaintenanceTaskEventResponse.model_validate(e) for e in events]
