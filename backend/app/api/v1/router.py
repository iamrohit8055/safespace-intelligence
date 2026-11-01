"""API v1 Router aggregation."""

from fastapi import APIRouter

from app.health.routes import api_v1_health_router

api_v1_router = APIRouter()

# Mount health routes under /health
api_v1_router.include_router(
    api_v1_health_router,
    prefix="/health",
    tags=["Health"],
)

# Future domain modules will be mounted here:
# api_v1_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
# api_v1_router.include_router(reports_router, prefix="/reports", tags=["Reports"])
# api_v1_router.include_router(sdi_router, prefix="/sdi", tags=["SDI"])
