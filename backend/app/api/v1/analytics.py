"""Administrative API endpoints for executive analytics and intelligence reporting."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.iam import User
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    ConfidenceAnalyticsResponse,
    MaintenanceAnalyticsResponse,
    ReportAnalyticsResponse,
    SdiAnalyticsResponse,
    TrendsAnalyticsResponse,
)
from app.services.analytics import (
    get_analytics_overview,
    get_confidence_analytics,
    get_maintenance_analytics,
    get_reports_analytics,
    get_sdi_analytics,
    get_trends_analytics,
)

admin_analytics_router = APIRouter()
admin_or_verifier = require_roles("admin", "verifier")


@admin_analytics_router.get(
    "/overview",
    response_model=AnalyticsOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Executive overview analytics dashboard",
    description="Returns summary KPIs across reports, verification backlogs, SDI, and maintenance.",
)
def get_overview_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
) -> AnalyticsOverviewResponse:
    """Get executive dashboard overview."""
    return get_analytics_overview(db)


@admin_analytics_router.get(
    "/reports",
    response_model=ReportAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Infrastructure deficiency reporting analytics",
    description="Returns report aggregations by status, category, area, and submission volume.",
)
def get_reports_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query(description="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[date | None, Query(description="End date (YYYY-MM-DD)")] = None,
    area_id: Annotated[uuid.UUID | None, Query(description="Filter by area UUID")] = None,
) -> ReportAnalyticsResponse:
    """Get report aggregations."""
    return get_reports_analytics(db, start_date=start_date, end_date=end_date, area_id=area_id)


@admin_analytics_router.get(
    "/sdi",
    response_model=SdiAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Safety Deficiency Index (SDI) analytics",
    description="Returns distribution of SDI deficiency scores grouped by severity tier.",
)
def get_sdi_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    area_id: Annotated[uuid.UUID | None, Query(description="Filter by area UUID")] = None,
) -> SdiAnalyticsResponse:
    """Get SDI aggregations."""
    return get_sdi_analytics(db, area_id=area_id)


@admin_analytics_router.get(
    "/confidence",
    response_model=ConfidenceAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Evidence confidence and data completeness analytics",
    description="Returns confidence scores, completeness distributions, and category sample sizes.",
)
def get_confidence_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    area_id: Annotated[uuid.UUID | None, Query(description="Filter by area UUID")] = None,
) -> ConfidenceAnalyticsResponse:
    """Get confidence aggregations."""
    return get_confidence_analytics(db, area_id=area_id)


@admin_analytics_router.get(
    "/maintenance",
    response_model=MaintenanceAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Infrastructure maintenance operations analytics",
    description="Returns work order volume, status breakdown, turnaround time, and overdue counts.",
)
def get_maintenance_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query(description="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[date | None, Query(description="End date (YYYY-MM-DD)")] = None,
    technician_id: Annotated[
        uuid.UUID | None, Query(description="Filter by technician UUID")
    ] = None,
) -> MaintenanceAnalyticsResponse:
    """Get maintenance aggregations."""
    return get_maintenance_analytics(
        db, start_date=start_date, end_date=end_date, technician_id=technician_id
    )


@admin_analytics_router.get(
    "/trends",
    response_model=TrendsAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="System activity timeline trends",
    description="Returns daily trends comparing submissions, verifications, and repairs.",
)
def get_trends_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query(description="Start date (YYYY-MM-DD)")] = None,
    end_date: Annotated[date | None, Query(description="End date (YYYY-MM-DD)")] = None,
    area_id: Annotated[uuid.UUID | None, Query(description="Filter by area UUID")] = None,
) -> TrendsAnalyticsResponse:
    """Get activity trends."""
    return get_trends_analytics(db, start_date=start_date, end_date=end_date, area_id=area_id)
