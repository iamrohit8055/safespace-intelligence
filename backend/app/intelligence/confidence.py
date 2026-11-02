"""Individual report evidence confidence calculation, factor scoring, and persistence."""

import uuid
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.models.confidence import (
    ConfidenceConfiguration,
    ReportConfidenceComponent,
    ReportConfidenceScore,
)
from app.models.reporting import Report

PRECISION_SCORE = Decimal("0.0001")
PRECISION_PCT = Decimal("0.01")


def get_active_confidence_config(
    db: Session,
    version: str | None = None,
) -> ConfidenceConfiguration:
    """Retrieve versioned confidence configuration with eager-loaded factors."""
    stmt = select(ConfidenceConfiguration).options(
        joinedload(ConfidenceConfiguration.factors),
    )
    if version:
        stmt = stmt.where(ConfidenceConfiguration.version == version)
    else:
        stmt = stmt.where(ConfidenceConfiguration.is_active.is_(True)).order_by(
            ConfidenceConfiguration.id.desc()
        )

    config = db.execute(stmt).scalars().first()
    if config is None:
        target = f"'{version}'" if version else "active"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Confidence configuration {target} not found.",
        )
    return config


def _score_evidence_freshness(report: Report) -> Decimal:
    """Evaluate observation timeliness latency between observed_at and submitted_at.

    Source & Data Integrity:
        - `observed_at` is the physical defect observation timestamp reported by the citizen.
        - Schema validation and report services enforce that `observed_at <= submitted_at`,
          preventing future timestamps while defaulting to `submitted_at` if omitted.
        - Latency = max(0.0, (report.submitted_at - report.observed_at).total_seconds()).
        - Shorter observation latency indicates higher temporal fidelity and lower probability
          of intervening physical changes or repairs.

    Decay Schedule:
        - < 24 hours (86,400s): 1.0000
        - 1 to 3 days (259,200s): 0.8500
        - 3 to 7 days (604,800s): 0.7000
        - 7 to 30 days (2,592,000s): 0.5000
        - > 30 days: 0.3000
    """
    delta = max(0.0, (report.submitted_at - report.observed_at).total_seconds())
    if delta < 86400:  # < 24 hours
        return Decimal("1.0000")
    elif delta < 259200:  # 1 - 3 days
        return Decimal("0.8500")
    elif delta < 604800:  # 3 - 7 days
        return Decimal("0.7000")
    elif delta < 2592000:  # 7 - 30 days
        return Decimal("0.5000")
    else:
        return Decimal("0.3000")


def _score_independent_corroboration(report: Report, db: Session) -> Decimal:
    """Evaluate independent corroboration from distinct reporters.

    Evaluated exclusively using confirmed duplicate links.

    Methodology & Integrity Rules:
        - Only confirmed duplicate links (reports explicitly linked via duplicate_of_id)
          are considered corroborating evidence.
        - Automatically detected proximity candidates (DuplicateCandidate) are NOT treated
          as independently verified evidence because they lack human moderation confirmation.
        - Only distinct, unique reporters are counted; repeated reports by the same reporter
          do not increase the corroboration score.
        - The target report's own reporter is strictly excluded.

    Heuristic Scoring Scale:
        - 0 independent corroborating reporters: 0.5000 (baseline single-source observation)
        - 1 independent corroborating reporter: 0.8000
        - >= 2 independent corroborating reporters: 1.0000

    Limits of the Corroboration Heuristic:
        - Corroboration relies on manual moderation linking confirmed duplicate reports.
        - It does not account for correlated reporting bias, social media virality, or potential
          collusion among reporters.
        - Absence of corroboration (0.5000) does not indicate an inaccurate report, only that
          no secondary observation has been confirmed by moderation yet.
    """
    corroborating_report_ids = set()

    # If this report is a duplicate pointing to a canonical parent
    if report.duplicate_of_id is not None:
        corroborating_report_ids.add(report.duplicate_of_id)
        # Sibling reports linked to the same canonical parent
        sibling_ids = (
            db.execute(
                select(Report.id).where(
                    Report.duplicate_of_id == report.duplicate_of_id,
                    Report.id != report.id,
                    Report.status.not_in(["ARCHIVED", "REJECTED"]),
                )
            )
            .scalars()
            .all()
        )
        corroborating_report_ids.update(sibling_ids)
    else:
        # If this report is canonical, find all confirmed duplicates pointing to it
        child_ids = (
            db.execute(
                select(Report.id).where(
                    Report.duplicate_of_id == report.id,
                    Report.id != report.id,
                    Report.status.not_in(["ARCHIVED", "REJECTED"]),
                )
            )
            .scalars()
            .all()
        )
        corroborating_report_ids.update(child_ids)

    if not corroborating_report_ids:
        return Decimal("0.5000")

    # Distinct reporters strictly excluding the author of the target report
    distinct_reporters = (
        db.execute(
            select(Report.reporter_id)
            .where(
                Report.id.in_(corroborating_report_ids),
                Report.reporter_id != report.reporter_id,
            )
            .distinct()
        )
        .scalars()
        .all()
    )

    distinct_count = len(distinct_reporters)
    if distinct_count >= 2:
        return Decimal("1.0000")
    elif distinct_count == 1:
        return Decimal("0.8000")
    else:
        return Decimal("0.5000")


