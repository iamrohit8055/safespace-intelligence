"""Area-level evidence confidence aggregation, completeness assessment, and persistence."""

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.intelligence.confidence import (
    calculate_report_confidence,
    get_active_confidence_config,
    get_current_report_confidence,
)
from app.models.confidence import (
    AreaConfidenceComponent,
    AreaConfidenceScore,
    ConfidenceConfiguration,
)
from app.models.geography import AdministrativeArea
from app.models.reporting import Report, ReportCategory

PRECISION_SCORE = Decimal("0.0001")
PRECISION_PCT = Decimal("0.01")


def calculate_area_confidence(
    db: Session,
    area_id: uuid.UUID,
    config_version: str | None = None,
) -> AreaConfidenceScore:
    """Calculate transparent, versioned area-level evidence confidence and completeness.

    Eligibility Rules:
        - Must be assigned to target administrative area (administrative_area_id == area_id).
        - Must be in VERIFIED lifecycle status.
        - Must be a canonical report (duplicate_of_id IS NULL). Confirmed duplicates are excluded.
        - Evaluates report confidence scores against the requested methodology version.

    Metrics Produced:
        - area_confidence_score: Category-balanced mean of observed category confidence scores.
        - confidence_completeness_pct: Proportion of eligible canonical reports with
          usable confidence.
        - total_reports_count: Total eligible canonical reports.
        - reports_with_confidence_count: Eligible canonical reports with non-null confidence.
        - reports_without_confidence_count: Eligible canonical reports without usable confidence.
        - Category-level breakdown components with observation counts and availability state.
    """
    area = db.execute(
        select(AdministrativeArea).where(AdministrativeArea.id == area_id)
    ).scalar_one_or_none()
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Administrative area not found.",
        )

    config = get_active_confidence_config(db, config_version)
    now = datetime.now(UTC)

    # 1. Query eligible canonical verified reports
    stmt = (
        select(Report)
        .where(
            Report.administrative_area_id == area_id,
            Report.status == "VERIFIED",
            Report.duplicate_of_id.is_(None),
        )
        .order_by(Report.category_id.asc(), Report.id.asc())
    )
    eligible_reports = list(db.execute(stmt).scalars().all())
    total_eligible = len(eligible_reports)

    # 2. Retrieve or compute report confidence scores for eligible reports
    category_scores_map: dict[int, list[Decimal]] = {}
    reports_with_conf = 0

    for rep in eligible_reports:
        r_conf = get_current_report_confidence(db, rep.id, config.version)
        if r_conf is None:
            r_conf = calculate_report_confidence(db, rep.id, config.version)

        cid = rep.category_id
        category_scores_map.setdefault(cid, [])
        if r_conf and r_conf.confidence_score is not None:
            category_scores_map[cid].append(r_conf.confidence_score)
            reports_with_conf += 1

    reports_without_conf = total_eligible - reports_with_conf

    # Completeness percentage
    if total_eligible > 0:
        completeness_pct = (
            (Decimal(reports_with_conf) / Decimal(total_eligible)) * Decimal("100.00")
        ).quantize(PRECISION_PCT, rounding=ROUND_HALF_UP)
    else:
        completeness_pct = Decimal("0.00")

    # 3. Retrieve all active taxonomy categories for exhaustive reporting
    categories = list(
        db.execute(
            select(ReportCategory)
            .where(ReportCategory.is_active.is_(True))
            .order_by(ReportCategory.id.asc())
        )
        .scalars()
        .all()
    )

    component_payloads: list[dict[str, Any]] = []
    observed_category_means: list[Decimal] = []

    for cat in categories:
        scores = category_scores_map.get(cat.id, [])
        report_cnt = sum(1 for r in eligible_reports if r.category_id == cat.id)
        confident_cnt = len(scores)

        if confident_cnt > 0:
            cat_mean = (sum(scores) / Decimal(confident_cnt)).quantize(
                PRECISION_SCORE, rounding=ROUND_HALF_UP
            )
            state = "OBSERVED"
            observed_category_means.append(cat_mean)
        else:
            cat_mean = None
            state = "INSUFFICIENT_DATA"

        component_payloads.append(
            {
                "category_id": cat.id,
                "category_confidence_score": cat_mean,
                "report_count": report_cnt,
                "confident_report_count": confident_cnt,
                "availability_state": state,
            }
        )

    # Area score: category-balanced mean across observed categories
    if observed_category_means:
        area_score = (
            sum(observed_category_means) / Decimal(len(observed_category_means))
        ).quantize(PRECISION_SCORE, rounding=ROUND_HALF_UP)
    else:
        area_score = None

    try:
        # Atomic archival: mark existing active area scores as inactive
        db.execute(
            update(AreaConfidenceScore)
            .where(
                AreaConfidenceScore.administrative_area_id == area.id,
                AreaConfidenceScore.configuration_id == config.id,
                AreaConfidenceScore.is_current.is_(True),
            )
            .values(is_current=False)
        )

        area_conf_record = AreaConfidenceScore(
            administrative_area_id=area.id,
            configuration_id=config.id,
            area_confidence_score=area_score,
            confidence_completeness_pct=completeness_pct,
            total_reports_count=total_eligible,
            reports_with_confidence_count=reports_with_conf,
            reports_without_confidence_count=reports_without_conf,
            calculation_timestamp=now,
            is_current=True,
            methodology_metadata={
                "aggregation_method": "category_balanced_mean",
                "participating_categories": len(observed_category_means),
                "total_categories": len(categories),
                "sample_size_guidance": (
                    "Area confidence is computed as an unweighted category-balanced mean across "
                    "observed categories. Inspect per-category report_count and "
                    "confident_report_count in components to evaluate sample size representation."
                ),
            },
        )
        db.add(area_conf_record)
        db.flush()

        for cp in component_payloads:
            comp = AreaConfidenceComponent(
                area_confidence_id=area_conf_record.id,
                category_id=cp["category_id"],
                category_confidence_score=cp["category_confidence_score"],
                report_count=cp["report_count"],
                confident_report_count=cp["confident_report_count"],
                availability_state=cp["availability_state"],
            )
            db.add(comp)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_current_area_confidence(db, area.id, config.version)  # type: ignore[return-value]


def get_current_area_confidence(
    db: Session,
    area_id: uuid.UUID,
    config_version: str | None = None,
) -> AreaConfidenceScore | None:
    """Retrieve active current confidence assessment for an administrative area."""
    stmt = (
        select(AreaConfidenceScore)
        .options(
            joinedload(AreaConfidenceScore.components).joinedload(AreaConfidenceComponent.category)
        )
        .join(ConfidenceConfiguration)
        .where(
            AreaConfidenceScore.administrative_area_id == area_id,
            AreaConfidenceScore.is_current.is_(True),
        )
    )
    if config_version:
        stmt = stmt.where(ConfidenceConfiguration.version == config_version)
    else:
        stmt = stmt.where(ConfidenceConfiguration.is_active.is_(True)).order_by(
            AreaConfidenceScore.calculation_timestamp.desc()
        )

    return db.execute(stmt).scalars().first()


def get_area_confidence_history(
    db: Session,
    area_id: uuid.UUID,
) -> list[AreaConfidenceScore]:
    """Retrieve chronological confidence assessment history for an administrative area."""
    stmt = (
        select(AreaConfidenceScore)
        .options(
            joinedload(AreaConfidenceScore.components).joinedload(AreaConfidenceComponent.category)
        )
        .where(AreaConfidenceScore.administrative_area_id == area_id)
        .order_by(AreaConfidenceScore.calculation_timestamp.desc())
    )
    return list(db.execute(stmt).scalars().unique().all())
