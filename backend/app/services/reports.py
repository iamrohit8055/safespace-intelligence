"""Service layer implementing citizen report submission, spatial queries, and retrieval."""

import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from geoalchemy2.elements import WKTElement
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.geometry import create_point_wkt, parse_point_geometry
from app.models.geography import AdministrativeArea
from app.models.iam import User
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportStatusHistory
from app.schemas.reports import PublicReportMapItem, ReportCreateRequest
from app.services.notifications import create_notification


def resolve_active_category(
    db: Session,
    category_id: int | None,
    category_code: str | None,
) -> ReportCategory:
    """Validate and resolve an active deficiency taxonomy category.

    Args:
        db: Active SQLAlchemy database session.
        category_id: Optional primary key of the category.
        category_code: Optional unique taxonomy code.

    Returns:
        ReportCategory: Matching active category entity.

    Raises:
        HTTPException: 404 if category not found, 400 if inactive or mismatched.
    """
    if category_id is not None:
        category = db.execute(
            select(ReportCategory).where(ReportCategory.id == category_id)
        ).scalar_one_or_none()
    elif category_code is not None:
        category = db.execute(
            select(ReportCategory).where(ReportCategory.code == category_code.strip().upper())
        ).scalar_one_or_none()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either category_id or category_code must be provided.",
        )

    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deficiency category not found.",
        )

    if (
        category_id is not None
        and category_code is not None
        and (category.id != category_id or category.code != category_code.strip().upper())
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mismatched category_id and category_code.",
        )

    if not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Deficiency category is inactive and cannot accept new reports.",
        )

    return category


