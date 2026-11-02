"""Administrative API endpoints for municipal infrastructure inspection priority scoring."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.database.session import get_db
from app.intelligence.priority import (
    calculate_area_inspection_priority,
    get_area_priority_history,
    get_current_area_priority,
    list_area_priorities,
    list_priority_configurations,
)
from app.models.iam import User
from app.schemas.priority import (
    AreaPriorityListResponse,
    AreaPriorityScoreDetailResponse,
    AreaPriorityScoreResponse,
    PriorityConfigurationResponse,
)

priority_subrouter = APIRouter()
admin_or_verifier = require_roles("admin", "verifier")
admin_only = require_roles("admin")


@priority_subrouter.get(
    "/priority/configurations",
    response_model=list[PriorityConfigurationResponse],
    status_code=status.HTTP_200_OK,
    summary="List inspection priority model configurations",
    description="Retrieves all versioned priority scoring model configurations.",
)
def get_priority_configurations(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
) -> list[PriorityConfigurationResponse]:
    """List all versioned priority configurations."""
    configs = list_priority_configurations(db)
    return [PriorityConfigurationResponse.model_validate(c) for c in configs]


@priority_subrouter.post(
    "/areas/{area_id}/calculate-priority",
    response_model=AreaPriorityScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate area infrastructure inspection priority",
    description=(
        "Executes multi-factor inspection priority calculation balancing SDI severity, "
        "observation staleness, unresolved defect volume, and confidence uncertainty gap."
    ),
)
def calculate_area_priority_endpoint(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
    version: Annotated[str | None, Query(description="Optional model version to apply")] = None,
) -> AreaPriorityScoreResponse:
    """Calculate and persist area inspection priority."""
    score = calculate_area_inspection_priority(db, area_id, config_version=version)
    resp = AreaPriorityScoreResponse.model_validate(score)
    if score.configuration:
        resp.configuration_version = score.configuration.version
    return resp


@priority_subrouter.get(
    "/areas/{area_id}/priority",
    response_model=AreaPriorityScoreDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current active area inspection priority",
    description="Retrieves the latest calculated active inspection priority score for an area.",
)
def get_area_priority_endpoint(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
) -> AreaPriorityScoreDetailResponse:
    """Get active inspection priority for an area."""
    score = get_current_area_priority(db, area_id)
    resp = AreaPriorityScoreDetailResponse.model_validate(score)
    if score.configuration:
        resp.configuration_version = score.configuration.version
    if score.area:
        resp.area_name = score.area.name
        resp.area_code = score.area.code
        resp.area_type = score.area.area_type
    return resp


@priority_subrouter.get(
    "/areas/{area_id}/priority-history",
    response_model=list[AreaPriorityScoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Get historical inspection priority calculations for an area",
    description="Returns chronological audit log of priority calculations for an area.",
)
def get_area_priority_history_endpoint(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 20,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> list[AreaPriorityScoreResponse]:
    """Get priority calculation history for an area."""
    items, _ = get_area_priority_history(db, area_id, limit=limit, offset=offset)
    results: list[AreaPriorityScoreResponse] = []
    for item in items:
        resp = AreaPriorityScoreResponse.model_validate(item)
        if item.configuration:
            resp.configuration_version = item.configuration.version
        results.append(resp)
    return results


@priority_subrouter.get(
    "/priority/areas",
    response_model=AreaPriorityListResponse,
    status_code=status.HTTP_200_OK,
    summary="List ranked area inspection priorities",
    description="Retrieves active inspection priority rankings across administrative areas.",
)
def list_area_priorities_endpoint(
    current_user: Annotated[User, Depends(admin_or_verifier)],
    db: Annotated[Session, Depends(get_db)],
    priority_level: Annotated[
        str | None,
        Query(description="Filter by level: CRITICAL, HIGH, MEDIUM, LOW, INSUFFICIENT_DATA"),
    ] = None,
    area_type: Annotated[
        str | None,
        Query(description="Filter by administrative area type: ward, district, municipality"),
    ] = None,
    sort_by: Annotated[
        str,
        Query(description="Sort order: score_desc, score_asc, unresolved_desc"),
    ] = "score_desc",
    limit: Annotated[int, Query(ge=1, le=100, description="Page limit")] = 50,
    offset: Annotated[int, Query(ge=0, description="Page offset")] = 0,
) -> AreaPriorityListResponse:
    """List ranked area inspection priorities with filtering and pagination."""
    items, total = list_area_priorities(
        db,
        priority_level=priority_level,
        area_type=area_type,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
    )
    detail_items: list[AreaPriorityScoreDetailResponse] = []
    for score, area in items:
        resp = AreaPriorityScoreDetailResponse.model_validate(score)
        if score.configuration:
            resp.configuration_version = score.configuration.version
        resp.area_name = area.name
        resp.area_code = area.code
        resp.area_type = area.area_type
        detail_items.append(resp)

    return AreaPriorityListResponse(
        items=detail_items,
        total=total,
        limit=limit,
        offset=offset,
    )
