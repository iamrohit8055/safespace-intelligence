"""Pydantic schemas for authentication and identity endpoints."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    """Schema for public citizen user registration."""

    email: EmailStr = Field(
        ...,
        description="User email address (normalized to lowercase).",
        max_length=255,
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="User password (minimum 8 characters, maximum 128 characters).",
    )
    full_name: str = Field(
        ...,
        min_length=1,
        max_length=150,
        description="Full legal or preferred name of the user.",
    )


class UserLoginRequest(BaseModel):
    """Schema for user credentials authentication."""

    email: EmailStr = Field(..., description="Registered user email address.")
    password: str = Field(..., min_length=1, max_length=128, description="User password.")


class TokenResponse(BaseModel):
    """Schema for JWT access token response."""

    access_token: str = Field(..., description="Signed HS256 JWT access token.")
    token_type: str = Field(default="bearer", description="Token authentication scheme.")


class UserResponse(BaseModel):
    """Schema for public/safe user account representation."""

    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    is_verified: bool
    roles: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("roles", mode="before")
    @classmethod
    def extract_role_names(cls, value: object) -> list[str]:
        """Extract role name strings from Role model instances or string list."""
        if isinstance(value, list):
            return [getattr(item, "name", str(item)) for item in value]
        return []
