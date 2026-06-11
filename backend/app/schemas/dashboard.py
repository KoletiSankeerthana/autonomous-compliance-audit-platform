"""Dashboard and analytics schemas."""

from pydantic import BaseModel


class DashboardStatsResponse(BaseModel):
    total_audits: int
    high_risk: int
    medium_risk: int
    low_risk: int
    average_compliance_score: float


class MonthlyTrendItem(BaseModel):
    month: str          # "2026-01"
    audit_count: int
    average_score: float


class RiskDistributionItem(BaseModel):
    risk_level: str     # "High" | "Medium" | "Low"
    count: int
    percentage: float


class RiskAssessmentResponse(BaseModel):
    risk: str
    issue_count: int
    compliance_score: int
