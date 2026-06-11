"""
Analytics and Trend Intelligence API router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.agents.router_workflow import run_query_router
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics & Trend Intelligence"])

# ---- Schemas ----

class AnalyticsTrendsResponse(BaseModel):
    compliance_score_trend: List[Dict[str, Any]]
    violation_frequency: List[Dict[str, Any]]
    risk_distribution_trend: List[Dict[str, Any]]
    recurring_findings: List[Dict[str, Any]]
    ai_trend_summary: str

class AnalyticsQueryRequest(BaseModel):
    query: str

class AnalyticsQueryResponse(BaseModel):
    success: bool
    route: str
    content: str
    saved_report_id: Optional[int] = None
    error: Optional[str] = None

# ---- Endpoints ----

@router.get(
    "/trends",
    response_model=AnalyticsTrendsResponse,
    summary="Get aggregated compliance trends metrics",
)
def get_compliance_trends(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns time-series and categorized statistics of compliance violations, 
    plus an AI-generated summary of all logs.
    """
    try:
        score_trend = analytics_service.get_compliance_score_trend(db)
        violation_freq = analytics_service.get_violation_frequency(db)
        risk_trend = analytics_service.get_risk_distribution_trend(db)
        recurring = analytics_service.get_recurring_findings(db)
        ai_summary = analytics_service.generate_ai_trend_summary(db)
        
        return AnalyticsTrendsResponse(
            compliance_score_trend=score_trend,
            violation_frequency=violation_freq,
            risk_distribution_trend=risk_trend,
            recurring_findings=recurring,
            ai_trend_summary=ai_summary,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to compile analytics: {exc}"
        )

@router.post(
    "/query",
    response_model=AnalyticsQueryResponse,
    summary="Route query to RAG, Audit, or Trend analysis dynamically",
)
def query_compliance_intelligence(
    payload: AnalyticsQueryRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Unified query routing endpoint. Runs the LangGraph query router to classify
    the request and fetch the grounded answer, audit execution, or SQL trends.
    """
    res = run_query_router(query=payload.query, user_id=current_user.id)
    if res.get("error"):
        return AnalyticsQueryResponse(
            success=False,
            route=res.get("route", "unknown"),
            content="",
            error=res.get("error")
        )
        
    return AnalyticsQueryResponse(
        success=True,
        route=res.get("route", "rag_question"),
        content=res.get("content", ""),
        saved_report_id=res.get("saved_report_id"),
    )
