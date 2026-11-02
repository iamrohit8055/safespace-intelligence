"""Service layer implementing spatial duplicate candidate detection, review, and linking."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from geoalchemy2 import Geography
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.geometry import parse_point_geometry
from app.models.duplicates import (
    DuplicateCandidate,
    DuplicateDetectionConfiguration,
    DuplicateReviewHistory,
)
from app.models.iam import User
from app.models.reporting import Report
from app.schemas.duplicates import DuplicateReviewRequest

ELIGIBLE_REPORT_STATUSES = ("SUBMITTED", "UNDER_VERIFICATION", "VERIFIED")


def get_active_duplicate_config(
    db: Session,
    version: str | None = None,
) -> DuplicateDetectionConfiguration:
    """Retrieve the active duplicate detection configuration or a specific version."""
    stmt = select(DuplicateDetectionConfiguration)
    if version:
        stmt = stmt.where(DuplicateDetectionConfiguration.version == version)
    else:
        stmt = stmt.where(DuplicateDetectionConfiguration.is_active.is_(True)).order_by(
            DuplicateDetectionConfiguration.id.desc()
        )

    config = db.execute(stmt).scalars().first()
    if config is None:
        target = f"'{version}'" if version else "active"
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Duplicate detection configuration {target} not found.",
        )
    return config


def detect_candidates_for_report(
    db: Session,
    report_id: uuid.UUID,
    config_version: str | None = None,
) -> list[DuplicateCandidate]:
    """Detect potential duplicate candidates for a specific report using PostGIS geography.

    Rules:
        - Same report category.
        - Distance within configured spatial radius in metres.
        - Submission time within configured time window days.
        - Report is active (SUBMITTED, UNDER_VERIFICATION, VERIFIED).
        - Excludes already linked duplicate reports (duplicate_of_id IS NOT NULL).
        - Excludes self-matches.
        - Ensures candidate pair ordering (first_report_id < second_report_id).
        - Idempotent insertion (skips existing candidate pairs).
    """
    config = get_active_duplicate_config(db, config_version)
    target_report = db.execute(select(Report).where(Report.id == report_id)).scalar_one_or_none()
    if target_report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    if (
        target_report.status not in ELIGIBLE_REPORT_STATUSES
        or target_report.duplicate_of_id is not None
    ):
        return []

    radius_m = float(config.spatial_radius_metres)
    window_delta = timedelta(days=config.time_window_days)
    min_time = target_report.submitted_at - window_delta
    max_time = target_report.submitted_at + window_delta

    # Spatial query with geography ST_DWithin and metric ST_Distance
    target_lon, target_lat = parse_point_geometry(target_report.location)
    target_geog = func.cast(
        func.ST_SetSRID(func.ST_MakePoint(target_lon, target_lat), 4326),
        Geography,
    )
    candidate_geog = func.cast(Report.location, Geography)

    stmt = (
        select(
            Report.id,
            func.ST_Distance(candidate_geog, target_geog).label("distance_metres"),
            Report.submitted_at,
        )
        .where(
            Report.id != target_report.id,
            Report.category_id == target_report.category_id,
            Report.status.in_(ELIGIBLE_REPORT_STATUSES),
            Report.duplicate_of_id.is_(None),
            Report.submitted_at >= min_time,
            Report.submitted_at <= max_time,
            func.ST_DWithin(candidate_geog, target_geog, radius_m),
        )
        .order_by("distance_metres")
    )

    matches = db.execute(stmt).all()
    created_candidates: list[DuplicateCandidate] = []

    for match_id, distance_val, match_submitted_at in matches:
        first_id, second_id = (
            (target_report.id, match_id)
            if target_report.id < match_id
            else (match_id, target_report.id)
        )

        existing = db.execute(
            select(DuplicateCandidate).where(
                DuplicateCandidate.first_report_id == first_id,
                DuplicateCandidate.second_report_id == second_id,
            )
        ).scalar_one_or_none()

        if existing:
            created_candidates.append(existing)
            continue

        time_diff = int(abs((target_report.submitted_at - match_submitted_at).total_seconds()))
        candidate = DuplicateCandidate(
            first_report_id=first_id,
            second_report_id=second_id,
            distance_metres=Decimal(str(round(distance_val, 2))),
            time_difference_seconds=time_diff,
            rule_version=config.version,
            review_status="PENDING",
        )
        db.add(candidate)
        db.flush()
        created_candidates.append(candidate)

    db.commit()
    return created_candidates


def detect_candidates_in_area(
    db: Session,
    area_id: uuid.UUID | None = None,
    config_version: str | None = None,
) -> tuple[int, int]:
    """Execute batch candidate discovery for an administrative area or globally.

    Returns:
        tuple[int, int]: (candidates_evaluated, new_candidates_created)
    """
    config = get_active_duplicate_config(db, config_version)
    radius_m = float(config.spatial_radius_metres)

    from sqlalchemy.orm import aliased

    Report2 = aliased(Report)

    r1_geog = func.cast(Report.location, Geography)
    r2_geog = func.cast(Report2.location, Geography)

    # Time difference condition in days
    time_window_seconds = config.time_window_days * 86400

    filters = [
        Report.id < Report2.id,
        Report.category_id == Report2.category_id,
        Report.status.in_(ELIGIBLE_REPORT_STATUSES),
        Report2.status.in_(ELIGIBLE_REPORT_STATUSES),
        Report.duplicate_of_id.is_(None),
        Report2.duplicate_of_id.is_(None),
        func.abs(func.extract("epoch", Report.submitted_at - Report2.submitted_at))
        <= time_window_seconds,
        func.ST_DWithin(r1_geog, r2_geog, radius_m),
    ]

    if area_id is not None:
        filters.append(
            or_(
                Report.administrative_area_id == area_id,
                Report2.administrative_area_id == area_id,
            )
        )

    stmt = select(
        Report.id.label("r1_id"),
        Report2.id.label("r2_id"),
        func.ST_Distance(r1_geog, r2_geog).label("distance_metres"),
        func.abs(func.extract("epoch", Report.submitted_at - Report2.submitted_at)).label(
            "time_diff_sec"
        ),
    ).where(*filters)

    rows = db.execute(stmt).all()
    evaluated = len(rows)
    new_count = 0

    for r1_id, r2_id, dist_m, time_diff in rows:
        existing = db.execute(
            select(DuplicateCandidate).where(
                DuplicateCandidate.first_report_id == r1_id,
                DuplicateCandidate.second_report_id == r2_id,
            )
        ).scalar_one_or_none()

        if existing is None:
            candidate = DuplicateCandidate(
                first_report_id=r1_id,
                second_report_id=r2_id,
                distance_metres=Decimal(str(round(dist_m, 2))),
                time_difference_seconds=int(time_diff),
                rule_version=config.version,
                review_status="PENDING",
            )
            db.add(candidate)
            new_count += 1

    db.commit()
    return evaluated, new_count


def get_duplicate_candidates(
    db: Session,
    review_status: str | None = None,
    report_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[DuplicateCandidate], int]:
    """Retrieve paginated duplicate candidates with optional filtering."""
    base_stmt = select(DuplicateCandidate)
    count_stmt = select(func.count(DuplicateCandidate.id))

    filters = []
    if review_status:
        filters.append(DuplicateCandidate.review_status == review_status)
    if report_id:
        filters.append(
            or_(
                DuplicateCandidate.first_report_id == report_id,
                DuplicateCandidate.second_report_id == report_id,
            )
        )

    if filters:
        base_stmt = base_stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    total = db.execute(count_stmt).scalar_one()
    items = list(
        db.execute(
            base_stmt.order_by(DuplicateCandidate.detected_at.desc()).limit(limit).offset(offset)
        )
        .scalars()
        .all()
    )
    return items, total


def get_duplicate_candidate_by_id(db: Session, candidate_id: uuid.UUID) -> DuplicateCandidate:
    """Retrieve a single duplicate candidate by ID or raise 404."""
    candidate = db.execute(
        select(DuplicateCandidate).where(DuplicateCandidate.id == candidate_id)
    ).scalar_one_or_none()
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Duplicate candidate record not found.",
        )
    return candidate


def select_canonical_and_duplicate(
    r1: Report,
    r2: Report,
    explicit_canonical_id: uuid.UUID | None = None,
) -> tuple[Report, Report]:
    """Select the canonical report and duplicate report according to approved policy.

    Policy:
        1. If explicit_canonical_id is provided, validate it belongs to the pair and is not
           ARCHIVED, REJECTED, or already a duplicate.
        2. Never select an ARCHIVED or REJECTED report as canonical.
        3. Never select an already linked duplicate (duplicate_of_id IS NOT NULL) as canonical.
        4. Prefer a currently VERIFIED eligible report whenever one exists
           (prevents SDI suppression).
        5. If multiple VERIFIED reports exist, select the earliest submitted report.
        6. If no VERIFIED report exists, select the earliest eligible report.
        7. Deterministic tie-breaker: UUID string comparison.
    """
    if explicit_canonical_id is not None:
        if explicit_canonical_id == r1.id:
            canonical, duplicate = r1, r2
        elif explicit_canonical_id == r2.id:
            canonical, duplicate = r2, r1
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provided canonical_report_id is not part of this candidate pair.",
            )
        if canonical.status in ("ARCHIVED", "REJECTED"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot select report with status '{canonical.status}' as canonical. "
                    "ARCHIVED or REJECTED reports cannot serve as canonical."
                ),
            )
        if canonical.duplicate_of_id is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected canonical report is itself already a linked duplicate.",
            )
        return canonical, duplicate

    def is_eligible(r: Report) -> bool:
        return r.status not in ("ARCHIVED", "REJECTED") and r.duplicate_of_id is None

    r1_eligible = is_eligible(r1)
    r2_eligible = is_eligible(r2)

    if not r1_eligible and not r2_eligible:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Cannot confirm duplicate: neither report is eligible to serve as canonical. "
                "ARCHIVED or REJECTED reports cannot serve as canonical."
            ),
        )

    if r1_eligible and not r2_eligible:
        return r1, r2
    if r2_eligible and not r1_eligible:
        return r2, r1

    # Both reports are eligible to be canonical
    r1_verified = r1.status == "VERIFIED"
    r2_verified = r2.status == "VERIFIED"

    # 1. Prefer a currently VERIFIED eligible report whenever one exists
    if r1_verified and not r2_verified:
        return r1, r2
    if r2_verified and not r1_verified:
        return r2, r1

    # 2. Both are VERIFIED or neither is VERIFIED: select earliest submitted report
    if r1.submitted_at < r2.submitted_at:
        return r1, r2
    if r2.submitted_at < r1.submitted_at:
        return r2, r1

    # 3. Deterministic tie-breaker: UUID string comparison
    return (r1, r2) if str(r1.id) < str(r2.id) else (r2, r1)


def review_duplicate_candidate(
    db: Session,
    candidate_id: uuid.UUID,
    payload: DuplicateReviewRequest,
    reviewer: User,
) -> tuple[DuplicateCandidate, DuplicateReviewHistory]:
    """Review a duplicate candidate pair and establish canonical duplicate links.

    Transactional safety & concurrency:
        - Locks candidate record and both reports using SELECT ... FOR UPDATE.
        - Validates category compatibility and canonical integrity.
        - Re-points any downstream duplicate references to avoid multi-hop chains.
        - Preserves append-only review audit history.
        - Rolls back entire transaction if any step fails.
    """
    valid_decisions = ("CONFIRMED_DUPLICATE", "NOT_DUPLICATE", "NEEDS_REVIEW")
    if payload.decision not in valid_decisions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid review decision '{payload.decision}'. Allowed: {valid_decisions}",
        )

    try:
        candidate = db.execute(
            select(DuplicateCandidate)
            .where(DuplicateCandidate.id == candidate_id)
            .with_for_update()
        ).scalar_one_or_none()
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Duplicate candidate not found.",
            )

        r1 = db.execute(
            select(Report).where(Report.id == candidate.first_report_id).with_for_update()
        ).scalar_one_or_none()
        r2 = db.execute(
            select(Report).where(Report.id == candidate.second_report_id).with_for_update()
        ).scalar_one_or_none()

        if not r1 or not r2:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or both candidate reports no longer exist.",
            )

        # Validate same category
        if r1.category_id != r2.category_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot confirm duplicate: reports belong to incompatible categories.",
            )

        now = datetime.now(UTC)

        if payload.decision == "CONFIRMED_DUPLICATE":
            # Determine canonical and duplicate reports via approved policy
            canonical, duplicate = select_canonical_and_duplicate(
                r1, r2, payload.canonical_report_id
            )

            # Rule: canonical report cannot itself be a duplicate
            if canonical.duplicate_of_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Selected canonical report is itself already a linked duplicate.",
                )

            # Rule: prevent self-reference
            if duplicate.id == canonical.id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Report cannot be linked as a duplicate of itself.",
                )

            # Rule: duplicate report cannot already have a different canonical parent
            if duplicate.duplicate_of_id is not None and duplicate.duplicate_of_id != canonical.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Report is already linked to a different canonical report.",
                )

            # Re-point reports pointing to duplicate to point to canonical
            db.execute(
                update(Report)
                .where(Report.duplicate_of_id == duplicate.id)
                .values(duplicate_of_id=canonical.id)
            )

            # Link duplicate report to canonical report
            duplicate.duplicate_of_id = canonical.id

            # Update candidate record
            candidate.review_status = "CONFIRMED_DUPLICATE"
            candidate.reviewer_id = reviewer.id
            candidate.reviewed_at = now
            candidate.review_reason = payload.reason

            # Record review audit history
            history = DuplicateReviewHistory(
                candidate_id=candidate.id,
                duplicate_report_id=duplicate.id,
                canonical_report_id=canonical.id,
                decision="CONFIRMED_DUPLICATE",
                reason=payload.reason,
                reviewer_id=reviewer.id,
                reviewed_at=now,
            )
            db.add(history)
            db.commit()
            return candidate, history

        else:
            # NOT_DUPLICATE or NEEDS_REVIEW: do not modify duplicate_of_id
            candidate.review_status = payload.decision
            candidate.reviewer_id = reviewer.id
            candidate.reviewed_at = now
            candidate.review_reason = payload.reason

            history = DuplicateReviewHistory(
                candidate_id=candidate.id,
                duplicate_report_id=r2.id,
                canonical_report_id=r1.id,
                decision=payload.decision,
                reason=payload.reason,
                reviewer_id=reviewer.id,
                reviewed_at=now,
            )
            db.add(history)
            db.commit()
            return candidate, history

    except Exception:
        db.rollback()
        raise


def get_report_duplicate_history(
    db: Session,
    report_id: uuid.UUID,
) -> list[DuplicateReviewHistory]:
    """Retrieve audit history of duplicate decisions involving a specific report."""
    stmt = (
        select(DuplicateReviewHistory)
        .where(
            or_(
                DuplicateReviewHistory.duplicate_report_id == report_id,
                DuplicateReviewHistory.canonical_report_id == report_id,
            )
        )
        .order_by(DuplicateReviewHistory.reviewed_at.desc())
    )
    return list(db.execute(stmt).scalars().all())