def calculate_report_confidence(
    db: Session,
    report_id: uuid.UUID,
    config_version: str | None = None,
) -> ReportConfidenceScore:
    """Calculate reproducible, versioned evidence confidence assessment for a report.

    Formula:
        Confidence = SUM(observed_factor_score * factor_weight) / SUM(observed_factor_weights)
        Normalized to 0.0000 - 1.0000 scale.
        If no factors are measurable, returns NULL.
    """
    report = db.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    config = get_active_confidence_config(db, config_version)
    now = datetime.now(UTC)

    factor_evaluations: list[dict[str, Any]] = []
    observed_weight_sum = Decimal("0.0000")

    for factor in config.factors:
        code = factor.factor_code
        assigned_w = Decimal(str(factor.weight))

        if not factor.is_measurable:
            factor_evaluations.append(
                {
                    "factor_code": code,
                    "score": None,
                    "assigned_weight": assigned_w,
                    "normalized_weight": None,
                    "weighted_contribution": None,
                    "availability_state": "UNAVAILABLE",
                    "unavailability_reason": factor.unavailability_reason,
                }
            )
            continue

        # Evaluate measurable factor
        score: Decimal | None = None
        if code == "VERIFICATION_COMPLETENESS":
            # Note-length based confidence scoring removed per architectural correction.
            # Structured verification completeness criteria are unavailable in current data model.
            factor_evaluations.append(
                {
                    "factor_code": code,
                    "score": None,
                    "assigned_weight": assigned_w,
                    "normalized_weight": None,
                    "weighted_contribution": None,
                    "availability_state": "UNAVAILABLE",
                    "unavailability_reason": (
                        "Structured verification completeness criteria unavailable in current "
                        "data model; subjective note-length scoring removed"
                    ),
                }
            )
            continue
        elif code == "EVIDENCE_FRESHNESS":
            score = _score_evidence_freshness(report)
        elif code == "INDEPENDENT_CORROBORATION":
            score = _score_independent_corroboration(report, db)
        else:
            # Unknown measurable factor without evaluator -> mark unavailable
            factor_evaluations.append(
                {
                    "factor_code": code,
                    "score": None,
                    "assigned_weight": assigned_w,
                    "normalized_weight": None,
                    "weighted_contribution": None,
                    "availability_state": "UNAVAILABLE",
                    "unavailability_reason": f"No evaluation logic for factor {code}",
                }
            )
            continue

        observed_weight_sum += assigned_w
        factor_evaluations.append(
            {
                "factor_code": code,
                "score": score,
                "assigned_weight": assigned_w,
                "normalized_weight": None,  # Computed below
                "weighted_contribution": None,  # Computed below
                "availability_state": "OBSERVED",
                "unavailability_reason": None,
            }
        )

    total_factors_count = len(config.factors)
    observed_factors = [f for f in factor_evaluations if f["availability_state"] == "OBSERVED"]
    available_factors_count = len(observed_factors)

    if total_factors_count > 0:
        completeness_pct = (
            (Decimal(available_factors_count) / Decimal(total_factors_count)) * Decimal("100.00")
        ).quantize(PRECISION_PCT, rounding=ROUND_HALF_UP)
    else:
        completeness_pct = Decimal("0.00")

    confidence_score: Decimal | None = None
    if observed_weight_sum > Decimal("0.0000") and observed_factors:
        total_weighted_sum = Decimal("0.0000")
        for f in observed_factors:
            norm_w = (f["assigned_weight"] / observed_weight_sum).quantize(
                PRECISION_SCORE, rounding=ROUND_HALF_UP
            )
            f["normalized_weight"] = norm_w
            contribution = (f["score"] * norm_w).quantize(PRECISION_SCORE, rounding=ROUND_HALF_UP)
            f["weighted_contribution"] = contribution
            total_weighted_sum += contribution
        confidence_score = min(Decimal("1.0000"), max(Decimal("0.0000"), total_weighted_sum))

    try:
        # Atomic archival: mark existing active scores for this report and config as inactive
        db.execute(
            update(ReportConfidenceScore)
            .where(
                ReportConfidenceScore.report_id == report.id,
                ReportConfidenceScore.configuration_id == config.id,
                ReportConfidenceScore.is_current.is_(True),
            )
            .values(is_current=False)
        )

        score_record = ReportConfidenceScore(
            report_id=report.id,
            configuration_id=config.id,
            confidence_score=confidence_score,
            completeness_pct=completeness_pct,
            available_factors_count=available_factors_count,
            total_factors_count=total_factors_count,
            is_current=True,
            factor_details={
                f["factor_code"]: {
                    "score": float(f["score"]) if f["score"] is not None else None,
                    "state": f["availability_state"],
                    "reason": f["unavailability_reason"],
                }
                for f in factor_evaluations
            },
            calculation_timestamp=now,
        )
        db.add(score_record)
        db.flush()

        for f in factor_evaluations:
            comp = ReportConfidenceComponent(
                report_confidence_id=score_record.id,
                factor_code=f["factor_code"],
                factor_score=f["score"],
                assigned_weight=f["assigned_weight"],
                normalized_weight=f["normalized_weight"],
                weighted_contribution=f["weighted_contribution"],
                availability_state=f["availability_state"],
                unavailability_reason=f["unavailability_reason"],
            )
            db.add(comp)

        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_current_report_confidence(db, report.id, config.version)  # type: ignore[return-value]


