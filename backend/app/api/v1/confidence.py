"""Administrative API endpoints for individual report and area-level evidence confidence."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.intelligence.area_confidence import (
    calculate_area_confidence,
    get_area_confidence_history,
    get_current_area_confidence,
)
from app.intelligence.confidence import (
    calculate_report_confidence,
    get_active_confidence_config,
    get_current_report_confidence,
    get_report_confidence_history,
)
from app.models.iam import User
from app.schemas.confidence import (
    AreaConfidenceScoreResponse,
    ConfidenceConfigurationResponse,
    ReportConfidenceScoreResponse,
)

confidence_subrouter = APIRouter()

verifier_or_admin = require_roles("verifier", "admin")
admin_only = require_roles("admin")


# --- Methodology & Configurations ---
@confidence_subrouter.get(
    "/confidence-configurations",
    response_model=ConfidenceConfigurationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get active evidence confidence methodology configuration",
    description=(
        "Retrieves active evidence confidence configuration including transparent "
        "factor definitions, assigned weights, and measurability states. "
        "Access restricted to verifiers and administrators."
    ),
)
def get_confidence_configuration(
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    version: Annotated[
        str | None,
        Query(description="Optional specific methodology version."),
    ] = None,
) -> ConfidenceConfigurationResponse:
    """Retrieve active or versioned evidence confidence configuration."""
    config = get_active_confidence_config(db, version=version)
    return ConfidenceConfigurationResponse.model_validate(config)


# --- Step 8C: Individual Report Evidence Confidence ---
@confidence_subrouter.get(
    "/reports/{report_id}/confidence",
    response_model=ReportConfidenceScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current evidence confidence score for a report",
    description=(
        "Retrieves the active evidence confidence assessment and multi-factor breakdown "
        "for the specified report. Access restricted to verifiers and administrators."
    ),
)
def get_report_confidence(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    configuration_version: Annotated[
        str | None,
        Query(description="Optional methodology version filter."),
    ] = None,
) -> ReportConfidenceScoreResponse:
    """Retrieve current confidence assessment for a report."""
    score = get_current_report_confidence(
        db, report_id=report_id, config_version=configuration_version
    )
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Evidence confidence assessment not found for this report. "
                "Execute POST /calculate-confidence to compute it."
            ),
        )
    return ReportConfidenceScoreResponse.model_validate(score)


@confidence_subrouter.post(
    "/reports/{report_id}/calculate-confidence",
    response_model=ReportConfidenceScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate evidence confidence score for a report",
    description=(
        "Executes a deterministic evidence confidence calculation for an individual report. "
        "Dynamically normalizes weights over available factors, archives prior assessments, "
        "and atomically records factor contributions. "
        "Access restricted to verifiers and administrators."
    ),
)
def calculate_confidence_for_report(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    configuration_version: Annotated[
        str | None,
        Query(description="Optional explicit methodology version (e.g. 'v1.0.0')."),
    ] = None,
) -> ReportConfidenceScoreResponse:
    """Calculate and persist evidence confidence assessment for a report."""
    score = calculate_report_confidence(
        db, report_id=report_id, config_version=configuration_version
    )
    return ReportConfidenceScoreResponse.model_validate(score)


@confidence_subrouter.get(
    "/reports/{report_id}/confidence-history",
    response_model=list[ReportConfidenceScoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Get evidence confidence calculation history for a report",
    description=(
        "Retrieves the complete historical audit log of all confidence calculations "
        "for the report. Access restricted to verifiers and administrators."
    ),
)
def get_report_confidence_audit_history(
    report_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ReportConfidenceScoreResponse]:
    """Retrieve complete chronological confidence history for a report."""
    history = get_report_confidence_history(db, report_id=report_id)
    return [ReportConfidenceScoreResponse.model_validate(s) for s in history]


# --- Step 8D: Area-Level Confidence & Completeness ---
@confidence_subrouter.get(
    "/areas/{area_id}/confidence",
    response_model=AreaConfidenceScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current evidence confidence and completeness for an area",
    description=(
        "Retrieves active area-level confidence score, completeness percentage, "
        "and category breakdown. Access restricted to verifiers and administrators."
    ),
)
def get_area_confidence(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    configuration_version: Annotated[
        str | None,
        Query(description="Optional methodology version filter."),
    ] = None,
) -> AreaConfidenceScoreResponse:
    """Retrieve current area confidence assessment."""
    score = get_current_area_confidence(db, area_id=area_id, config_version=configuration_version)
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Area confidence assessment not found. "
                "Execute POST /calculate-confidence to compute it."
            ),
        )
    return AreaConfidenceScoreResponse.model_validate(score)


@confidence_subrouter.post(
    "/areas/{area_id}/calculate-confidence",
    response_model=AreaConfidenceScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate area-level evidence confidence and completeness",
    description=(
        "Aggregates eligible canonical verified reports, calculates category-balanced confidence, "
        "evaluates data completeness, and records audit history. "
        "Access restricted to administrators."
    ),
)
def calculate_confidence_for_area(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
    configuration_version: Annotated[
        str | None,
        Query(description="Optional explicit methodology version (e.g. 'v1.0.0')."),
    ] = None,
) -> AreaConfidenceScoreResponse:
    """Calculate and persist area confidence assessment."""
    score = calculate_area_confidence(db, area_id=area_id, config_version=configuration_version)
    return AreaConfidenceScoreResponse.model_validate(score)


@confidence_subrouter.get(
    "/areas/{area_id}/confidence-history",
    response_model=list[AreaConfidenceScoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Get area confidence calculation history",
    description=(
        "Retrieves the chronological audit log of all area-level confidence calculations. "
        "Access restricted to verifiers and administrators."
    ),
)
def get_area_confidence_audit_history(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AreaConfidenceScoreResponse]:
    """Retrieve complete chronological confidence history for an administrative area."""
    history = get_area_confidence_history(db, area_id=area_id)
    return [AreaConfidenceScoreResponse.model_validate(s) for s in history]