def resolve_administrative_area(
    db: Session,
    longitude: float,
    latitude: float,
) -> uuid.UUID | None:
    """Resolve the most granular administrative area covering the coordinate via PostGIS ST_Covers.

    Uses topological boundary-inclusive containment (ST_Covers). Resolves overlapping
    boundaries deterministically by hierarchy granularity (ward -> zone -> district -> municipality)
    with code ASC as a tie-breaker.

    Args:
        db: Active SQLAlchemy database session.
        longitude: X coordinate in WGS 84 [-180, 180].
        latitude: Y coordinate in WGS 84 [-90, 90].

    Returns:
        uuid.UUID | None: Matching administrative area ID or None if unassigned.
    """
    point_geom = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
    area_order = case(
        (AdministrativeArea.area_type == "ward", 1),
        (AdministrativeArea.area_type == "zone", 2),
        (AdministrativeArea.area_type == "district", 3),
        (AdministrativeArea.area_type == "municipality", 4),
        else_=5,
    )

    stmt = (
        select(AdministrativeArea.id)
        .where(func.ST_Covers(AdministrativeArea.boundary, point_geom))
        .order_by(area_order.asc(), AdministrativeArea.code.asc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()


def create_citizen_report(
    db: Session,
    payload: ReportCreateRequest,
    current_user: User,
) -> Report:
    """Create and persist a new citizen report with its initial audit status history row.

    The report record and its initial ReportStatusHistory transition (NULL -> SUBMITTED)
    are written within the exact same database transaction. If status history insertion
    fails, the entire transaction is rolled back.

    Args:
        db: Active SQLAlchemy database session.
        payload: Validated report creation request schema.
        current_user: Authenticated citizen User.

    Returns:
        Report: Newly created Report entity with eager-loaded relationships.
    """
    category = resolve_active_category(db, payload.category_id, payload.category_code)
    admin_area_id = resolve_administrative_area(db, payload.longitude, payload.latitude)

    location_wkt = create_point_wkt(payload.longitude, payload.latitude)
    now = datetime.now(UTC)
    if payload.observed_at is not None:
        observed_time = (
            payload.observed_at
            if payload.observed_at.tzinfo is not None
            else payload.observed_at.replace(tzinfo=UTC)
        )
        if observed_time > now:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Observation timestamp cannot be in the future.",
            )
    else:
        observed_time = now

    report = Report(
        reporter_id=current_user.id,
        category_id=category.id,
        administrative_area_id=admin_area_id,
        title=payload.title,
        description=payload.description,
        location=WKTElement(location_wkt),
        address_text=payload.address_text,
        status="SUBMITTED",
        observed_at=observed_time,
    )

    try:
        db.add(report)
        db.flush()

        status_history = ReportStatusHistory(
            report_id=report.id,
            from_status=None,
            to_status="SUBMITTED",
            changed_by_user_id=current_user.id,
            reason="Initial citizen report submission",
        )
        db.add(status_history)

        create_notification(
            db,
            recipient_id=current_user.id,
            notification_type="REPORT_SUBMITTED",
            title="Report Submitted",
            message=f"Your infrastructure deficiency report '{report.title}' has been submitted.",
            resource_type="report",
            resource_id=report.id,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return get_citizen_report_by_id(db, report.id, current_user.id)


def get_report_by_id(
    db: Session,
    report_id: uuid.UUID,
) -> Report:
    """Retrieve any report by primary key with eager-loaded relationships.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.

    Returns:
        Report: Report model instance with eager-loaded relationships.

    Raises:
        HTTPException: 404 if not found.
    """
    stmt = (
        select(Report)
        .options(
            joinedload(Report.category),
            joinedload(Report.administrative_area),
            selectinload(Report.media),
        )
        .where(Report.id == report_id)
    )
    report = db.execute(stmt).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )
    return report


def get_citizen_report_by_id(
    db: Session,
    report_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> Report:
    """Retrieve an authenticated citizen's report by primary key.

    Returns 404 if the report does not exist OR if it belongs to another user,
    preventing user ID enumeration and information disclosure.

    Args:
        db: Active SQLAlchemy database session.
        report_id: Unique report UUID.
        current_user_id: Authenticated user UUID.

    Returns:
        Report: Report model instance with eager-loaded relationships.

    Raises:
        HTTPException: 404 if not found or unauthorized.
    """
    stmt = (
        select(Report)
        .options(
            joinedload(Report.category),
            joinedload(Report.administrative_area),
            selectinload(Report.media),
        )
        .where(
            Report.id == report_id,
            Report.reporter_id == current_user_id,
        )
    )
    report = db.execute(stmt).scalar_one_or_none()
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found.",
        )
    return report


def list_citizen_reports(
    db: Session,
    current_user: User,
    limit: int,
    offset: int,
) -> tuple[list[Report], int]:
    """Retrieve a paginated collection of reports submitted by the authenticated citizen.

    Avoids N+1 queries by eager-loading category and administrative area relationships.
    Orders deterministically by submitted_at DESC with id DESC as a tie-breaker.

    Args:
        db: Active SQLAlchemy database session.
        current_user: Authenticated citizen User.
        limit: Maximum number of records to return.
        offset: Number of records to skip.

    Returns:
        tuple[list[Report], int]: (reports on page, total count of citizen's reports).
    """
    count_stmt = select(func.count(Report.id)).where(Report.reporter_id == current_user.id)
    total = db.execute(count_stmt).scalar_one()

    items_stmt = (
        select(Report)
        .options(
            joinedload(Report.category),
            joinedload(Report.administrative_area),
            selectinload(Report.media),
        )
        .where(Report.reporter_id == current_user.id)
        .order_by(Report.submitted_at.desc(), Report.id.desc())
        .limit(limit)
        .offset(offset)
    )
    items = list(db.execute(items_stmt).scalars().all())

    return items, total


def list_active_categories(db: Session) -> list[ReportCategory]:
    """Retrieve all active taxonomy deficiency categories."""
    stmt = (
        select(ReportCategory)
        .where(ReportCategory.is_active.is_(True))
        .order_by(ReportCategory.id.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_public_map_reports(
    db: Session,
    category_id: int | None = None,
    status_filter: str | None = None,
    limit: int = 250,
) -> list[PublicReportMapItem]:
    """Retrieve public deficiency reports with privacy-preserving coordinates.

    Applies coordinate fuzzing (rounding to 3 decimal places ~100m radius) to prevent
    exact private residence identification, and excludes reporter identities.
    """
    stmt = (
        select(Report)
        .options(
            joinedload(Report.category),
            joinedload(Report.administrative_area),
            selectinload(Report.media),
        )
        .where(
            Report.duplicate_of_id.is_(None),
            Report.status.in_(["SUBMITTED", "UNDER_VERIFICATION", "VERIFIED"]),
        )
    )

    if category_id is not None:
        stmt = stmt.where(Report.category_id == category_id)
    if status_filter:
        stmt = stmt.where(Report.status == status_filter.upper())

    stmt = stmt.order_by(Report.submitted_at.desc(), Report.id.desc()).limit(limit)
    reports = list(db.execute(stmt).scalars().unique().all())

    results: list[PublicReportMapItem] = []
    for r in reports:
        lon, lat = parse_point_geometry(r.location)
        # Privacy-safe coordinate fuzzing (3 decimal places ~ 110m)
        fuzzed_lat = round(lat, 3)
        fuzzed_lon = round(lon, 3)
        results.append(
            PublicReportMapItem(
                id=r.id,
                title=r.title,
                description=r.description,
                category_id=r.category.id,
                category_code=r.category.code,
                category_name=r.category.name,
                status=r.status,
                latitude=fuzzed_lat,
                longitude=fuzzed_lon,
                observed_at=r.observed_at,
                submitted_at=r.submitted_at,
                administrative_area_name=r.administrative_area.name
                if r.administrative_area
                else None,
                has_media=len(r.media) > 0,
            )
        )
    return results