def get_current_report_confidence(
    db: Session,
    report_id: uuid.UUID,
    config_version: str | None = None,
) -> ReportConfidenceScore | None:
    """Retrieve active current confidence assessment for a report."""
    stmt = (
        select(ReportConfidenceScore)
        .options(joinedload(ReportConfidenceScore.components))
        .join(ConfidenceConfiguration)
        .where(
            ReportConfidenceScore.report_id == report_id,
            ReportConfidenceScore.is_current.is_(True),
        )
    )
    if config_version:
        stmt = stmt.where(ConfidenceConfiguration.version == config_version)
    else:
        stmt = stmt.where(ConfidenceConfiguration.is_active.is_(True)).order_by(
            ReportConfidenceScore.calculation_timestamp.desc()
        )

    return db.execute(stmt).scalars().first()


def get_report_confidence_history(
    db: Session,
    report_id: uuid.UUID,
) -> list[ReportConfidenceScore]:
    """Retrieve chronological confidence assessment history for a report."""
    stmt = (
        select(ReportConfidenceScore)
        .options(joinedload(ReportConfidenceScore.components))
        .where(ReportConfidenceScore.report_id == report_id)
        .order_by(ReportConfidenceScore.calculation_timestamp.desc())
    )
    return list(db.execute(stmt).scalars().unique().all())
