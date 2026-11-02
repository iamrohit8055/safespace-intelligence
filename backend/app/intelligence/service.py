"""Service layer orchestrating SDI calculations, configuration resolution, and persistence."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.intelligence.aggregation import (
    get_eligible_verified_reports,
    group_observations_by_category,
)
from app.intelligence.constants import (
    DEFAULT_MIN_OBSERVATIONS,
    STATE_INSUFFICIENT_DATA,
    STATE_OBSERVED,
)
from app.intelligence.scoring import (
    calculate_category_deficiency_score,
    calculate_sdi,
    validate_configuration_weights,
)
from app.models.geography import AdministrativeArea
from app.models.intelligence import (
    AreaScore,
    ScoreComponent,
    ScoringConfiguration,
    ScoringConfigurationWeight,
)


def get_active_scoring_configuration(
    db: Session,
    version: str | None = None,
) -> ScoringConfiguration:
    """Retrieve a versioned scoring configuration with eager-loaded weights and categories.

    Args:
        db: Active SQLAlchemy database session.
        version: Optional explicit version identifier (e.g. 'v1.0.0').

    Returns:
        ScoringConfiguration: Scoring configuration entity.

    Raises:
        HTTPException: 404 if the requested or active configuration is not found.
    """
    stmt = select(ScoringConfiguration).options(
        joinedload(ScoringConfiguration.weights).joinedload(ScoringConfigurationWeight.category),
    )

    if version is not None:
        stmt = stmt.where(ScoringConfiguration.version == version)
    else:
        stmt = stmt.where(ScoringConfiguration.is_active.is_(True)).order_by(
            ScoringConfiguration.id.desc()
        )

    config = db.execute(stmt).scalars().first()
    if config is None:
        target = f"'{version}'" if version else "active"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scoring configuration {target} not found.",
        )
    return config


def list_scoring_configurations(db: Session) -> list[ScoringConfiguration]:
    """Retrieve all scoring configuration versions.

    Args:
        db: Active SQLAlchemy database session.

    Returns:
        list[ScoringConfiguration]: All configured methodologies ordered by ID.
    """
    stmt = (
        select(ScoringConfiguration)
        .options(
            joinedload(ScoringConfiguration.weights).joinedload(
                ScoringConfigurationWeight.category
            ),
        )
        .order_by(ScoringConfiguration.id.asc())
    )
    return list(db.execute(stmt).scalars().unique().all())


def calculate_area_sdi(
    db: Session,
    area_id: uuid.UUID,
    configuration_version: str | None = None,
) -> AreaScore:
    """Execute reproducible SDI calculation for an administrative area.

    Pipeline:
        1. Validate administrative area existence.
        2. Resolve active or specified scoring configuration version.
        3. Retrieve eligible verified deficiency reports.
        4. Group observations and compute category deficiency scores (0-100).
        5. Normalize available category weights and calculate weighted composite SDI.
        6. Compute data completeness percentage.
        7. Atomically persist AreaScore and associated ScoreComponent records.

    Args:
        db: Active SQLAlchemy database session.
        area_id: Unique UUID of the administrative area.
        configuration_version: Optional version identifier; defaults to current active version.

    Returns:
        AreaScore: Persisted area score record with eager-loaded components and metadata.

    Raises:
        HTTPException: 404 if area or configuration not found.
    """
    area = db.execute(
        select(AdministrativeArea).where(AdministrativeArea.id == area_id)
    ).scalar_one_or_none()

    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrative area not found.",
        )

    config = get_active_scoring_configuration(db, configuration_version)

    assigned_weights: dict[int, Decimal] = {w.category_id: w.weight for w in config.weights}
    validate_configuration_weights(list(assigned_weights.values()))

    eligible_reports = get_eligible_verified_reports(db, area_id)
    grouped = group_observations_by_category(eligible_reports)

    metadata = config.methodology_metadata
    if isinstance(metadata, str):
        import json

        metadata = json.loads(metadata)
    elif not isinstance(metadata, dict):
        metadata = {}

    min_observations = int(metadata.get("min_observations_per_category", DEFAULT_MIN_OBSERVATIONS))

    category_scores: dict[int, Decimal | None] = {}
    component_metadata: dict[int, dict[str, Any]] = {}

    for cid, weight in assigned_weights.items():
        severities = grouped.get(cid, [])
        report_count = len(severities)

        if report_count >= min_observations:
            cat_score = calculate_category_deficiency_score(severities)
            state = STATE_OBSERVED
        else:
            cat_score = None
            state = STATE_INSUFFICIENT_DATA

        category_scores[cid] = cat_score
        component_metadata[cid] = {
            "category_score": cat_score,
            "assigned_weight": weight,
            "report_count": report_count,
            "availability_state": state,
        }

    sdi, norm_weights, contribs, completeness_pct = calculate_sdi(category_scores, assigned_weights)

    participating_count = len([s for s in category_scores.values() if s is not None])
    total_categories = len(assigned_weights)
    reason = (
        "Insufficient eligible observations to compute representative SDI" if sdi is None else None
    )

    try:
        # Mark previous current calculations for this area & configuration as non-current
        db.execute(
            update(AreaScore)
            .where(
                AreaScore.administrative_area_id == area_id,
                AreaScore.configuration_id == config.id,
                AreaScore.is_current.is_(True),
            )
            .values(is_current=False)
        )

        area_score = AreaScore(
            administrative_area_id=area_id,
            configuration_id=config.id,
            score=sdi,
            completeness_pct=completeness_pct,
            participating_categories_count=participating_count,
            total_categories_count=total_categories,
            eligible_reports_count=len(eligible_reports),
            calculation_timestamp=datetime.now(UTC),
            is_current=True,
            reason=reason,
            methodology_metadata=metadata,
        )
        db.add(area_score)
        db.flush()

        for cid, meta in component_metadata.items():
            component = ScoreComponent(
                area_score_id=area_score.id,
                category_id=cid,
                category_score=meta["category_score"],
                assigned_weight=meta["assigned_weight"],
                normalized_weight=norm_weights.get(cid),
                weighted_contribution=contribs.get(cid),
                report_count=meta["report_count"],
                availability_state=meta["availability_state"],
            )
            db.add(component)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_area_score_by_id(db, area_score.id)


def get_area_score_by_id(db: Session, score_id: uuid.UUID) -> AreaScore:
    """Retrieve an AreaScore by ID with all relationships eagerly loaded.

    Args:
        db: Active SQLAlchemy database session.
        score_id: Unique UUID of the AreaScore.

    Returns:
        AreaScore: Loaded score entity with components, area, and configuration.

    Raises:
        HTTPException: 404 if score record not found.
    """
    stmt = (
        select(AreaScore)
        .options(
            joinedload(AreaScore.administrative_area),
            joinedload(AreaScore.configuration),
            joinedload(AreaScore.components).joinedload(ScoreComponent.category),
        )
        .where(AreaScore.id == score_id)
    )
    score = db.execute(stmt).scalars().unique().one_or_none()
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area score record not found.",
        )
    return score


def get_current_area_sdi(
    db: Session,
    area_id: uuid.UUID,
    configuration_version: str | None = None,
) -> AreaScore:
    """Retrieve the current active SDI score for an administrative area.

    Args:
        db: Active SQLAlchemy database session.
        area_id: Unique UUID of the administrative area.
        configuration_version: Optional version identifier.

    Returns:
        AreaScore: Current area score record.

    Raises:
        HTTPException: 404 if area does not exist or no calculation has been run.
    """
    area = db.execute(
        select(AdministrativeArea).where(AdministrativeArea.id == area_id)
    ).scalar_one_or_none()
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrative area not found.",
        )

    stmt = (
        select(AreaScore)
        .options(
            joinedload(AreaScore.administrative_area),
            joinedload(AreaScore.configuration),
            joinedload(AreaScore.components).joinedload(ScoreComponent.category),
        )
        .where(
            AreaScore.administrative_area_id == area_id,
            AreaScore.is_current.is_(True),
        )
    )

    if configuration_version is not None:
        config = get_active_scoring_configuration(db, configuration_version)
        stmt = stmt.where(AreaScore.configuration_id == config.id)
    else:
        stmt = stmt.order_by(AreaScore.calculation_timestamp.desc())

    score = db.execute(stmt).scalars().unique().first()
    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No current SDI calculation found for this administrative area.",
        )
    return score


def get_area_sdi_history(
    db: Session,
    area_id: uuid.UUID,
) -> list[AreaScore]:
    """Retrieve complete chronological calculation history for an administrative area.

    Args:
        db: Active SQLAlchemy database session.
        area_id: Unique UUID of the administrative area.

    Returns:
        list[AreaScore]: Chronologically ordered area score calculations (newest first).

    Raises:
        HTTPException: 404 if administrative area does not exist.
    """
    area = db.execute(
        select(AdministrativeArea).where(AdministrativeArea.id == area_id)
    ).scalar_one_or_none()
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrative area not found.",
        )

    stmt = (
        select(AreaScore)
        .options(
            joinedload(AreaScore.administrative_area),
            joinedload(AreaScore.configuration),
            joinedload(AreaScore.components).joinedload(ScoreComponent.category),
        )
        .where(AreaScore.administrative_area_id == area_id)
        .order_by(AreaScore.calculation_timestamp.desc(), AreaScore.id.desc())
    )
    return list(db.execute(stmt).scalars().unique().all())
