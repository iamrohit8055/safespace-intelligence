"""Administrative and analyst API endpoints for Safety Deficiency Index (SDI) intelligence."""

import json
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.api.v1.confidence import confidence_subrouter
from app.api.v1.duplicates import duplicates_subrouter
from app.api.v1.priority import priority_subrouter
from app.database.session import get_db
from app.intelligence.service import (
    calculate_area_sdi,
    get_area_sdi_history,
    get_current_area_sdi,
    list_scoring_configurations,
)
from app.models.geography import AdministrativeArea
from app.models.iam import User
from app.models.intelligence import AreaScore
from app.models.priority import AreaPriorityScore
from app.schemas.intelligence import (
    AreaScoreResponse,
    ScoringConfigurationResponse,
)

intelligence_router = APIRouter()
intelligence_router.include_router(duplicates_subrouter)
intelligence_router.include_router(confidence_subrouter)
intelligence_router.include_router(priority_subrouter)

verifier_or_admin = require_roles("verifier", "admin")
admin_only = require_roles("admin")


@intelligence_router.get(
    "/scoring-configurations",
    response_model=list[ScoringConfigurationResponse],
    status_code=status.HTTP_200_OK,
    summary="List SDI scoring methodologies and configurations",
    description=(
        "Retrieves all versioned SDI scoring configurations including category weight "
        "distributions. Access restricted to verifiers and administrators."
    ),
)
def get_scoring_configurations(
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ScoringConfigurationResponse]:
    """List all versioned scoring configurations."""
    configs = list_scoring_configurations(db)
    return [ScoringConfigurationResponse.model_validate(c) for c in configs]


@intelligence_router.post(
    "/areas/{area_id}/calculate",
    response_model=AreaScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Calculate Safety Deficiency Index (SDI) for an administrative area",
    description=(
        "Executes a deterministic SDI calculation for the specified administrative area. "
        "Evaluates verified infrastructure deficiency reports, normalizes weights over observed "
        "categories, atomically records score components, and marks this calculation as current. "
        "Access strictly restricted to administrators."
    ),
)
def calculate_area_score(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(admin_only)],
    db: Annotated[Session, Depends(get_db)],
    configuration_version: Annotated[
        str | None,
        Query(
            description=(
                "Optional explicit methodology version (e.g. 'v1.0.0'). Defaults to active version."
            ),
        ),
    ] = None,
) -> AreaScoreResponse:
    """Execute SDI calculation for an administrative area."""
    score = calculate_area_sdi(db, area_id=area_id, configuration_version=configuration_version)
    return AreaScoreResponse.model_validate(score)


@intelligence_router.get(
    "/areas/{area_id}/sdi",
    response_model=AreaScoreResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current SDI score for an administrative area",
    description=(
        "Retrieves the active current Safety Deficiency Index (SDI) calculation "
        "and component breakdown for the specified administrative area. "
        "Access restricted to verifiers and administrators."
    ),
)
def get_current_sdi(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
    configuration_version: Annotated[
        str | None,
        Query(
            description=(
                "Optional configuration version filter. If omitted, returns latest active score."
            ),
        ),
    ] = None,
) -> AreaScoreResponse:
    """Retrieve current SDI score for an administrative area."""
    score = get_current_area_sdi(db, area_id=area_id, configuration_version=configuration_version)
    return AreaScoreResponse.model_validate(score)


@intelligence_router.get(
    "/areas/{area_id}/history",
    response_model=list[AreaScoreResponse],
    status_code=status.HTTP_200_OK,
    summary="Get SDI calculation history for an administrative area",
    description=(
        "Retrieves the complete historical audit log of all SDI calculations executed for the "
        "specified administrative area, ordered chronologically (newest first). "
        "Access restricted to verifiers and administrators."
    ),
)
def get_sdi_history(
    area_id: uuid.UUID,
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> list[AreaScoreResponse]:
    """Retrieve complete chronological SDI history for an administrative area."""
    history = get_area_sdi_history(db, area_id=area_id)
    return [AreaScoreResponse.model_validate(s) for s in history]


@intelligence_router.get(
    "/areas/geojson",
    status_code=status.HTTP_200_OK,
    summary="Get administrative boundaries as GeoJSON FeatureCollection",
    description=(
        "Returns all administrative areas with their PostGIS polygon boundaries and "
        "associated SDI, priority, confidence, and completeness scores for GIS map rendering."
    ),
)
def get_areas_geojson(
    current_user: Annotated[User, Depends(verifier_or_admin)],
    db: Annotated[Session, Depends(get_db)],
) -> dict[str, Any]:
    """Retrieve all municipal administrative area boundaries as GeoJSON."""
    stmt = select(
        AdministrativeArea.id,
        AdministrativeArea.name,
        AdministrativeArea.code,
        AdministrativeArea.area_type,
        AdministrativeArea.parent_id,
        func.ST_AsGeoJSON(AdministrativeArea.boundary).label("geojson"),
    ).order_by(AdministrativeArea.name.asc())

    rows = db.execute(stmt).all()

    current_priorities = {
        p.area_id: p
        for p in db.execute(select(AreaPriorityScore).where(AreaPriorityScore.is_current.is_(True)))
        .scalars()
        .all()
    }
    current_sdis = {
        s.administrative_area_id: s
        for s in db.execute(select(AreaScore).where(AreaScore.is_current.is_(True))).scalars().all()
    }

    features: list[dict[str, Any]] = []
    for row in rows:
        area_id = row.id
        geom = json.loads(row.geojson) if row.geojson else None
        p_score = current_priorities.get(area_id)
        s_score = current_sdis.get(area_id)

        features.append(
            {
                "type": "Feature",
                "id": str(area_id),
                "geometry": geom,
                "properties": {
                    "id": str(area_id),
                    "name": row.name,
                    "code": row.code,
                    "area_type": row.area_type,
                    "parent_id": str(row.parent_id) if row.parent_id else None,
                    "sdi_score": (
                        float(s_score.score) if s_score and s_score.score is not None else None
                    ),
                    "sdi_completeness_pct": float(s_score.completeness_pct) if s_score else 0.0,
                    "priority_score": (
                        float(p_score.priority_score)
                        if p_score and p_score.priority_score is not None
                        else None
                    ),
                    "priority_level": p_score.priority_level if p_score else "INSUFFICIENT_DATA",
                    "confidence_score": (
                        float(p_score.confidence_score)
                        if p_score and p_score.confidence_score is not None
                        else None
                    ),
                    "confidence_completeness_pct": (
                        float(p_score.completeness_pct)
                        if p_score and p_score.completeness_pct
                        else 0.0
                    ),
                    "unresolved_reports_count": (
                        p_score.unresolved_reports_count if p_score else 0
                    ),
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }
