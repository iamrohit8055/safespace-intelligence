"""Pydantic schemas for evidence confidence configurations, report scores, and area confidence."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator


class ConfidenceConfigurationFactorResponse(BaseModel):
    """Methodology factor definition."""

    model_config = ConfigDict(from_attributes=True)

    factor_code: str
    name: str
    description: str
    weight: Decimal
    is_measurable: bool
    unavailability_reason: str | None


class ConfidenceConfigurationResponse(BaseModel):
    """Versioned confidence methodology configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    version: str
    name: str
    description: str
    is_active: bool
    methodology_metadata: dict[str, Any]
    factors: list[ConfidenceConfigurationFactorResponse]
    created_at: datetime
    updated_at: datetime


class ReportConfidenceComponentResponse(BaseModel):
    """Component evaluation within an individual report confidence assessment."""

    model_config = ConfigDict(from_attributes=True)

    factor_code: str
    factor_score: Decimal | None
    assigned_weight: Decimal
    normalized_weight: Decimal | None
    weighted_contribution: Decimal | None
    availability_state: str
    unavailability_reason: str | None


class ReportConfidenceScoreResponse(BaseModel):
    """Individual report evidence confidence assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    report_id: uuid.UUID
    configuration_id: int
    confidence_score: Decimal | None
    completeness_pct: Decimal
    available_factors_count: int
    total_factors_count: int
    is_current: bool
    factor_details: dict[str, Any]
    calculation_timestamp: datetime
    components: list[ReportConfidenceComponentResponse]


class AreaConfidenceComponentResponse(BaseModel):
    """Category-level evidence confidence contribution within an area score."""

    model_config = ConfigDict(from_attributes=True)

    category_id: int
    category_code: str = ""
    category_name: str = ""
    category_confidence_score: Decimal | None
    report_count: int
    confident_report_count: int
    availability_state: str

    @model_validator(mode="before")
    @classmethod
    def from_orm_obj(cls, data: Any) -> Any:
        """Map attributes from SQLAlchemy AreaConfidenceComponent entity."""
        if hasattr(data, "category_id"):
            category = getattr(data, "category", None)
            return {
                "category_id": data.category_id,
                "category_code": category.code if category else "",
                "category_name": category.name if category else "",
                "category_confidence_score": data.category_confidence_score,
                "report_count": data.report_count,
                "confident_report_count": data.confident_report_count,
                "availability_state": data.availability_state,
            }
        return data


class AreaConfidenceScoreResponse(BaseModel):
    """Area-level evidence confidence and completeness assessment."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    administrative_area_id: uuid.UUID
    configuration_id: int
    area_confidence_score: Decimal | None
    confidence_completeness_pct: Decimal
    total_reports_count: int
    reports_with_confidence_count: int
    reports_without_confidence_count: int
    calculation_timestamp: datetime
    is_current: bool
    methodology_metadata: dict[str, Any]
    components: list[AreaConfidenceComponentResponse]
