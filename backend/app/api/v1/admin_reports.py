"""Administrative report moderation, verification, and lifecycle transition endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.iam import User
from app.models.reporting import Report
from app.schemas.reports import ReportListResponse, ReportResponse
from app.schemas.verification import (
    RejectReportRequest,
    ReopenReportRequest,
    VerifyReportRequest,
)
from app.services.reports import get_report_by_id
from app.services.verification import (
    get_pending_reports_queue,
    reject_report,
    reopen_report,
    start_report_verification,
    verify_report,
)

admin_reports_router = APIRouter()

verifier_or_admin = require_roles("verifier", "admin")


@admin_reports_router.get(
    "",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List all reports with administrative filters",
    description=(
        "Returns a paginated list of reports with optional status and category filters for staff."
    ),
)
def list_admin_reports(
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    status_filter: Annotated[
        str | None, Query(alias="status", description="Filter by status")
    ] = None,
    category_id: Annotated[int | None, Query(description="Filter by category ID")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> ReportListResponse:
    """List reports across all jurisdictions with optional status and category filters."""
    stmt = select(Report).options(
        joinedload(Report.category),
        joinedload(Report.administrative_area),
        selectinload(Report.media),
    )
    if status_filter:
        stmt = stmt.where(Report.status == status_filter.upper())
    if category_id:
        stmt = stmt.where(Report.category_id == category_id)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
    items = list(
        db.execute(
            stmt.order_by(Report.submitted_at.desc(), Report.id.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .unique()
        .all()
    )
    return ReportListResponse(
        items=[ReportResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_reports_router.get(
    "/detail/{report_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get report detail for staff moderation",
    description="Retrieves complete report details for verifiers and administrators.",
)
def get_admin_report_detail(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Retrieve full details of any report for staff review."""
    report = get_report_by_id(db, report_id)
    return ReportResponse.model_validate(report)


@admin_reports_router.get(
    "/pending",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="Pending reports inspection queue",
    description=(
        "Returns a paginated FIFO queue of reports in SUBMITTED status awaiting moderation. "
        "Ordered deterministically by submitted_at ASC, id ASC. Restricted to verifier/admin."
    ),
)
def get_pending_queue(
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> ReportListResponse:
    """Retrieve the pending report inspection queue for moderation."""
    items, total = get_pending_reports_queue(db, limit, offset)
    return ReportListResponse(
        items=[ReportResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_reports_router.post(
    "/{report_id}/start-verification",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Start report verification",
    description=(
        "Transitions a SUBMITTED report into UNDER_VERIFICATION with row locking. "
        "Returns 409 if the report is no longer in SUBMITTED status."
    ),
)
def start_verification(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Lock the report and transition its status from SUBMITTED to UNDER_VERIFICATION."""
    report = start_report_verification(db, report_id, current_user)
    return ReportResponse.model_validate(report)


@admin_reports_router.post(
    "/{report_id}/verify",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve and verify report",
    description=(
        "Approves an UNDER_VERIFICATION report, assigns physical deficiency severity (1-5), "
        "and atomically records append-only verification and status history entries."
    ),
)
def verify(
    report_id: uuid.UUID,
    payload: VerifyReportRequest,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Approve report, assign severity scale (1-5), and transition to VERIFIED."""
    report = verify_report(db, report_id, payload, current_user)
    return ReportResponse.model_validate(report)


@admin_reports_router.post(
    "/{report_id}/reject",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject report",
    description=(
        "Rejects an UNDER_VERIFICATION report with mandatory categorical reasoning, "
        "and atomically records append-only verification and status history entries."
    ),
)
def reject(
    report_id: uuid.UUID,
    payload: RejectReportRequest,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Reject report with reason code and transition to REJECTED."""
    report = reject_report(db, report_id, payload, current_user)
    return ReportResponse.model_validate(report)


@admin_reports_router.post(
    "/{report_id}/reopen",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Reopen report for moderation",
    description=(
        "Reopens a VERIFIED or REJECTED report back to UNDER_VERIFICATION. "
        "Preserves prior verification decisions and appends an audit status history record."
    ),
)
def reopen(
    report_id: uuid.UUID,
    payload: ReopenReportRequest,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Reopen a finalized report back into UNDER_VERIFICATION status."""
    report = reopen_report(db, report_id, payload, current_user)
    return ReportResponse.model_validate(report)
