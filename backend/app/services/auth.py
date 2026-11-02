"""Authentication business logic and user management services."""

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.iam import Role, User, UserRole
from app.schemas.auth import UserRegisterRequest


def register_user(db: Session, data: UserRegisterRequest) -> User:
    """Register a new citizen user account transactionally with the standard citizen role.

    Args:
        db: Active SQLAlchemy database session.
        data: Validated registration payload.

    Returns:
        User: Newly created and persisted User model instance.

    Raises:
        HTTPException: 409 if email already exists, 500 if citizen role missing.
    """
    normalized_email = data.email.lower().strip()

    # Pre-check for existing account with case-insensitive email
    existing_user = db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    ).scalar_one_or_none()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        )

    # Retrieve standard citizen role
    citizen_role = db.execute(select(Role).where(Role.name == "citizen")).scalar_one_or_none()
    if citizen_role is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Standard citizen role is not configured in the system.",
        )

    hashed_pw = hash_password(data.password)

    try:
        user = User(
            email=normalized_email,
            hashed_password=hashed_pw,
            full_name=data.full_name.strip(),
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()

        # Automatically bind citizen role
        user_role = UserRole(
            user_id=user.id,
            role_id=citizen_role.id,
            assigned_by=None,
        )
        db.add(user_role)
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email address already exists.",
        ) from None


def authenticate_user(db: Session, email: str, password: str) -> User:
    """Authenticate user credentials against stored Argon2id password hash.

    Args:
        db: Active SQLAlchemy database session.
        email: User email address.
        password: User password candidate.

    Returns:
        User: Authenticated User model instance.

    Raises:
        HTTPException: 401 if credentials are invalid or account is inactive.
    """
    normalized_email = email.lower().strip()

    user = db.execute(
        select(User).where(func.lower(User.email) == normalized_email)
    ).scalar_one_or_none()

    # Generic authentication failure prevents account enumeration
    if user is None or not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user.last_login_at = datetime.now(UTC)
    db.commit()
    db.refresh(user)
    return user
