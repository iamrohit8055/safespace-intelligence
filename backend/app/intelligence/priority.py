"""Inspection priority engine for scoring and ranking municipal areas for field inspection."""

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.models.confidence import AreaConfidenceScore
from app.models.geography import AdministrativeArea
from app.models.intelligence import AreaScore
from app.models.priority import AreaPriorityScore, PriorityConfiguration
from app.models.reporting import Report
from app.models.verification import ReportVerification

PRECISION_PRIORITY = Decimal("0.01")


def get_active_priority_config(
    db: Session,
    version: str | None = None,
) -> PriorityConfiguration:
    """Retrieve active or specified inspection priority model configuration."""
    stmt = select(PriorityConfiguration)
    if version:
        stmt = stmt.where(PriorityConfiguration.version == version)
    else:
        stmt = stmt.where(PriorityConfiguration.is_active.is_(True)).order_by(
            PriorityConfiguration.id.desc()
        )

    config = db.execute(stmt).scalars().first()
    if config is None:
        target = f"'{version}'" if version else "active"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection priority configuration {target} not found.",
        )
    return config


def list_priority_configurations(db: Session) -> list[PriorityConfiguration]:
    """List all versioned inspection priority configurations."""
    stmt = select(PriorityConfiguration).order_by(PriorityConfiguration.id.desc())
    return list(db.execute(stmt).scalars().all())


