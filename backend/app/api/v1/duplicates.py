"""Administrative API endpoints for duplicate candidate detection, review, and linking."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.models.iam import User
from app.schemas.duplicates import (
    DetectDuplicatesRequest,
    DetectDuplicatesResponse,
    DuplicateCandidateListResponse,
    DuplicateCandidateResponse,
    DuplicateReviewHistoryResponse,
    DuplicateReviewRequest,
)
from app.services.duplicates import (
    detect_candidates_for_report,
    detect_candidates_in_area,
    get_active_duplicate_config,
    get_duplicate_candidates,
    get_report_duplicate_history,
    review_duplicate_candidate,
)

duplicates_subrouter = APIRouter()

verifier_or_admin = require_roles("verifier", "admin")
admin_only = require_roles("admin")


@duplicates_subrouter.get(
    "/duplicate-candidates",
    response_model=DuplicateCandidateListResponse,
    status_code=status.HTTP_200_OK,
    summary="List spatial duplicate candidate pairs",
    description=(
        "Retrieves a paginated list of potential duplicate report pairs detected by spatial "
        "and temporal proximity. Access restricted to verifiers and administrators."
    ),
)
def list_duplicate_candidates(
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    review_status: Annotated[
        str | None,
        Query(
            description=(
                "Optional filter by review status ('PENDING', 'CONFIRMED_DUPLICATE', "
                "'NOT_DUPLICATE', 'NEEDS_REVIEW')."
            )
        ),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> DuplicateCandidateListResponse:
    """List duplicate candidates with pagination and filtering."""
    items, total = get_duplicate_candidates(
        db, review_status=review_status, limit=limit, offset=offset
    )
    return DuplicateCandidateListResponse(
        items=[DuplicateCandidateResponse.model_validate(c) for c in items],
        total=total,
        limit=limit,
        offset=offset,
    )


@duplicates_subrouter.get(
    "/reports/{report_id}/duplicate-candidates",
    response_model=list[DuplicateCandidateResponse],
    status_code=status.HTTP_200_OK,
    summary="Get duplicate candidates for a specific report",
    description=(
        "Retrieves all detected duplicate candidate pairs involving the specified report. "
        "Optionally executes on-demand candidate discovery if none exist. "
        "Access restricted to verifiers and administrators."
    ),
)
def get_candidates_for_report(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    detect: Annotated[
        bool,
        Query(description="If True, triggers candidate detection for this report."),
    ] = True,
) -> list[DuplicateCandidateResponse]:
    """Retrieve or detect duplicate candidates for a specific report."""
    if detect:
        candidates = detect_candidates_for_report(db, report_id)
    else:
        candidates, _ = get_duplicate_candidates(db, report_id=report_id)
    return [DuplicateCandidateResponse.model_validate(c) for c in candidates]


@duplicates_subrouter.post(
    "/duplicate-candidates/detect",
    response_model=DetectDuplicatesResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger batch duplicate candidate discovery",
    description=(
        "Executes spatial and temporal duplicate candidate discovery across reports in an "
        "administrative area or globally. Access strictly restricted to administrators."
    ),
)
def trigger_batch_detection(
    payload: DetectDuplicatesRequest,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
) -> DetectDuplicatesResponse:
    """Execute batch duplicate candidate discovery using PostGIS geography."""
    config = get_active_duplicate_config(db, payload.configuration_version)
    evaluated, new_count = detect_candidates_in_area(
        db,
        area_id=payload.administrative_area_id,
        config_version=payload.configuration_version,
    )
    return DetectDuplicatesResponse(
        candidates_evaluated=evaluated,
        new_candidates_created=new_count,
        configuration_version=config.version,
        administrative_area_id=payload.administrative_area_id,
    )


@duplicates_subrouter.post(
    "/duplicate-candidates/{candidate_id}/review",
    response_model=DuplicateCandidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Review candidate pair and confirm duplicate relationship",
    description=(
        "Records moderation decision (CONFIRMED_DUPLICATE, NOT_DUPLICATE, NEEDS_REVIEW). "
        "When confirmed, links the duplicate report to the canonical report via duplicate_of_id. "
        "Maintains an immutable review audit trail. "
        "Access restricted to verifiers and administrators."
    ),
)
def review_candidate(
    candidate_id: uuid.UUID,
    payload: DuplicateReviewRequest,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> DuplicateCandidateResponse:
    """Review duplicate candidate and establish canonical links."""
    candidate, _ = review_duplicate_candidate(db, candidate_id, payload, current_user)
    return DuplicateCandidateResponse.model_validate(candidate)


@duplicates_subrouter.get(
    "/reports/{report_id}/duplicate-history",
    response_model=list[DuplicateReviewHistoryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get duplicate review audit history for a report",
    description=(
        "Retrieves chronological duplicate moderation decisions and canonical linking history "
        "for the specified report. Access restricted to verifiers and administrators."
    ),
)
def get_duplicate_history(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[DuplicateReviewHistoryResponse]:
    """Retrieve duplicate review history ledger for a report."""
    history = get_report_duplicate_history(db, report_id)
    return [DuplicateReviewHistoryResponse.model_validate(h) for h in history]
