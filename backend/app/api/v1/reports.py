"""Citizen infrastructure deficiency report router endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.database.session import get_db
from app.models.iam import User
from app.schemas.media import ReportMediaResponse
from app.schemas.reports import (
    PublicReportMapItem,
    ReportCategoryDetail,
    ReportCreateRequest,
    ReportListResponse,
    ReportResponse,
)
from app.schemas.verification import VerificationHistoryResponse
from app.services.media import get_report_media_file, upload_report_media
from app.services.reports import (
    create_citizen_report,
    get_citizen_report_by_id,
    get_public_map_reports,
    list_active_categories,
    list_citizen_reports,
)
from app.services.verification import get_verification_history

reports_router = APIRouter()

citizen_only = require_roles("citizen")


@reports_router.get(
    "/categories",
    response_model=list[ReportCategoryDetail],
    status_code=status.HTTP_200_OK,
    summary="List active deficiency categories",
    description="Retrieves the taxonomy classification categories accepted by the platform.",
)
def get_categories(
    db: Annotated[Session, Depends(get_db)],
) -> list[ReportCategoryDetail]:
    """List active deficiency categories."""
    categories = list_active_categories(db)
    return [ReportCategoryDetail.model_validate(c) for c in categories]


@reports_router.get(
    "/public/map",
    response_model=list[PublicReportMapItem],
    status_code=status.HTTP_200_OK,
    summary="Public infrastructure deficiency map observations",
    description=(
        "Retrieves active infrastructure deficiencies with privacy-preserving fuzzed coordinates "
        "(~100m street level) and stripped reporter identity for public exploration maps."
    ),
)
def get_public_map(
    db: Annotated[Session, Depends(get_db)],
    category_id: Annotated[int | None, Query(description="Optional category filter")] = None,
    status_filter: Annotated[str | None, Query(description="Optional status filter")] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Max observations returned")] = 250,
) -> list[PublicReportMapItem]:
    """Retrieve public deficiency reports for interactive map rendering."""
    return get_public_map_reports(
        db, category_id=category_id, status_filter=status_filter, limit=limit
    )


@reports_router.post(
    "",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit infrastructure deficiency report",
    description=(
        "Submits a new citizen infrastructure deficiency observation. "
        "Initial status is always SUBMITTED. Automatically creates the initial "
        "audit status history row and resolves administrative boundary via PostGIS."
    ),
)
def submit_report(
    payload: ReportCreateRequest,
    current_user: Annotated[User, Depends(citizen_only)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Submit a new infrastructure deficiency observation.

    Reporter identity is derived strictly from the authenticated JWT token.
    Administrative area is resolved spatially using PostGIS ST_Covers if matching boundaries exist.
    """
    report = create_citizen_report(db, payload, current_user)
    return ReportResponse.model_validate(report)


@reports_router.get(
    "",
    response_model=ReportListResponse,
    status_code=status.HTTP_200_OK,
    summary="List citizen's submitted reports",
    description=(
        "Returns a paginated list of deficiency reports submitted by the authenticated citizen. "
        "Orders deterministically by submitted_at DESC with report ID as a tie-breaker."
    ),
)
def list_reports(
    current_user: Annotated[User, Depends(citizen_only)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page size limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> ReportListResponse:
    """List reports belonging to the authenticated citizen."""
    items, total = list_citizen_reports(db, current_user, limit, offset)
    return ReportListResponse(
        items=[ReportResponse.model_validate(r) for r in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@reports_router.get(
    "/{report_id}",
    response_model=ReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get citizen report details",
    description=(
        "Retrieves detailed sanitized information for a specific report. "
        "Returns 404 if the report does not exist or does not belong to the calling citizen."
    ),
)
def get_report_detail(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(citizen_only)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportResponse:
    """Retrieve details for a single citizen report."""
    report = get_citizen_report_by_id(db, report_id, current_user.id)
    return ReportResponse.model_validate(report)


@reports_router.get(
    "/{report_id}/verification-history",
    response_model=list[VerificationHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get report verification history",
    description=(
        "Retrieves the chronological list of verification decisions for a report. "
        "Citizens can view history only for their own reports; verifiers and admins "
        "can view history for any report. Returns 404 if not found or unauthorized."
    ),
)
def get_report_verification_history(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> list[VerificationHistoryResponse]:
    """Retrieve chronological audit verification decisions for a report."""
    records = get_verification_history(db, report_id, current_user)
    return [VerificationHistoryResponse.model_validate(rec) for rec in records]


@reports_router.post(
    "/{report_id}/media",
    response_model=ReportMediaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload photographic evidence for report",
    description=(
        "Uploads and attaches an image file (JPEG, PNG, WebP) up to 15 MB. "
        "Automatically strips EXIF/GPS tags, calculates SHA-256 checksum, and safely stores file."
    ),
)
def upload_media_endpoint(
    report_id: uuid.UUID,
    file: Annotated[UploadFile, File(description="Image file (JPEG, PNG, WebP)")],
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ReportMediaResponse:
    """Upload photographic evidence for a report."""
    media = upload_report_media(db, report_id, file, current_user)
    resp = ReportMediaResponse.model_validate(media)
    resp.download_url = f"/api/v1/reports/{report_id}/media/{media.id}"
    return resp


@reports_router.get(
    "/{report_id}/media/{media_id}",
    summary="Download report photographic media",
    description="Streams stored photographic evidence with proper content-type headers.",
)
def download_media_endpoint(
    report_id: uuid.UUID,
    media_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_current_user)] = None,
) -> FileResponse:
    """Retrieve and stream photographic evidence file."""
    file_path, mime_type = get_report_media_file(db, report_id, media_id, current_user)
    return FileResponse(path=file_path, media_type=mime_type, filename=file_path.name)
