"""Pydantic schemas for report submission, retrieval, and pagination."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.geometry import parse_point_geometry
from app.schemas.media import ReportMediaResponse


class ReportCategoryDetail(BaseModel):
    """Full taxonomy category definition."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key identifier")
    code: str = Field(description="Unique classification code")
    name: str = Field(description="Human-readable category name")
    description: str = Field(description="Category description")
    is_active: bool = Field(description="Whether the category currently accepts reports")


class PublicReportMapItem(BaseModel):
    """Privacy-preserving report item for public exploration map."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique report identifier")
    title: str = Field(description="Deficiency title")
    description: str = Field(description="Deficiency description")
    category_id: int = Field(description="Category taxonomy ID")
    category_code: str = Field(description="Category code")
    category_name: str = Field(description="Category human name")
    status: str = Field(description="Moderation status")
    latitude: float = Field(description="Safe privacy-rounded latitude (3 decimal places, ~100m)")
    longitude: float = Field(description="Safe privacy-rounded longitude (3 decimal places, ~100m)")
    observed_at: datetime = Field(description="Observation timestamp")
    submitted_at: datetime = Field(description="Submission timestamp")
    administrative_area_name: str | None = Field(
        default=None, description="Assigned jurisdiction name"
    )
    has_media: bool = Field(default=False, description="Whether photographic evidence is attached")


class ReportCategorySummary(BaseModel):
    """Concise representation of deficiency taxonomy classification."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Primary key identifier for the deficiency category")
    code: str = Field(description="Taxonomy classification code")
    name: str = Field(description="Human-readable category name")


class AdministrativeAreaSummary(BaseModel):
    """Concise representation of assigned municipal jurisdiction."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique jurisdiction identifier")
    name: str = Field(description="Municipal area name")
    code: str = Field(description="Unique area boundary code")
    area_type: str = Field(description="Jurisdiction hierarchy level (e.g. ward, district)")


class ReportCreateRequest(BaseModel):
    """Input payload for citizen infrastructure deficiency submission."""

    model_config = ConfigDict(extra="forbid")

    category_id: int | None = Field(
        default=None,
        ge=1,
        le=32767,
        description="Numeric category ID (either category_id or category_code required)",
    )
    category_code: str | None = Field(
        default=None,
        max_length=50,
        description="Taxonomy code of the category (e.g. STREET_LIGHTING)",
    )
    title: str = Field(
        ...,
        min_length=3,
        max_length=150,
        description="Concise title describing the infrastructure deficiency",
    )
    description: str = Field(
        ...,
        min_length=5,
        max_length=5000,
        description="Detailed description of the observed deficiency",
    )
    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="WGS 84 latitude coordinate in degrees [-90.0, 90.0]",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="WGS 84 longitude coordinate in degrees [-180.0, 180.0]",
    )
    address_text: str | None = Field(
        default=None,
        max_length=255,
        description="Optional human-readable street address or landmark description",
    )
    observed_at: datetime | None = Field(
        default=None,
        description="Timestamp when the defect was observed; defaults to submission time",
    )

    @field_validator("observed_at")
    @classmethod
    def validate_observed_at_not_in_future(cls, v: datetime | None) -> datetime | None:
        """Reject future observation timestamps."""
        if v is not None:
            now = datetime.now(UTC)
            v_utc = v if v.tzinfo is not None else v.replace(tzinfo=UTC)
            if v_utc > now + timedelta(seconds=5):
                raise ValueError("Observation timestamp cannot be in the future.")
        return v

    @model_validator(mode="after")
    def validate_category_identifier(self) -> "ReportCreateRequest":
        """Verify that at least one category identifier was supplied."""
        if self.category_id is None and not self.category_code:
            raise ValueError("Either 'category_id' or 'category_code' must be provided.")
        return self


class ReportResponse(BaseModel):
    """Sanitized public-facing report representation for citizen interfaces."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique report identifier")
    reporter_id: uuid.UUID = Field(description="Citizen reporter UUID")
    category: ReportCategorySummary = Field(description="Deficiency classification category")
    administrative_area: AdministrativeAreaSummary | None = Field(
        default=None,
        description="Assigned municipal jurisdiction, if resolved via PostGIS ST_Covers",
    )
    title: str = Field(description="Deficiency title")
    description: str = Field(description="Deficiency description")
    latitude: float = Field(description="WGS 84 latitude coordinate")
    longitude: float = Field(description="WGS 84 longitude coordinate")
    address_text: str | None = Field(default=None, description="Street address description")
    status: str = Field(description="Current lifecycle status")
    observed_at: datetime = Field(description="Observation timestamp")
    submitted_at: datetime = Field(description="Submission timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    media: list[ReportMediaResponse] = Field(
        default_factory=list, description="Attached photographic evidence"
    )

    @model_validator(mode="before")
    @classmethod
    def populate_coordinates_from_location(cls, data: Any) -> Any:
        """Extract latitude and longitude coordinates from PostGIS geometry before validation."""
        if isinstance(data, dict):
            return data
        if hasattr(data, "location"):
            lon, lat = parse_point_geometry(data.location)
            media_list = getattr(data, "media", []) or []
            return {
                "id": data.id,
                "reporter_id": data.reporter_id,
                "category": data.category,
                "administrative_area": data.administrative_area,
                "title": data.title,
                "description": data.description,
                "latitude": lat,
                "longitude": lon,
                "address_text": data.address_text,
                "status": data.status,
                "observed_at": data.observed_at,
                "submitted_at": data.submitted_at,
                "updated_at": data.updated_at,
                "media": media_list,
            }
        return data


class ReportListResponse(BaseModel):
    """Paginated collection of citizen reports."""

    items: list[ReportResponse] = Field(description="List of reports on the current page")
    total: int = Field(ge=0, description="Total count of reports matching the filter")
    limit: int = Field(ge=1, description="Requested page size limit")
    offset: int = Field(ge=0, description="Requested pagination offset")
