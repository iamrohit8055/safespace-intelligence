"""Service layer implementing report moderation, verification lifecycle, and audit trail."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.iam import User
from app.models.reporting import Report
from app.models.verification import ReportStatusHistory, ReportVerification
from app.schemas.verification import (
    RejectReportRequest,
    ReopenReportRequest,
    VerifyReportRequest,
)
from app.services.notifications import create_notification
from app.services.reports import get_report_by_id


def get_pending_reports_queue(
    db: Session,
    limit: int,
    offset: int,
) -> tuple[list[Report], int]:
    """Retrieve FIFO queue of pending reports in SUBMITTED status.

    Eager-loads related category and administrative area to prevent N+1 queries.
    Orders deterministically by submitted_at ASC, id ASC.

    Args:
        db: Active SQLAlchemy database session.
        limit: Maximum number of records to return.
        offset: Number of records to skip.

    Returns:
        tuple[list[Report], int]: (reports on page, total count of pending reports).
    """
    count_stmt = select(func.count(Report.id)).where(Report.status == "SUBMITTED")
    total = db.execute(count_stmt).scalar_one()

    stmt = (
        select(Report)
        .options(
            joinedload(Report.category),
            joinedload(Report.administrative_area),
        )
        .where(Report.status == "SUBMITTED")
        .order_by(Report.submitted_at.asc(), Report.id.asc())
        .limit(limit)
        .offset(offset)
    )
    items = list(db.execute(stmt).scalars().all())
    return items, total


def start_report_verification(
    db: Session,
    report_id: uuid.UUID,
    verifier: User,
) -> Report:
    """Transition a report from SUBMITTED to UNDER_VERIFICATION with row locking.

    Uses SELECT ... FOR UPDATE to prevent race conditions during concurrent attempts.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.
        verifier: Authenticated verifier or admin User.

    Returns:
        Report: Updated Report entity.

    Raises:
        HTTPException: 404 if not found, 409 if status is not SUBMITTED.
    """
    try:
        report = db.execute(
            select(Report).where(Report.id == report_id).with_for_update()
        ).scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        if report.status != "SUBMITTED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot start verification: report is currently '{report.status}', "
                    "expected 'SUBMITTED'."
                ),
            )

        report.status = "UNDER_VERIFICATION"

        history = ReportStatusHistory(
            report_id=report.id,
            from_status="SUBMITTED",
            to_status="UNDER_VERIFICATION",
            changed_by_user_id=verifier.id,
            reason="Verification initiated by moderator",
        )
        db.add(history)

        create_notification(
            db,
            recipient_id=report.reporter_id,
            notification_type="REPORT_VERIFICATION_STARTED",
            title="Verification Started",
            message=f"Field verification has started for your report '{report.title}'.",
            resource_type="report",
            resource_id=report.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_report_by_id(db, report_id)


def verify_report(
    db: Session,
    report_id: uuid.UUID,
    payload: VerifyReportRequest,
    verifier: User,
) -> Report:
    """Approve and verify an UNDER_VERIFICATION report with deficiency severity scoring.

    Atomically records append-only ReportVerification and ReportStatusHistory records.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.
        payload: Validated verification request with severity (1-5).
        verifier: Authenticated verifier or admin User.

    Returns:
        Report: Updated Report entity with status VERIFIED.

    Raises:
        HTTPException: 404 if not found, 409 if not currently UNDER_VERIFICATION.
    """
    try:
        report = db.execute(
            select(Report).where(Report.id == report_id).with_for_update()
        ).scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        if report.status != "UNDER_VERIFICATION":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot verify report: report is currently '{report.status}', "
                    "expected 'UNDER_VERIFICATION'."
                ),
            )

        report.status = "VERIFIED"

        verification = ReportVerification(
            report_id=report.id,
            verifier_id=verifier.id,
            decision="VERIFIED",
            verified_severity=payload.verified_severity,
            verification_notes=payload.verification_notes,
            rejection_reason=None,
            data_confidence_score=None,
            verified_at=datetime.now(UTC),
        )
        db.add(verification)

        history = ReportStatusHistory(
            report_id=report.id,
            from_status="UNDER_VERIFICATION",
            to_status="VERIFIED",
            changed_by_user_id=verifier.id,
            reason=payload.verification_notes or "Report verified with severity score",
        )
        db.add(history)

        create_notification(
            db,
            recipient_id=report.reporter_id,
            notification_type="REPORT_VERIFIED",
            title="Report Verified",
            message=(
                f"Your report '{report.title}' has been verified with "
                f"severity level {payload.verified_severity}."
            ),
            resource_type="report",
            resource_id=report.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_report_by_id(db, report_id)


def reject_report(
    db: Session,
    report_id: uuid.UUID,
    payload: RejectReportRequest,
    verifier: User,
) -> Report:
    """Reject an UNDER_VERIFICATION report with mandatory rejection reasoning.

    Atomically records append-only ReportVerification and ReportStatusHistory records.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.
        payload: Validated rejection request with reason code.
        verifier: Authenticated verifier or admin User.

    Returns:
        Report: Updated Report entity with status REJECTED.

    Raises:
        HTTPException: 404 if not found, 409 if not currently UNDER_VERIFICATION.
    """
    try:
        report = db.execute(
            select(Report).where(Report.id == report_id).with_for_update()
        ).scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        if report.status != "UNDER_VERIFICATION":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot reject report: report is currently '{report.status}', "
                    "expected 'UNDER_VERIFICATION'."
                ),
            )

        clean_reason = payload.rejection_reason.strip()
        report.status = "REJECTED"

        verification = ReportVerification(
            report_id=report.id,
            verifier_id=verifier.id,
            decision="REJECTED",
            rejection_reason=clean_reason,
            verified_severity=None,
            verification_notes=payload.verification_notes,
            data_confidence_score=None,
            verified_at=datetime.now(UTC),
        )
        db.add(verification)

        history = ReportStatusHistory(
            report_id=report.id,
            from_status="UNDER_VERIFICATION",
            to_status="REJECTED",
            changed_by_user_id=verifier.id,
            reason=f"Rejected: {clean_reason}",
        )
        db.add(history)

        create_notification(
            db,
            recipient_id=report.reporter_id,
            notification_type="REPORT_REJECTED",
            title="Report Rejected",
            message=f"Your report '{report.title}' was rejected: {clean_reason}.",
            resource_type="report",
            resource_id=report.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_report_by_id(db, report_id)


def reopen_report(
    db: Session,
    report_id: uuid.UUID,
    payload: ReopenReportRequest,
    verifier: User,
) -> Report:
    """Reopen a VERIFIED or REJECTED report back to UNDER_VERIFICATION.

    Preserves all previous verification records and adds a new status history transition.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.
        payload: Validated reopening request with required reason.
        verifier: Authenticated verifier or admin User.

    Returns:
        Report: Updated Report entity with status UNDER_VERIFICATION.

    Raises:
        HTTPException: 404 if not found, 409 if status is not VERIFIED or REJECTED.
    """
    try:
        report = db.execute(
            select(Report).where(Report.id == report_id).with_for_update()
        ).scalar_one_or_none()
        if report is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Report not found.",
            )

        if report.status not in ("VERIFIED", "REJECTED"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Cannot reopen report: report is currently '{report.status}', "
                    "expected 'VERIFIED' or 'REJECTED'."
                ),
            )

        from_status = report.status
        report.status = "UNDER_VERIFICATION"

        history = ReportStatusHistory(
            report_id=report.id,
            from_status=from_status,
            to_status="UNDER_VERIFICATION",
            changed_by_user_id=verifier.id,
            reason=payload.reason.strip(),
        )
        db.add(history)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_report_by_id(db, report_id)


def get_verification_history(
    db: Session,
    report_id: uuid.UUID,
    current_user: User,
) -> list[ReportVerification]:
    """Retrieve chronological verification records for a report with authorization scoping.

    Citizens can only view history for reports they submitted. Staff (verifier/admin)
    can view history for any report. Returns 404 if not found or unauthorized to prevent
    information leakage.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.
        current_user: Currently authenticated user.

    Returns:
        list[ReportVerification]: Chronologically ordered verification records.

    Raises:
        HTTPException: 404 if not found or access denied for citizen.
    """
    report = db.execute(
        select(Report.id, Report.reporter_id).where(Report.id == report_id)
    ).one_or_none()

    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    user_roles = {r.name for r in current_user.roles}
    is_staff = bool(user_roles.intersection({"verifier", "admin"}))

    if not is_staff and report.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )

    stmt = (
        select(ReportVerification)
        .where(ReportVerification.report_id == report_id)
        .order_by(ReportVerification.verified_at.asc(), ReportVerification.id.asc())
    )
    return list(db.execute(stmt).scalars().all())
