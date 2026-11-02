"""Pydantic schemas for municipal infrastructure maintenance management."""

import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MaintenanceTaskCreateRequest(BaseModel):
    """Payload to create a maintenance task from a verified deficiency report."""

    model_config = ConfigDict(extra="forbid")

    report_id: uuid.UUID = Field(description="UUID of verified deficiency report")
    assigned_to_user_id: uuid.UUID | None = Field(
        default=None,
        validation_alias=AliasChoices("assigned_to_user_id", "assigned_to_id"),
        description="Optional UUID of assigned maintenance personnel",
    )
    title: str = Field(min_length=3, max_length=200, description="Task summary")
    description: str = Field(min_length=5, description="Work order instructions and scope")
    priority: str = Field(
        default="MEDIUM",
        description="Priority urgency: LOW, MEDIUM, HIGH, URGENT",
    )
    due_date: datetime | None = Field(default=None, description="Scheduled deadline")
    follow_up_required: bool = Field(
        default=False, description="Whether post-repair re-verification is required"
    )
    allow_duplicate: bool = Field(
        default=False, description="Override flag allowing multiple active tasks on the report"
    )
    duplicate_override_reason: str | None = Field(
        default=None, description="Justification when allow_duplicate is True"
    )


class MaintenanceTaskAssignRequest(BaseModel):
    """Payload for assigning or reassigning a maintenance task."""

    model_config = ConfigDict(extra="forbid")

    assigned_to_user_id: uuid.UUID = Field(
        description="UUID of maintenance user receiving the task"
    )
    notes: str | None = Field(default=None, max_length=1000, description="Assignment instructions")


class MaintenanceTaskTransitionRequest(BaseModel):
    """Payload for lifecycle state changes (start, block, complete, cancel)."""

    model_config = ConfigDict(extra="forbid")

    notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Work notes, blocking reason, or completion summary",
    )


class MaintenanceTaskEventResponse(BaseModel):
    """Audit log entry for maintenance lifecycle transitions."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Event primary key")
    task_id: uuid.UUID = Field(description="Maintenance task UUID")
    actor_id: uuid.UUID = Field(description="User who executed transition")
    previous_status: str | None = Field(description="Status before transition")
    new_status: str = Field(description="Status after transition")
    event_type: str = Field(description="Event action type")
    notes: str | None = Field(description="Transition notes")
    created_at: datetime = Field(description="Timestamp of event")


class MaintenanceTaskResponse(BaseModel):
    """Public representation of an infrastructure maintenance task."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique task identifier")
    report_id: uuid.UUID = Field(description="Associated deficiency report identifier")
    assigned_to_user_id: uuid.UUID | None = Field(
        description="Assigned maintenance user identifier"
    )
    created_by_user_id: uuid.UUID = Field(description="Administrator who created task")
    title: str = Field(description="Task title")
    description: str = Field(description="Work order description")
    priority: str = Field(description="Priority: LOW, MEDIUM, HIGH, URGENT")
    status: str = Field(description="Current task lifecycle status")
    due_date: datetime | None = Field(description="Task due date")
    completed_at: datetime | None = Field(description="Completion timestamp")
    follow_up_required: bool = Field(description="Whether follow-up inspection is needed")
    allow_duplicate: bool = Field(description="Whether multiple active tasks were allowed")
    duplicate_override_reason: str | None = Field(description="Duplicate justification")
    created_at: datetime = Field(description="Creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")


class MaintenanceTaskListResponse(BaseModel):
    """Paginated collection of maintenance tasks."""

    items: list[MaintenanceTaskResponse] = Field(description="List of tasks")
    total: int = Field(ge=0, description="Total matching query")
    limit: int = Field(ge=1, description="Page limit")
    offset: int = Field(ge=0, description="Page offset")
