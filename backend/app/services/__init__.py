"""Services package for SafeSpace Intelligence business logic."""

from app.services.auth import authenticate_user, register_user
from app.services.reports import (
    create_citizen_report,
    get_citizen_report_by_id,
    get_report_by_id,
    list_citizen_reports,
    resolve_active_category,
    resolve_administrative_area,
)
from app.services.verification import (
    get_pending_reports_queue,
    get_verification_history,
    reject_report,
    reopen_report,
    start_report_verification,
    verify_report,
)

__all__ = [
    "authenticate_user",
    "create_citizen_report",
    "get_citizen_report_by_id",
    "get_pending_reports_queue",
    "get_report_by_id",
    "get_verification_history",
    "list_citizen_reports",
    "register_user",
    "reject_report",
    "reopen_report",
    "resolve_active_category",
    "resolve_administrative_area",
    "start_report_verification",
    "verify_report",
]