def calculate_area_inspection_priority(
    db: Session,
    area_id: uuid.UUID,
    config_version: str | None = None,
) -> AreaPriorityScore:
    """Calculate and persist deterministic municipal infrastructure inspection priority.

    Evaluation Framework:
    ---------------------
    1. SDI Severity Contribution (0-100 scale):
       - If current AreaScore exists: sdi_component = (area_score.score / 5.0) * 100
       - If no SDI exists: Component is unobserved.

    2. Observation Urgency / Staleness Contribution (0-100 scale):
       - Measures latency of latest unresolved deficiency report.
       - If reports exist: staleness_days = max(0, (now - latest_observed_at).days)
         staleness_component = min(100.0, (staleness_days / 30.0) * 100.0)
       - If never inspected: Base urgency of 50.0 is applied for baseline reconnaissance.

    3. Unresolved Deficiencies Volume (0-100 scale):
       - Evaluates count of distinct active canonical deficiency reports
         (status in 'SUBMITTED', 'UNDER_VERIFICATION', 'VERIFIED' and duplicate_of_id IS NULL).
       - Capped at unresolved_cap (default 20):
         unresolved_component = min(100.0, (unresolved_count / 20.0) * 100.0)

    4. Evidence Confidence Gap / Verification Need (0-100 scale):
       - If evidence confidence is low (e.g. citizen reports uncorroborated, zero verification),
         the need for municipal inspection is GREATER, not lesser.
       - gap_component = (1.0 - confidence_score) * 100 if confidence exists, else 75.0.

    5. Missing Data & Insufficient Data Handling:
       - Available factor weights are dynamically re-normalized over observed factors.
       - If area has 0 reports, no SDI, and has never been inspected:
         priority_score is NULL and priority_level is 'INSUFFICIENT_DATA'
         (with recommendation: 'BASELINE_INSPECTION').
    """
    area = db.execute(
        select(AdministrativeArea).where(AdministrativeArea.id == area_id)
    ).scalar_one_or_none()
    if area is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Administrative area '{area_id}' not found.",
        )

    config = get_active_priority_config(db, config_version)
    now = datetime.now(UTC)

    # 1. Fetch current SDI
    sdi_record = (
        db.execute(
            select(AreaScore).where(
                AreaScore.administrative_area_id == area_id, AreaScore.is_current.is_(True)
            )
        )
        .scalars()
        .first()
    )
    sdi_score = sdi_record.score if sdi_record else None

    # 2. Fetch current area confidence
    conf_record = (
        db.execute(
            select(AreaConfidenceScore).where(
                AreaConfidenceScore.administrative_area_id == area_id,
                AreaConfidenceScore.is_current.is_(True),
            )
        )
        .scalars()
        .first()
    )
    confidence_score = conf_record.confidence_score if conf_record else None
    completeness_pct = conf_record.completeness_pct if conf_record else None

    # 3. Query active unresolved canonical deficiency reports for this area
    unresolved_reports = list(
        db.execute(
            select(Report)
            .where(
                Report.administrative_area_id == area_id,
                Report.duplicate_of_id.is_(None),
                Report.status.in_(["SUBMITTED", "UNDER_VERIFICATION", "VERIFIED"]),
            )
            .order_by(Report.observed_at.desc())
        )
        .scalars()
        .all()
    )
    unresolved_count = len(unresolved_reports)
    latest_observation_at = unresolved_reports[0].observed_at if unresolved_reports else None

    # 4. Query last inspection date (most recent verification record in this area)
    last_verification = (
        db.execute(
            select(ReportVerification.verified_at)
            .join(Report, ReportVerification.report_id == Report.id)
            .where(Report.administrative_area_id == area_id)
            .order_by(ReportVerification.verified_at.desc())
        )
        .scalars()
        .first()
    )
    last_inspected_at = last_verification
    never_inspected = last_inspected_at is None

    # 5. Check if insufficient data
    if unresolved_count == 0 and sdi_score is None and never_inspected:
        calc_metadata: dict[str, Any] = {
            "components": {},
            "recommendation": "BASELINE_INSPECTION",
            "reason": (
                "Jurisdiction has no deficiency observations, no prior SDI, "
                "and has never been inspected."
            ),
        }
        priority_score_val = None
        priority_level = "INSUFFICIENT_DATA"
    else:
        # Calculate components and weighted sum
        components: dict[str, Any] = {}
        weighted_sum = Decimal("0.0000")
        available_weight = Decimal("0.0000")

        # A. SDI Severity Component
        if sdi_score is not None:
            dec_sdi = Decimal(str(sdi_score))
            if dec_sdi <= Decimal("5.0"):
                sdi_comp = (dec_sdi / Decimal("5.0")) * Decimal("100.0")
            else:
                sdi_comp = min(Decimal("100.0"), dec_sdi)
            w = config.sdi_weight
            weighted_sum += sdi_comp * w
            available_weight += w
            components["sdi"] = {
                "score": float(sdi_comp.quantize(PRECISION_PRIORITY, rounding=ROUND_HALF_UP)),
                "raw_sdi": float(sdi_score),
                "weight": float(w),
            }

        # Safe extraction of methodology metadata
        meta = config.methodology_metadata
        if isinstance(meta, str):
            import json

            try:
                meta = json.loads(meta)
            except Exception:
                meta = {}
        elif not isinstance(meta, dict):
            meta = {}

        # B. Urgency / Staleness Component
        staleness_max_days = Decimal(str(meta.get("staleness_max_days", 30)))
        if latest_observation_at is not None:
            latest_obs_utc = (
                latest_observation_at
                if latest_observation_at.tzinfo is not None
                else latest_observation_at.replace(tzinfo=UTC)
            )
            delta_days = Decimal(str(max(0, (now - latest_obs_utc).days)))
            urgency_comp = min(
                Decimal("100.0"), (delta_days / staleness_max_days) * Decimal("100.0")
            )
        elif never_inspected:
            urgency_comp = Decimal("50.0")  # Baseline reconnaissance need
        else:
            urgency_comp = Decimal("10.0")

        w_urg = config.urgency_weight
        weighted_sum += urgency_comp * w_urg
        available_weight += w_urg
        components["urgency"] = {
            "score": float(urgency_comp.quantize(PRECISION_PRIORITY, rounding=ROUND_HALF_UP)),
            "weight": float(w_urg),
        }

        # C. Unresolved Deficiencies Volume Component
        unres_cap = Decimal(str(meta.get("unresolved_cap", 20)))
        unres_comp = min(
            Decimal("100.0"),
            (Decimal(str(unresolved_count)) / unres_cap) * Decimal("100.0"),
        )
        w_unres = config.unresolved_reports_weight
        weighted_sum += unres_comp * w_unres
        available_weight += w_unres
        components["unresolved_deficiencies"] = {
            "score": float(unres_comp.quantize(PRECISION_PRIORITY, rounding=ROUND_HALF_UP)),
            "count": unresolved_count,
            "weight": float(w_unres),
        }

        # D. Confidence Gap / Verification Need Component
        if confidence_score is not None:
            conf_gap_comp = (Decimal("1.0") - Decimal(str(confidence_score))) * Decimal("100.0")
        else:
            conf_gap_comp = Decimal("75.0")  # High verification need due to missing evidence

        w_gap = config.confidence_gap_weight
        weighted_sum += conf_gap_comp * w_gap
        available_weight += w_gap
        components["confidence_gap"] = {
            "score": float(conf_gap_comp.quantize(PRECISION_PRIORITY, rounding=ROUND_HALF_UP)),
            "weight": float(w_gap),
        }

        # Re-normalize over available weights
        if available_weight > Decimal("0.0000"):
            raw_score = weighted_sum / available_weight
            priority_score_val = raw_score.quantize(PRECISION_PRIORITY, rounding=ROUND_HALF_UP)
        else:
            priority_score_val = Decimal("0.00")

        # Determine level based on thresholds
        thresholds = meta.get("thresholds", {})
        crit_t = Decimal(str(thresholds.get("CRITICAL", 80.0)))
        high_t = Decimal(str(thresholds.get("HIGH", 60.0)))
        med_t = Decimal(str(thresholds.get("MEDIUM", 40.0)))

        if priority_score_val >= crit_t:
            priority_level = "CRITICAL"
        elif priority_score_val >= high_t:
            priority_level = "HIGH"
        elif priority_score_val >= med_t:
            priority_level = "MEDIUM"
        else:
            priority_level = "LOW"

        calc_metadata = {
            "components": components,
            "available_weight_sum": float(available_weight),
            "recommendation": (
                "IMMEDIATE_FIELD_INSPECTION"
                if priority_level in ("CRITICAL", "HIGH")
                else "ROUTINE_MONITORING"
            ),
        }

    # 6. Archive prior active priority records for this area
    db.execute(
        update(AreaPriorityScore)
        .where(
            AreaPriorityScore.area_id == area_id,
            AreaPriorityScore.is_current.is_(True),
        )
        .values(is_current=False)
    )

    # 7. Persist new priority score record
    score_record = AreaPriorityScore(
        area_id=area_id,
        configuration_id=config.id,
        priority_score=priority_score_val,
        priority_level=priority_level,
        sdi_score=sdi_score,
        confidence_score=confidence_score,
        completeness_pct=completeness_pct,
        unresolved_reports_count=unresolved_count,
        latest_observation_at=latest_observation_at,
        last_inspected_at=last_inspected_at,
        never_inspected=never_inspected,
        calculation_metadata=calc_metadata,
        is_current=True,
        calculation_timestamp=datetime.now(UTC),
    )
    db.add(score_record)
    db.commit()
    db.refresh(score_record)

    return score_record


