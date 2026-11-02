"""Pydantic schemas for municipal infrastructure inspection priority scoring."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PriorityConfigurationResponse(BaseModel):
    """Inspection priority scoring model configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Configuration primary key")
    version: str = Field(description="Model methodology version (e.g. v1.0.0)")
    name: str = Field(description="Model configuration name")
    description: str = Field(description="Methodology and weighting description")
    sdi_weight: Decimal = Field(description="Weight assigned to SDI severity")
    urgency_weight: Decimal = Field(description="Weight assigned to observation latency/staleness")
    unresolved_reports_weight: Decimal = Field(
        description="Weight assigned to unresolved report volume"
    )
    confidence_gap_weight: Decimal = Field(
        description="Weight assigned to evidence uncertainty/confidence gap"
    )
    methodology_metadata: dict[str, Any] = Field(
        description="Configuration thresholds, caps, and scale parameters"
    )
    is_active: bool = Field(description="Whether this configuration is active")
    created_at: datetime = Field(description="Configuration creation timestamp")


class AreaPriorityScoreResponse(BaseModel):
    """Calculated infrastructure inspection priority for a municipal administrative area."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Priority score record identifier")
    area_id: uuid.UUID = Field(description="Administrative area identifier")
    configuration_id: int = Field(description="Configuration ID used for calculation")
    configuration_version: str | None = Field(
        default=None, description="Configuration version string"
    )
    priority_score: Decimal | None = Field(
        default=None,
        description="Calculated priority score from 0.00 to 100.00; NULL if INSUFFICIENT_DATA",
    )
    priority_level: str = Field(
        description="Priority category: CRITICAL, HIGH, MEDIUM, LOW, or INSUFFICIENT_DATA"
    )
    sdi_score: Decimal | None = Field(
        default=None, description="Current area SDI (0.00-5.00) considered in calculation"
    )
    confidence_score: Decimal | None = Field(
        default=None, description="Current area evidence confidence (0.0000-1.0000)"
    )
    completeness_pct: Decimal | None = Field(
        default=None, description="Current area confidence completeness percentage"
    )
    unresolved_reports_count: int = Field(
        description="Count of distinct active unresolved deficiency reports"
    )
    latest_observation_at: datetime | None = Field(
        default=None, description="Timestamp of most recent defect observation"
    )
    last_inspected_at: datetime | None = Field(
        default=None, description="Timestamp of most recent inspection or completed repair"
    )
    never_inspected: bool = Field(
        description="Whether this jurisdiction has never had a field inspection"
    )
    calculation_metadata: dict[str, Any] = Field(
        description="Component breakdown and interpretation metadata"
    )
    is_current: bool = Field(description="Whether this score is the active current calculation")
    calculation_timestamp: datetime = Field(description="Timestamp calculation was performed")


class AreaPriorityScoreDetailResponse(AreaPriorityScoreResponse):
    """Detailed area priority response including area jurisdiction metadata."""

    area_name: str | None = Field(default=None, description="Administrative area name")
    area_code: str | None = Field(default=None, description="Administrative area code")
    area_type: str | None = Field(default=None, description="Administrative area hierarchy type")


class AreaPriorityListResponse(BaseModel):
    """Paginated collection of municipal administrative area inspection priorities."""

    items: list[AreaPriorityScoreDetailResponse] = Field(description="List of area priority scores")
    total: int = Field(ge=0, description="Total count matching query filters")
    limit: int = Field(ge=1, description="Page size limit")
    offset: int = Field(ge=0, description="Page offset")
