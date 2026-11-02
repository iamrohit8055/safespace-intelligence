"""Service layer implementing database-backed administrative analytics and aggregations."""

import uuid
from datetime import UTC, date, datetime, time
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.confidence import AreaConfidenceComponent, AreaConfidenceScore
from app.models.geography import AdministrativeArea
from app.models.iam import User
from app.models.intelligence import AreaScore
from app.models.maintenance import MaintenanceTask
from app.models.priority import AreaPriorityScore
from app.models.reporting import Report, ReportCategory
from app.models.verification import ReportVerification
from app.schemas.analytics import (
    AnalyticsOverviewResponse,
    AreaReportCount,
    AreaSdiItem,
    CategoryCount,
    ConfidenceAnalyticsResponse,
    MaintenanceAnalyticsResponse,
    MaintenanceUserTaskCount,
    ReportAnalyticsResponse,
    SdiAnalyticsResponse,
    SdiRangeDistribution,
    StatusCount,
    TimeSeriesPoint,
    TrendsAnalyticsResponse,
)


def get_reports_analytics(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    area_id: uuid.UUID | None = None,
) -> ReportAnalyticsResponse:
    """Aggregate report volume, status breakdowns, categories, and timeline trends."""
    base_query = select(Report)
    if start_date:
        dt_start = datetime.combine(start_date, time.min, tzinfo=UTC)
        base_query = base_query.where(Report.submitted_at >= dt_start)
    if end_date:
        dt_end = datetime.combine(end_date, time.max, tzinfo=UTC)
        base_query = base_query.where(Report.submitted_at <= dt_end)
    if area_id:
        base_query = base_query.where(Report.administrative_area_id == area_id)

    # 1. Total reports
    subq = base_query.subquery()
    total_stmt = select(func.count()).select_from(subq)
    total_reports = db.execute(total_stmt).scalar_one()

    # 2. Breakdown by status
    status_stmt = select(subq.c.status, func.count()).select_from(subq).group_by(subq.c.status)
    status_counts_raw = db.execute(status_stmt).all()
    status_map = dict(status_counts_raw)
    by_status = [StatusCount(status=s, count=c) for s, c in sorted(status_map.items())]

    # 3. Breakdown by category
    cat_stmt = select(
        ReportCategory.id,
        ReportCategory.code,
        ReportCategory.name,
        func.count(Report.id),
    ).join(Report, Report.category_id == ReportCategory.id)
    if start_date:
        cat_stmt = cat_stmt.where(
            Report.submitted_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
        )
    if end_date:
        cat_stmt = cat_stmt.where(
            Report.submitted_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
    if area_id:
        cat_stmt = cat_stmt.where(Report.administrative_area_id == area_id)

    cat_stmt = cat_stmt.group_by(
        ReportCategory.id, ReportCategory.code, ReportCategory.name
    ).order_by(func.count(Report.id).desc())
    by_category = [
        CategoryCount(category_id=cid, category_code=code, category_name=name, count=cnt)
        for cid, code, name, cnt in db.execute(cat_stmt).all()
    ]

    # 4. Breakdown by administrative area
    area_stmt = select(
        AdministrativeArea.id,
        AdministrativeArea.name,
        AdministrativeArea.code,
        AdministrativeArea.area_type,
        func.count(Report.id),
    ).join(Report, Report.administrative_area_id == AdministrativeArea.id)
    if start_date:
        area_stmt = area_stmt.where(
            Report.submitted_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
        )
    if end_date:
        area_stmt = area_stmt.where(
            Report.submitted_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
    if area_id:
        area_stmt = area_stmt.where(Report.administrative_area_id == area_id)

    area_stmt = area_stmt.group_by(
        AdministrativeArea.id,
        AdministrativeArea.name,
        AdministrativeArea.code,
        AdministrativeArea.area_type,
    ).order_by(func.count(Report.id).desc())
    by_area = [
        AreaReportCount(area_id=aid, area_name=aname, area_code=acode, area_type=atype, count=cnt)
        for aid, aname, acode, atype, cnt in db.execute(area_stmt).all()
    ]

    # 5. Timeline submission frequency
    date_trunc_expr = func.to_char(subq.c.submitted_at, "YYYY-MM-DD")
    time_stmt = (
        select(date_trunc_expr, func.count())
        .select_from(subq)
        .group_by(date_trunc_expr)
        .order_by(date_trunc_expr.asc())
    )
    submitted_over_time = [TimeSeriesPoint(date=d, count=c) for d, c in db.execute(time_stmt).all()]

    # 6. Specific counts
    verified_count = status_map.get("VERIFIED", 0)
    rejected_count = status_map.get("REJECTED", 0)
    pending_backlog_count = status_map.get("SUBMITTED", 0) + status_map.get("UNDER_VERIFICATION", 0)

    # Duplicates count
    dup_stmt = select(func.count()).where(Report.duplicate_of_id.is_not(None))
    if start_date:
        dup_stmt = dup_stmt.where(
            Report.submitted_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
        )
    if end_date:
        dup_stmt = dup_stmt.where(
            Report.submitted_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
    if area_id:
        dup_stmt = dup_stmt.where(Report.administrative_area_id == area_id)
    duplicate_count = db.execute(dup_stmt).scalar_one()

    return ReportAnalyticsResponse(
        total_reports=total_reports,
        by_status=by_status,
        by_category=by_category,
        by_area=by_area,
        submitted_over_time=submitted_over_time,
        verified_count=verified_count,
        rejected_count=rejected_count,
        duplicate_count=duplicate_count,
        pending_backlog_count=pending_backlog_count,
    )


def get_sdi_analytics(
    db: Session,
    area_id: uuid.UUID | None = None,
) -> SdiAnalyticsResponse:
    """Aggregate Safety Deficiency Index distribution across municipal jurisdictions."""
    # Fetch all areas
    areas_stmt = select(AdministrativeArea).order_by(AdministrativeArea.name.asc())
    if area_id:
        areas_stmt = areas_stmt.where(AdministrativeArea.id == area_id)
    areas = list(db.execute(areas_stmt).scalars().all())

    # Fetch current area scores
    sdi_stmt = select(AreaScore).where(AreaScore.is_current.is_(True))
    if area_id:
        sdi_stmt = sdi_stmt.where(AreaScore.administrative_area_id == area_id)
    scores = {s.administrative_area_id: s for s in db.execute(sdi_stmt).scalars().all()}

    negligible = 0
    low = 0
    moderate = 0
    high = 0
    severe = 0
    insufficient = 0

    area_items: list[AreaSdiItem] = []
    for a in areas:
        sc = scores.get(a.id)
        if sc and sc.score is not None:
            val = sc.score
            if val < Decimal("1.0"):
                negligible += 1
            elif val < Decimal("2.0"):
                low += 1
            elif val < Decimal("3.0"):
                moderate += 1
            elif val < Decimal("4.0"):
                high += 1
            else:
                severe += 1
            area_items.append(
                AreaSdiItem(
                    area_id=a.id,
                    area_name=a.name,
                    area_code=a.code,
                    sdi_score=sc.score,
                    completeness_pct=sc.completeness_pct,
                    calculation_timestamp=sc.calculation_timestamp,
                )
            )
        else:
            insufficient += 1
            area_items.append(
                AreaSdiItem(
                    area_id=a.id,
                    area_name=a.name,
                    area_code=a.code,
                    sdi_score=None,
                    completeness_pct=None,
                    calculation_timestamp=None,
                )
            )

    distribution = SdiRangeDistribution(
        negligible=negligible,
        low=low,
        moderate=moderate,
        high=high,
        severe=severe,
        insufficient_data=insufficient,
    )

    return SdiAnalyticsResponse(
        total_areas_evaluated=len(areas),
        range_distribution=distribution,
        areas=area_items,
        insufficient_data_areas_count=insufficient,
    )


def get_confidence_analytics(
    db: Session,
    area_id: uuid.UUID | None = None,
) -> ConfidenceAnalyticsResponse:
    """Aggregate area confidence, data completeness, and category sample sizes."""
    stmt = select(AreaConfidenceScore).where(AreaConfidenceScore.is_current.is_(True))
    if area_id:
        stmt = stmt.where(AreaConfidenceScore.administrative_area_id == area_id)
    conf_scores = list(db.execute(stmt).scalars().all())

    evaluated_count = len(conf_scores)
    if evaluated_count > 0:
        valid_scores = [c.confidence_score for c in conf_scores if c.confidence_score is not None]
        avg_conf = sum(valid_scores) / Decimal(str(len(valid_scores))) if valid_scores else None
        if avg_conf:
            avg_conf = avg_conf.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        valid_comps = [c.completeness_pct for c in conf_scores if c.completeness_pct is not None]
        avg_comp = sum(valid_comps) / Decimal(str(len(valid_comps))) if valid_comps else None
        if avg_comp:
            avg_comp = avg_comp.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        low_evidence = sum(
            1
            for c in conf_scores
            if (c.confidence_score is None or c.confidence_score < Decimal("0.4000"))
            or (c.completeness_pct is None or c.completeness_pct < Decimal("50.00"))
        )
    else:
        avg_conf = None
        avg_comp = None
        low_evidence = 0

    # Category confident sample counts
    sample_stmt = (
        select(
            ReportCategory.id,
            ReportCategory.code,
            ReportCategory.name,
            func.coalesce(func.sum(AreaConfidenceComponent.confident_report_count), 0),
        )
        .join(
            AreaConfidenceComponent,
            AreaConfidenceComponent.category_id == ReportCategory.id,
        )
        .join(
            AreaConfidenceScore,
            AreaConfidenceComponent.area_confidence_id == AreaConfidenceScore.id,
        )
        .where(AreaConfidenceScore.is_current.is_(True))
    )
    if area_id:
        sample_stmt = sample_stmt.where(AreaConfidenceScore.administrative_area_id == area_id)

    sample_stmt = sample_stmt.group_by(ReportCategory.id, ReportCategory.code, ReportCategory.name)
    cat_samples = [
        CategoryCount(category_id=cid, category_code=code, category_name=name, count=int(cnt))
        for cid, code, name, cnt in db.execute(sample_stmt).all()
    ]

    return ConfidenceAnalyticsResponse(
        evaluated_areas_count=evaluated_count,
        average_area_confidence=avg_conf,
        average_completeness_pct=avg_comp,
        category_sample_counts=cat_samples,
        low_evidence_areas_count=low_evidence,
    )


def get_maintenance_analytics(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    technician_id: uuid.UUID | None = None,
) -> MaintenanceAnalyticsResponse:
    """Aggregate work order status, priority, turnaround duration, and technician metrics."""
    stmt = select(MaintenanceTask)
    if start_date:
        dt_start = datetime.combine(start_date, time.min, tzinfo=UTC)
        stmt = stmt.where(MaintenanceTask.created_at >= dt_start)
    if end_date:
        dt_end = datetime.combine(end_date, time.max, tzinfo=UTC)
        stmt = stmt.where(MaintenanceTask.created_at <= dt_end)
    if technician_id:
        stmt = stmt.where(MaintenanceTask.assigned_to_user_id == technician_id)

    subq_maint = stmt.subquery()
    total_tasks = db.execute(select(func.count()).select_from(subq_maint)).scalar_one()

    # Status breakdown
    st_stmt = (
        select(subq_maint.c.status, func.count())
        .select_from(subq_maint)
        .group_by(subq_maint.c.status)
    )
    by_status = [StatusCount(status=s, count=c) for s, c in db.execute(st_stmt).all()]

    # Priority breakdown
    pr_stmt = (
        select(subq_maint.c.priority, func.count())
        .select_from(subq_maint)
        .group_by(subq_maint.c.priority)
    )
    by_priority = [StatusCount(status=p, count=c) for p, c in db.execute(pr_stmt).all()]

    # Turnaround time on completed tasks (in hours)
    duration_stmt = select(
        func.avg(
            func.extract(
                "epoch",
                MaintenanceTask.completed_at - MaintenanceTask.created_at,
            )
            / 3600.0
        )
    ).where(MaintenanceTask.completed_at.is_not(None))
    if technician_id:
        duration_stmt = duration_stmt.where(MaintenanceTask.assigned_to_user_id == technician_id)

    avg_turnaround_val = db.execute(duration_stmt).scalar_one()
    avg_hours = (
        Decimal(str(avg_turnaround_val)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if avg_turnaround_val is not None
        else None
    )

    # Overdue tasks count
    now = datetime.now(UTC)
    overdue_stmt = select(func.count()).where(
        MaintenanceTask.due_date.is_not(None),
        MaintenanceTask.due_date < now,
        MaintenanceTask.status.not_in(["COMPLETED", "CANCELLED"]),
    )
    if technician_id:
        overdue_stmt = overdue_stmt.where(MaintenanceTask.assigned_to_user_id == technician_id)
    overdue_count = db.execute(overdue_stmt).scalar_one()

    # Breakdown by technician
    tech_stmt = (
        select(
            User.id,
            User.full_name,
            func.count(MaintenanceTask.id),
            func.count(case((MaintenanceTask.status == "COMPLETED", 1))),
        )
        .join(MaintenanceTask, MaintenanceTask.assigned_to_user_id == User.id)
        .group_by(User.id, User.full_name)
    )
    by_technician = [
        MaintenanceUserTaskCount(
            user_id=uid,
            user_name=uname,
            assigned_count=assigned,
            completed_count=completed,
        )
        for uid, uname, assigned, completed in db.execute(tech_stmt).all()
    ]

    return MaintenanceAnalyticsResponse(
        total_tasks=total_tasks,
        by_status=by_status,
        by_priority=by_priority,
        average_completion_time_hours=avg_hours,
        overdue_tasks_count=overdue_count,
        by_technician=by_technician,
    )


def get_analytics_overview(db: Session) -> AnalyticsOverviewResponse:
    """High-level summary KPIs combining reporting, verification, SDI, and maintenance."""
    total_reports = db.execute(select(func.count(Report.id))).scalar_one()
    pending_verification = db.execute(
        select(func.count(Report.id)).where(Report.status.in_(["SUBMITTED", "UNDER_VERIFICATION"]))
    ).scalar_one()
    verified_reports = db.execute(
        select(func.count(Report.id)).where(Report.status == "VERIFIED")
    ).scalar_one()

    total_tasks = db.execute(select(func.count(MaintenanceTask.id))).scalar_one()
    active_tasks = db.execute(
        select(func.count(MaintenanceTask.id)).where(
            MaintenanceTask.status.in_(["ASSIGNED", "ACCEPTED", "IN_PROGRESS", "BLOCKED"])
        )
    ).scalar_one()

    critical_priority_areas = db.execute(
        select(func.count(AreaPriorityScore.id)).where(
            AreaPriorityScore.is_current.is_(True),
            AreaPriorityScore.priority_level == "CRITICAL",
        )
    ).scalar_one()

    return AnalyticsOverviewResponse(
        total_reports=total_reports,
        pending_verification=pending_verification,
        verified_reports=verified_reports,
        total_maintenance_tasks=total_tasks,
        active_maintenance_tasks=active_tasks,
        critical_priority_areas_count=critical_priority_areas,
        generated_at=datetime.now(UTC),
    )


def get_trends_analytics(
    db: Session,
    start_date: date | None = None,
    end_date: date | None = None,
    area_id: uuid.UUID | None = None,
) -> TrendsAnalyticsResponse:
    """Historical timeline trends comparing submissions, verifications, and repairs."""
    # 1. Submissions trend
    date_sub = func.to_char(Report.submitted_at, "YYYY-MM-DD")
    sub_stmt = select(date_sub, func.count(Report.id)).group_by(date_sub).order_by(date_sub.asc())
    if start_date:
        sub_stmt = sub_stmt.where(
            Report.submitted_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
        )
    if end_date:
        sub_stmt = sub_stmt.where(
            Report.submitted_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
    if area_id:
        sub_stmt = sub_stmt.where(Report.administrative_area_id == area_id)
    sub_trends = [TimeSeriesPoint(date=d, count=c) for d, c in db.execute(sub_stmt).all()]

    # 2. Verifications trend
    date_ver = func.to_char(ReportVerification.verified_at, "YYYY-MM-DD")
    ver_stmt = (
        select(date_ver, func.count(ReportVerification.id))
        .join(Report, ReportVerification.report_id == Report.id)
        .group_by(date_ver)
        .order_by(date_ver.asc())
    )
    if start_date:
        ver_stmt = ver_stmt.where(
            ReportVerification.verified_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
        )
    if end_date:
        ver_stmt = ver_stmt.where(
            ReportVerification.verified_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
    if area_id:
        ver_stmt = ver_stmt.where(Report.administrative_area_id == area_id)
    ver_trends = [TimeSeriesPoint(date=d, count=c) for d, c in db.execute(ver_stmt).all()]

    # 3. Completions trend
    date_comp = func.to_char(MaintenanceTask.completed_at, "YYYY-MM-DD")
    comp_stmt = (
        select(date_comp, func.count(MaintenanceTask.id))
        .where(MaintenanceTask.completed_at.is_not(None))
        .group_by(date_comp)
        .order_by(date_comp.asc())
    )
    if start_date:
        comp_stmt = comp_stmt.where(
            MaintenanceTask.completed_at >= datetime.combine(start_date, time.min, tzinfo=UTC)
        )
    if end_date:
        comp_stmt = comp_stmt.where(
            MaintenanceTask.completed_at <= datetime.combine(end_date, time.max, tzinfo=UTC)
        )
    comp_trends = [TimeSeriesPoint(date=d, count=c) for d, c in db.execute(comp_stmt).all()]

    return TrendsAnalyticsResponse(
        submissions_trend=sub_trends,
        verifications_trend=ver_trends,
        completions_trend=comp_trends,
    )