def get_current_area_priority(
    db: Session,
    area_id: uuid.UUID,
) -> AreaPriorityScore:
    """Retrieve current active priority score for an administrative area."""
    score = (
        db.execute(
            select(AreaPriorityScore)
            .options(
                joinedload(AreaPriorityScore.configuration),
                joinedload(AreaPriorityScore.area),
            )
            .where(
                AreaPriorityScore.area_id == area_id,
                AreaPriorityScore.is_current.is_(True),
            )
        )
        .scalars()
        .first()
    )

    if score is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No current inspection priority calculation found for area '{area_id}'.",
        )
    return score


def get_area_priority_history(
    db: Session,
    area_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AreaPriorityScore], int]:
    """Retrieve chronological history of inspection priority calculations for an area."""
    base_stmt = select(AreaPriorityScore).where(AreaPriorityScore.area_id == area_id)
    total = db.execute(select(func.count()).select_from(base_stmt.subquery())).scalar_one()

    items = list(
        db.execute(
            base_stmt.options(
                joinedload(AreaPriorityScore.configuration),
                joinedload(AreaPriorityScore.area),
            )
            .order_by(
                AreaPriorityScore.is_current.desc(),
                AreaPriorityScore.calculation_timestamp.desc(),
                AreaPriorityScore.id.desc(),
            )
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )
    return items, total


def list_area_priorities(
    db: Session,
    priority_level: str | None = None,
    area_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "score_desc",
) -> tuple[list[tuple[AreaPriorityScore, AdministrativeArea]], int]:
    """Query current area inspection priorities with filtering and pagination."""
    stmt = (
        select(AreaPriorityScore, AdministrativeArea)
        .join(AdministrativeArea, AreaPriorityScore.area_id == AdministrativeArea.id)
        .options(joinedload(AreaPriorityScore.configuration))
        .where(AreaPriorityScore.is_current.is_(True))
    )

    if priority_level:
        stmt = stmt.where(AreaPriorityScore.priority_level == priority_level.upper())
    if area_type:
        stmt = stmt.where(AdministrativeArea.area_type == area_type.lower())

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    if sort_by == "score_asc":
        stmt = stmt.order_by(
            AreaPriorityScore.priority_score.asc().nulls_last(),
            AreaPriorityScore.id.desc(),
        )
    elif sort_by == "unresolved_desc":
        stmt = stmt.order_by(
            AreaPriorityScore.unresolved_reports_count.desc(),
            AreaPriorityScore.id.desc(),
        )
    else:  # score_desc (default)
        stmt = stmt.order_by(
            AreaPriorityScore.priority_score.desc().nulls_last(),
            AreaPriorityScore.id.desc(),
        )

    results = list(db.execute(stmt.limit(limit).offset(offset)).all())
    return [(row[0], row[1]) for row in results], total
