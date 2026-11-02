"""In-app notifications API router for authenticated citizens, technicians, and moderators."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database.session import get_db
from app.models.iam import User
from app.schemas.notifications import (
    NotificationListResponse,
    NotificationResponse,
    UnreadCountResponse,
)
from app.services.notifications import (
    get_user_unread_count,
    list_user_notifications,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)

notifications_router = APIRouter()


@notifications_router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
    summary="List authenticated user notifications",
    description="Returns paginated notifications belonging to the current authenticated user.",
)
def get_my_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    unread_only: Annotated[bool, Query(description="Filter to unread notifications only")] = False,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> NotificationListResponse:
    """List notifications for current user."""
    items, total, unread_count = list_user_notifications(
        db,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )
    return NotificationListResponse(
        items=[NotificationResponse.model_validate(n) for n in items],
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
    )


@notifications_router.get(
    "/unread-count",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get unread notification count",
    description="Returns the total count of unread notifications for the calling user.",
)
def get_unread_count_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UnreadCountResponse:
    """Get unread notification count."""
    count = get_user_unread_count(db, current_user.id)
    return UnreadCountResponse(unread_count=count)


@notifications_router.post(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark single notification as read",
    description="Marks a specific notification as read. Returns 404 if not found.",
)
def mark_read_endpoint(
    notification_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> NotificationResponse:
    """Mark single notification as read."""
    notif = mark_notification_as_read(db, notification_id, current_user.id)
    return NotificationResponse.model_validate(notif)


@notifications_router.post(
    "/read-all",
    response_model=UnreadCountResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark all notifications as read",
    description="Marks all unread notifications for the calling user as read.",
)
def mark_all_read_endpoint(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UnreadCountResponse:
    """Mark all notifications as read."""
    _ = mark_all_notifications_as_read(db, current_user.id)
    return UnreadCountResponse(unread_count=0)
