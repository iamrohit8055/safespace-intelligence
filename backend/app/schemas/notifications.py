"""Pydantic schemas for in-app notifications and alert delivery."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    """Public representation of an in-app notification."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Notification UUID")
    recipient_id: uuid.UUID = Field(description="Recipient user UUID")
    notification_type: str = Field(description="Event classification type")
    title: str = Field(description="Alert headline")
    message: str = Field(description="Notification message content")
    resource_type: str | None = Field(default=None, description="Resource model name")
    resource_id: uuid.UUID | None = Field(default=None, description="Resource model UUID")
    is_read: bool = Field(description="Whether the notification has been marked read")
    read_at: datetime | None = Field(default=None, description="Read timestamp")
    created_at: datetime = Field(description="Creation timestamp")


class NotificationListResponse(BaseModel):
    """Paginated collection of notifications."""

    items: list[NotificationResponse] = Field(description="List of notifications")
    total: int = Field(ge=0, description="Total matching notifications")
    unread_count: int = Field(ge=0, description="Unread notifications count")
    limit: int = Field(ge=1, description="Page limit")
    offset: int = Field(ge=0, description="Page offset")


class UnreadCountResponse(BaseModel):
    """Unread notifications summary count."""

    unread_count: int = Field(ge=0, description="Total unread notifications for calling user")
