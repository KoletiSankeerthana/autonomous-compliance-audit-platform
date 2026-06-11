"""
Dashboard and analytics router.
GET /api/v1/dashboard/stats              — summary statistics
GET /api/v1/dashboard/trend              — monthly audit trend
GET /api/v1/dashboard/risk-distribution  — risk breakdown for pie chart
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.crud.audit_report import crud_audit_report
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import (
    DashboardStatsResponse,
    MonthlyTrendItem,
    RiskDistributionItem,
)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = get_logger(__name__)


@router.get(
    "/stats",
    response_model=DashboardStatsResponse,
    summary="Aggregate dashboard statistics",
)
def get_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = crud_audit_report.get_dashboard_stats(db)
    logger.info(f"Dashboard stats served: user_id={current_user.id}")
    return DashboardStatsResponse(**stats)


@router.get(
    "/trend",
    response_model=list[MonthlyTrendItem],
    summary="Monthly audit volume and compliance score trend",
)
def get_audit_trend(
    months: int = 12,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns audit count and average compliance score per calendar month
    for the last N months (default: 12).
    """
    rows = crud_audit_report.get_monthly_trend(db, months=months)
    return [MonthlyTrendItem(**row) for row in rows]


@router.get(
    "/risk-distribution",
    response_model=list[RiskDistributionItem],
    summary="Risk level distribution for pie/donut charts",
)
def get_risk_distribution(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = crud_audit_report.get_risk_distribution(db)
    return [RiskDistributionItem(**row) for row in rows]
