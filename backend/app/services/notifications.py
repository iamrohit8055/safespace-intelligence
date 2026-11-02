"""Service layer implementing transactional in-app notifications and read management."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notifications import Notification


def create_notification(
    db: Session,
    recipient_id: uuid.UUID,
    notification_type: str,
    title: str,
    message: str,
    resource_type: str | None = None,
    resource_id: uuid.UUID | None = None,
) -> Notification:
    """Create a new in-app notification transactionally, deduplicating unread alerts."""
    # Check for duplicate unread alert within same resource and notification type
    if resource_id is not None:
        duplicate = (
            db.execute(
                select(Notification).where(
                    Notification.recipient_id == recipient_id,
                    Notification.notification_type == notification_type,
                    Notification.resource_id == resource_id,
                    Notification.is_read.is_(False),
                )
            )
            .scalars()
            .first()
        )
        if duplicate is not None:
            return duplicate

    notif = Notification(
        recipient_id=recipient_id,
        notification_type=notification_type,
        title=title,
        message=message,
        resource_type=resource_type,
        resource_id=resource_id,
        is_read=False,
    )
    db.add(notif)
    return notif


def list_user_notifications(
    db: Session,
    user_id: uuid.UUID,
    unread_only: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[Notification], int, int]:
    """Retrieve paginated notifications for the calling user with total and unread counts."""
    base_stmt = select(Notification).where(Notification.recipient_id == user_id)
    if unread_only:
        base_stmt = base_stmt.where(Notification.is_read.is_(False))

    total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()

    # Total unread count regardless of pagination/filter
    unread_stmt = select(func.count(Notification.id)).where(
        Notification.recipient_id == user_id,
        Notification.is_read.is_(False),
    )
    unread_count = db.execute(unread_stmt).scalar_one()

    items = list(
        db.execute(
            base_stmt.order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return items, total, unread_count


def get_user_unread_count(
    db: Session,
    user_id: uuid.UUID,
) -> int:
    """Get the count of unread notifications for a user."""
    stmt = select(func.count(Notification.id)).where(
        Notification.recipient_id == user_id,
        Notification.is_read.is_(False),
    )
    return db.execute(stmt).scalar_one()


def mark_notification_as_read(
    db: Session,
    notification_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Notification:
    """Mark a single notification as read if it belongs to the authenticated user."""
    notif = db.execute(
        select(Notification).where(Notification.id == notification_id)
    ).scalar_one_or_none()

    if notif is None or notif.recipient_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Notification '{notification_id}' not found.",
        )

    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notif)

    return notif


def mark_all_notifications_as_read(
    db: Session,
    user_id: uuid.UUID,
) -> int:
    """Mark all unread notifications for a user as read."""
    now = datetime.now(UTC)
    result = db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user_id,
            Notification.is_read.is_(False),
        )
        .values(is_read=True, read_at=now)
    )
    db.commit()
    return result.rowcount
