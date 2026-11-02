"""Pydantic schemas for report verification, rejection, reopening, and audit history."""

import uuid
from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class VerifyReportRequest(BaseModel):
    """Payload for approving and verifying a report with severity scoring."""

    model_config = ConfigDict(extra="forbid")

    verified_severity: int = Field(
        ...,
        ge=1,
        le=5,
        validation_alias=AliasChoices("verified_severity", "severity"),
        description="Physical deficiency severity level on a scale from 1 (minor) to 5 (critical)",
    )
    verification_notes: str | None = Field(
        default=None,
        max_length=2000,
        validation_alias=AliasChoices("verification_notes", "notes"),
        description="Optional detailed inspection notes or field assessment observations",
    )


class RejectReportRequest(BaseModel):
    """Payload for rejecting an invalid or unverified report."""

    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Mandatory categorical reason for rejection (e.g. INSUFFICIENT_EVIDENCE)",
    )
    verification_notes: str | None = Field(
        default=None,
        max_length=2000,
        validation_alias=AliasChoices("verification_notes", "notes"),
        description="Optional additional context explaining the rejection decision",
    )

    @field_validator("rejection_reason")
    @classmethod
    def validate_non_empty_reason(cls, value: str) -> str:
        """Ensure rejection reason is not empty or composed solely of whitespace."""
        clean = value.strip()
        if not clean:
            raise ValueError("Rejection reason cannot be empty or whitespace only.")
        return clean


class ReopenReportRequest(BaseModel):
    """Payload for reopening a verified or rejected report back to moderation."""

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Mandatory justification for reopening the report verification process",
    )

    @field_validator("reason")
    @classmethod
    def validate_non_empty_reopening_reason(cls, value: str) -> str:
        """Ensure reopening reason is not empty or composed solely of whitespace."""
        clean = value.strip()
        if not clean:
            raise ValueError("Reopening reason cannot be empty or whitespace only.")
        return clean


class VerificationHistoryResponse(BaseModel):
    """Chronological verification record entry for auditing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique verification record identifier")
    report_id: uuid.UUID = Field(description="Associated report UUID")
    decision: str = Field(description="Moderation outcome (e.g. VERIFIED, REJECTED)")
    rejection_reason: str | None = Field(
        default=None,
        description="Categorical reason if rejected",
    )
    verification_notes: str | None = Field(
        default=None,
        description="Verifier assessment notes",
    )
    verified_severity: int | None = Field(
        default=None,
        description="Assigned physical deficiency severity (1-5) if verified",
    )
    verified_at: datetime = Field(description="Timestamp when the decision was recorded")
