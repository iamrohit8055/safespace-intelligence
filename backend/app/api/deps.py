"""FastAPI dependency injection utilities for authentication and authorization."""

import uuid
from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database.session import get_db
from app.models.iam import User

# HTTP Bearer scheme
bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Resolve and validate the authenticated user from the incoming JWT Bearer token.

    Args:
        credentials: Extracted HTTP Bearer credentials.
        db: Active SQLAlchemy database session.

    Returns:
        User: Currently authenticated active User model instance.

    Raises:
        HTTPException: 401 if token is missing, expired, invalid, or user is inactive/not found.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    subject: str | None = payload.get("sub")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: missing subject claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(subject)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token: subject must be a valid UUID.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with this token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(*allowed_roles: str) -> Callable[[User], User]:
    """Factory creating an authorization dependency requiring one or more specific roles.

    Args:
        *allowed_roles: Names of roles permitted to access the protected endpoint.

    Returns:
        Callable[[User], User]: Dependency checking role membership and returning the user.
    """

    def role_checker(
        current_user: Annotated[User, Depends(get_current_user)],
    ) -> User:
        user_roles = {r.name for r in current_user.roles}
        if not user_roles.intersection(allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access forbidden: You do not possess the required role permissions.",
            )
        return current_user

    return role_checker
