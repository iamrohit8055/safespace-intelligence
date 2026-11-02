"""Pydantic schemas for administrative data analytics and reporting dashboards."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class StatusCount(BaseModel):
    """Aggregate count grouped by status."""

    status: str = Field(description="Lifecycle status identifier")
    count: int = Field(ge=0, description="Count of records in status")


class CategoryCount(BaseModel):
    """Aggregate count grouped by deficiency category."""

    category_id: int = Field(description="Category taxonomy identifier")
    category_code: str = Field(description="Category taxonomy code")
    category_name: str = Field(description="Category human-readable name")
    count: int = Field(ge=0, description="Total reports in category")


class AreaReportCount(BaseModel):
    """Aggregate count grouped by administrative area."""

    area_id: uuid.UUID = Field(description="Administrative area UUID")
    area_name: str = Field(description="Administrative area name")
    area_code: str = Field(description="Administrative area code")
    area_type: str = Field(description="Jurisdiction hierarchy level")
    count: int = Field(ge=0, description="Total reports in area")


class TimeSeriesPoint(BaseModel):
    """Temporal aggregate count data point."""

    date: str = Field(description="Bucket date (YYYY-MM-DD)")
    count: int = Field(ge=0, description="Event count on date")


class ReportAnalyticsResponse(BaseModel):
    """Aggregated infrastructure report metrics."""

    total_reports: int = Field(ge=0, description="Total reports matching filter")
    by_status: list[StatusCount] = Field(description="Breakdown by status")
    by_category: list[CategoryCount] = Field(description="Breakdown by taxonomy category")
    by_area: list[AreaReportCount] = Field(description="Breakdown by administrative area")
    submitted_over_time: list[TimeSeriesPoint] = Field(
        description="Submission frequency time-series"
    )
    verified_count: int = Field(ge=0, description="Total verified reports")
    rejected_count: int = Field(ge=0, description="Total rejected reports")
    duplicate_count: int = Field(ge=0, description="Total confirmed duplicate reports")
    pending_backlog_count: int = Field(
        ge=0, description="Total reports awaiting verification (SUBMITTED + UNDER_VERIFICATION)"
    )


class SdiRangeDistribution(BaseModel):
    """Count of areas grouped by SDI deficiency severity bracket."""

    negligible: int = Field(ge=0, description="Areas with SDI in [0.0, 1.0)")
    low: int = Field(ge=0, description="Areas with SDI in [1.0, 2.0)")
    moderate: int = Field(ge=0, description="Areas with SDI in [2.0, 3.0)")
    high: int = Field(ge=0, description="Areas with SDI in [3.0, 4.0)")
    severe: int = Field(ge=0, description="Areas with SDI in [4.0, 5.0]")
    insufficient_data: int = Field(ge=0, description="Areas without calculated SDI")


class AreaSdiItem(BaseModel):
    """Current SDI score for an administrative area."""

    area_id: uuid.UUID = Field(description="Administrative area UUID")
    area_name: str = Field(description="Area name")
    area_code: str = Field(description="Area code")
    sdi_score: Decimal | None = Field(default=None, description="SDI score (0.00-5.00)")
    completeness_pct: Decimal | None = Field(default=None, description="Confidence completeness")
    calculation_timestamp: datetime | None = Field(
        default=None, description="Calculation timestamp"
    )


class SdiAnalyticsResponse(BaseModel):
    """Aggregated Safety Deficiency Index (SDI) metrics."""

    total_areas_evaluated: int = Field(ge=0, description="Total areas inspected or scored")
    range_distribution: SdiRangeDistribution = Field(description="Areas grouped by severity tier")
    areas: list[AreaSdiItem] = Field(description="List of area SDI summaries")
    insufficient_data_areas_count: int = Field(
        ge=0, description="Areas with zero or incomplete data"
    )


class ConfidenceAnalyticsResponse(BaseModel):
    """Aggregated evidence confidence metrics."""

    evaluated_areas_count: int = Field(ge=0, description="Areas with confidence calculated")
    average_area_confidence: Decimal | None = Field(
        default=None, description="Average confidence score across evaluated areas"
    )
    average_completeness_pct: Decimal | None = Field(
        default=None, description="Average evidence completeness across evaluated areas"
    )
    category_sample_counts: list[CategoryCount] = Field(
        description="Total confident report samples per category"
    )
    low_evidence_areas_count: int = Field(
        ge=0, description="Areas with confidence < 0.40 or completeness < 50%"
    )


class MaintenanceUserTaskCount(BaseModel):
    """Task count assigned to a technician."""

    user_id: uuid.UUID = Field(description="Technician user ID")
    user_name: str = Field(description="Technician name")
    assigned_count: int = Field(ge=0, description="Total assigned tasks")
    completed_count: int = Field(ge=0, description="Completed tasks")


class MaintenanceAnalyticsResponse(BaseModel):
    """Aggregated infrastructure repair maintenance task metrics."""

    total_tasks: int = Field(ge=0, description="Total maintenance tasks")
    by_status: list[StatusCount] = Field(description="Tasks breakdown by status")
    by_priority: list[StatusCount] = Field(description="Tasks breakdown by priority")
    average_completion_time_hours: Decimal | None = Field(
        default=None, description="Average turnaround time from creation to completion"
    )
    overdue_tasks_count: int = Field(ge=0, description="Tasks past due_date not yet completed")
    by_technician: list[MaintenanceUserTaskCount] = Field(description="Tasks by technician")


class AnalyticsOverviewResponse(BaseModel):
    """High-level executive dashboard summary."""

    total_reports: int = Field(ge=0, description="Total citizen reports")
    pending_verification: int = Field(ge=0, description="Backlog awaiting inspection")
    verified_reports: int = Field(ge=0, description="Total verified infrastructure defects")
    total_maintenance_tasks: int = Field(ge=0, description="Total maintenance work orders")
    active_maintenance_tasks: int = Field(ge=0, description="Work orders in progress")
    critical_priority_areas_count: int = Field(
        ge=0, description="Areas flagged as CRITICAL inspection priority"
    )
    generated_at: datetime = Field(description="Dashboard generation timestamp")


class TrendsAnalyticsResponse(BaseModel):
    """Historical timeline trends across submissions, verifications, and repairs."""

    submissions_trend: list[TimeSeriesPoint] = Field(description="Daily report submissions")
    verifications_trend: list[TimeSeriesPoint] = Field(description="Daily completed verifications")
    completions_trend: list[TimeSeriesPoint] = Field(description="Daily completed repairs")
