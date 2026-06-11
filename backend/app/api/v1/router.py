"""Aggregates all v1 API routers into a single router."""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.compliance import router as compliance_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.documents import router as documents_router
from app.api.v1.mcp import router as mcp_router
from app.api.v1.users import router as users_router
from app.api.v1.workflow import router as workflow_router
from app.api.v1.health import router as health_router
from app.api.v1.export import router as export_router
from app.api.v1.analytics import router as analytics_router

api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(documents_router)
api_router.include_router(mcp_router)
api_router.include_router(compliance_router)
api_router.include_router(workflow_router)
api_router.include_router(dashboard_router)
api_router.include_router(health_router)
api_router.include_router(export_router)
api_router.include_router(analytics_router)
