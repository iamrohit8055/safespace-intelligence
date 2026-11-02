"""Pydantic schemas for SDI scoring configurations, components, and area deficiency scores."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CategoryWeightSchema(BaseModel):
    """Category scoring weight definition."""

    model_config = ConfigDict(from_attributes=True)

    category_id: int = Field(description="Deficiency category identifier")
    category_code: str = Field(description="Unique category code string")
    category_name: str = Field(description="Human-readable category name")
    weight: Decimal = Field(
        description="Assigned relative weight (0.000 to 1.000)",
        decimal_places=4,
    )

    @model_validator(mode="before")
    @classmethod
    def from_orm_obj(cls, data: Any) -> Any:
        """Map attributes from SQLAlchemy ScoringConfigurationWeight entity."""
        if hasattr(data, "category_id"):
            category = getattr(data, "category", None)
            return {
                "category_id": data.category_id,
                "category_code": category.code if category else "",
                "category_name": category.name if category else "",
                "weight": data.weight,
            }
        return data


class ScoringConfigurationResponse(BaseModel):
    """Versioned SDI scoring methodology configuration."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description="Configuration unique primary key")
    version: str = Field(description="Semantic version string (e.g. v1.0.0)")
    name: str = Field(description="Descriptive methodology name")
    description: str | None = Field(default=None, description="Detailed methodology notes")
    is_active: bool = Field(description="Whether this configuration is the active default")
    weights: list[CategoryWeightSchema] = Field(
        default_factory=list,
        description="Assigned category weights",
    )
    methodology_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Algorithm parameters and tuning metadata",
    )
    created_at: datetime = Field(description="Creation timestamp")

    @field_validator("methodology_metadata", mode="before")
    @classmethod
    def parse_metadata(cls, v: Any) -> dict[str, Any]:
        """Ensure methodology_metadata is a dict."""
        if isinstance(v, str):
            import json

            return json.loads(v)
        return v or {}


class ScoreComponentResponse(BaseModel):
    """Individual category contribution to the composite SDI score."""

    model_config = ConfigDict(from_attributes=True)

    category_id: int = Field(description="Category identifier")
    category_code: str = Field(description="Category code string")
    category_name: str = Field(description="Category display name")
    category_score: Decimal | None = Field(
        default=None,
        description="Mean severity deficiency score (20.00 - 100.00), or None if insufficient data",
    )
    assigned_weight: Decimal = Field(
        description="Nominal weight defined in scoring configuration",
    )
    normalized_weight: Decimal | None = Field(
        default=None,
        description="Weight re-normalized over observed categories, or None if unobserved",
    )
    weighted_contribution: Decimal | None = Field(
        default=None,
        description="Product of category_score and normalized_weight",
    )
    report_count: int = Field(
        description="Count of eligible verified reports in this category",
    )
    availability_state: str = Field(
        description="Observation state ('OBSERVED' or 'INSUFFICIENT_DATA')",
    )

    @model_validator(mode="before")
    @classmethod
    def from_orm_obj(cls, data: Any) -> Any:
        """Map attributes from SQLAlchemy ScoreComponent entity."""
        if hasattr(data, "category_id"):
            category = getattr(data, "category", None)
            return {
                "category_id": data.category_id,
                "category_code": category.code if category else "",
                "category_name": category.name if category else "",
                "category_score": data.category_score,
                "assigned_weight": data.assigned_weight,
                "normalized_weight": data.normalized_weight,
                "weighted_contribution": data.weighted_contribution,
                "report_count": data.report_count,
                "availability_state": data.availability_state,
            }
        return data


class AreaScoreResponse(BaseModel):
    """Calculated Safety Deficiency Index (SDI) record for an administrative area."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(description="Unique area score calculation record UUID")
    administrative_area_id: uuid.UUID = Field(description="Evaluated administrative area UUID")
    administrative_area_name: str = Field(description="Name of the administrative area")
    administrative_area_code: str = Field(description="Code of the administrative area")
    configuration_version: str = Field(description="Methodology version used for calculation")
    score: Decimal | None = Field(
        default=None,
        description="Composite SDI deficiency score (0.00 - 100.00), or None if insufficient data",
    )
    completeness_pct: Decimal = Field(
        description="Data completeness percentage based on observed category weights",
    )
    participating_categories_count: int = Field(
        description="Number of categories meeting minimum observation criteria",
    )
    total_categories_count: int = Field(
        description="Total categories defined in the methodology",
    )
    eligible_reports_count: int = Field(
        description="Total verified reports included in calculation",
    )
    is_current: bool = Field(
        description="Flag indicating whether this is the latest active calculation",
    )
    reason: str | None = Field(
        default=None,
        description="Explanation when SDI score cannot be determined (e.g. insufficient data)",
    )
    calculation_timestamp: datetime = Field(
        description="Timestamp when the calculation was executed",
    )
    components: list[ScoreComponentResponse] = Field(
        default_factory=list,
        description="Breakdown of individual category contributions",
    )

    @model_validator(mode="before")
    @classmethod
    def from_orm_obj(cls, data: Any) -> Any:
        """Map attributes from SQLAlchemy AreaScore entity."""
        if hasattr(data, "administrative_area_id"):
            area = getattr(data, "administrative_area", None)
            config = getattr(data, "configuration", None)
            return {
                "id": data.id,
                "administrative_area_id": data.administrative_area_id,
                "administrative_area_name": area.name if area else "",
                "administrative_area_code": area.code if area else "",
                "configuration_version": config.version if config else "",
                "score": data.score,
                "completeness_pct": data.completeness_pct,
                "participating_categories_count": data.participating_categories_count,
                "total_categories_count": data.total_categories_count,
                "eligible_reports_count": data.eligible_reports_count,
                "is_current": data.is_current,
                "reason": data.reason,
                "calculation_timestamp": data.calculation_timestamp,
                "components": data.components if hasattr(data, "components") else [],
            }
        return data
