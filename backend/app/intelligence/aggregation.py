"""Aggregation logic querying eligible verified reports for area-level SDI calculation."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.reporting import Report
from app.models.verification import ReportVerification


def get_eligible_verified_reports(
    db: Session,
    area_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Retrieve all eligible verified deficiency reports within an administrative area.

    Eligibility Rules:
        - Current report status must be VERIFIED.
        - Must have a matching administrative_area_id.
        - Must not be marked as a duplicate (duplicate_of_id IS NULL).
        - Must have an associated VERIFIED decision in report_verifications.
        - Disambiguates multiple verifications by selecting the latest verified severity.

    Args:
        db: Active SQLAlchemy database session.
        area_id: Unique UUID of the target administrative area.

    Returns:
        list[dict[str, Any]]: List of dicts containing report_id, category_id,
            and verified_severity.
    """
    stmt = (
        select(
            Report.id,
            Report.category_id,
            ReportVerification.verified_severity,
        )
        .join(
            ReportVerification,
            ReportVerification.report_id == Report.id,
        )
        .where(
            Report.administrative_area_id == area_id,
            Report.status == "VERIFIED",
            Report.duplicate_of_id.is_(None),
            ReportVerification.decision == "VERIFIED",
            ReportVerification.verified_severity.is_not(None),
        )
        .order_by(
            Report.id,
            ReportVerification.verified_at.desc(),
            ReportVerification.id.desc(),
        )
        .distinct(Report.id)
    )

    rows = db.execute(stmt).all()
    return [
        {
            "report_id": row[0],
            "category_id": row[1],
            "verified_severity": row[2],
        }
        for row in rows
    ]


def group_observations_by_category(
    eligible_reports: list[dict[str, Any]],
) -> dict[int, list[int]]:
    """Group verified severities by report category ID.

    Args:
        eligible_reports: List of eligible report dictionaries.

    Returns:
        dict[int, list[int]]: Mapping of category_id -> list of verified severity scores.
    """
    grouped: dict[int, list[int]] = {}
    for r in eligible_reports:
        cid = r["category_id"]
        sev = r["verified_severity"]
        grouped.setdefault(cid, []).append(sev)
    return grouped
