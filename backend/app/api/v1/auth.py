"""Authentication and identity router endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token
from app.database.session import get_db
from app.models.iam import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth import authenticate_user, register_user

auth_router = APIRouter()


@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new citizen account",
    description="Registers a new citizen user account and automatically assigns the citizen role.",
)
def register(
    payload: UserRegisterRequest,
    db: Annotated[Session, Depends(get_db)],
) -> UserResponse:
    """Register a new citizen user account.

    The citizen role is assigned automatically; caller privileges cannot be elevated.
    """
    user = register_user(db, payload)
    return UserResponse.model_validate(user)


@auth_router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user credentials",
    description=(
        "Validates email and password credentials, returning a signed HS256 JWT access token."
    ),
)
def login(
    payload: UserLoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    """Authenticate with email and password to receive an access token."""
    user = authenticate_user(db, payload.email, payload.password)
    access_token = create_access_token(subject=user.id)
    return TokenResponse(access_token=access_token, token_type="bearer")


@auth_router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user",
    description="Returns public profile and assigned roles for the currently authenticated user.",
)
def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Retrieve identity and assigned roles for the current bearer token."""
    return UserResponse.model_validate(current_user)
