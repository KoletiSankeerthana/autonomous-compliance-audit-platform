"""
Audit report schemas.
The field_validator on issues/recommendations automatically deserialises
the JSON text stored in the database into typed Python lists.
"""

import json
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, field_validator


class AuditReportCreate(BaseModel):
    """Internal schema used when saving a report from the AI pipeline."""
    risk: str
    compliance_score: int
    violation_count: int
    issues: List[str]
    recommendations: List[str]
    audit_timestamp: str
    auditor: str
    created_by_user_id: Optional[int] = None


class AuditReportResponse(BaseModel):
    """Full audit report with parsed issues and recommendations."""
    id: int
    risk: str
    compliance_score: int
    violation_count: int
    issues: List[str]
    recommendations: List[str]
    audit_timestamp: str
    auditor: str
    created_by_user_id: Optional[int] = None
    created_at: Optional[datetime] = None

    @field_validator("issues", "recommendations", mode="before")
    @classmethod
    def parse_json_string(cls, v):
        """Deserialise JSON text from the database into a Python list."""
        if isinstance(v, str):
            try:
                parsed = json.loads(v)
                return parsed if isinstance(parsed, list) else [str(parsed)]
            except (json.JSONDecodeError, TypeError):
                return []
        return v if v is not None else []

    class Config:
        from_attributes = True


class AuditReportListItem(BaseModel):
    """Lightweight representation used in list views."""
    id: int
    risk: str
    compliance_score: int
    violation_count: int
    audit_timestamp: str
    auditor: str
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ComplianceReportResponse(BaseModel):
    """Response returned immediately after generating a compliance report."""
    violation: bool
    issues: List[str]
    recommendations: List[str]
    risk: str
    compliance_score: int
    violation_count: int
    audit_timestamp: str
    auditor: str
    id: Optional[int] = None
