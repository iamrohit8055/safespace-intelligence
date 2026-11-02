"""Pydantic schemas for duplicate candidate detection, moderation, and canonical linking."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class DuplicateDetectionConfigResponse(BaseModel):
    """Configuration for spatial and temporal proximity candidate detection."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    name: str
    description: str
    spatial_radius_metres: Decimal
    time_window_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DuplicateCandidateResponse(BaseModel):
    """Duplicate candidate pair record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    first_report_id: uuid.UUID
    second_report_id: uuid.UUID
    distance_metres: Decimal
    time_difference_seconds: int
    rule_version: str
    review_status: str
    reviewer_id: uuid.UUID | None
    reviewed_at: datetime | None
    review_reason: str | None
    detected_at: datetime


class DuplicateCandidateListResponse(BaseModel):
    """Paginated list of duplicate candidate pairs."""

    items: list[DuplicateCandidateResponse]
    total: int
    limit: int
    offset: int


class DetectDuplicatesRequest(BaseModel):
    """Request payload for triggering duplicate candidate detection."""

    administrative_area_id: uuid.UUID | None = Field(
        default=None,
        description="Optional administrative area ID to scope batch detection.",
    )
    configuration_version: str | None = Field(
        default=None,
        description="Optional explicit methodology version (e.g. 'v1.0.0').",
    )


class DetectDuplicatesResponse(BaseModel):
    """Summary result of candidate detection execution."""

    candidates_evaluated: int
    new_candidates_created: int
    configuration_version: str
    administrative_area_id: uuid.UUID | None


class DuplicateReviewRequest(BaseModel):
    """Request payload for reviewing a candidate pair and establishing duplicate relationships."""

    decision: str = Field(
        ...,
        description="Review decision: CONFIRMED_DUPLICATE, NOT_DUPLICATE, or NEEDS_REVIEW.",
    )
    reason: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Justification for the review decision.",
    )
    canonical_report_id: uuid.UUID | None = Field(
        default=None,
        description=(
            "Optional explicit canonical report ID if CONFIRMED_DUPLICATE. "
            "If omitted, the earliest valid submitted report is selected deterministically."
        ),
    )


class DuplicateReviewHistoryResponse(BaseModel):
    """Audit ledger entry of a duplicate review decision."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    candidate_id: uuid.UUID | None
    duplicate_report_id: uuid.UUID
    canonical_report_id: uuid.UUID
    decision: str
    reason: str
    reviewer_id: uuid.UUID
    reviewed_at: datetime
