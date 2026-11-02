"""API v1 Router aggregation."""

from fastapi import APIRouter

from app.api.v1.admin_maintenance import admin_maintenance_router
from app.api.v1.admin_reports import admin_reports_router
from app.api.v1.analytics import admin_analytics_router
from app.api.v1.auth import auth_router
from app.api.v1.intelligence import intelligence_router
from app.api.v1.maintenance import maintenance_router
from app.api.v1.notifications import notifications_router
from app.api.v1.reports import reports_router
from app.health.routes import api_v1_health_router

api_v1_router = APIRouter()

# Mount health routes under /health
api_v1_router.include_router(
    api_v1_health_router,
    prefix="/health",
    tags=["Health"],
)

# Authentication and user identity endpoints under /auth
api_v1_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["Authentication"],
)

# Citizen reporting endpoints under /reports
api_v1_router.include_router(
    reports_router,
    prefix="/reports",
    tags=["Reports"],
)

# In-app user notifications under /notifications
api_v1_router.include_router(
    notifications_router,
    prefix="/notifications",
    tags=["Notifications"],
)

# Administrative moderation and verification queue under /admin/reports
api_v1_router.include_router(
    admin_reports_router,
    prefix="/admin/reports",
    tags=["Moderation"],
)

# Administrative SDI intelligence engine under /admin/intelligence
api_v1_router.include_router(
    intelligence_router,
    prefix="/admin/intelligence",
    tags=["Intelligence"],
)

# Administrative maintenance management under /admin/maintenance
api_v1_router.include_router(
    admin_maintenance_router,
    prefix="/admin/maintenance",
    tags=["Admin Maintenance"],
)

# Administrative analytics dashboards under /admin/analytics
api_v1_router.include_router(
    admin_analytics_router,
    prefix="/admin/analytics",
    tags=["Analytics"],
)

# Maintenance technician work orders under /maintenance
api_v1_router.include_router(
    maintenance_router,
    prefix="/maintenance",
    tags=["Maintenance"],
)
