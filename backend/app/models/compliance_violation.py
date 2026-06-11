"""
ComplianceViolation ORM model.
Stores granular metadata for each identified issue in an audit report.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.models.base import Base

class ComplianceViolation(Base):
    """Structured compliance violation record associated with an audit report."""

    __tablename__ = "compliance_violations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    report_id = Column(Integer, ForeignKey("audit_reports.id", ondelete="CASCADE"), nullable=False, index=True)

    violation_type = Column(String(100), nullable=False, index=True)       # e.g., "MFA", "Access Control"
    severity = Column(String(50), nullable=False, index=True)             # e.g., "Critical", "High", "Medium", "Low"
    department = Column(String(100), nullable=False, default="General", index=True) # e.g., "IT", "HR"
    compliance_score = Column(Integer, nullable=False, default=0)
    regulation_category = Column(String(100), nullable=False, index=True)  # e.g., "Data Privacy", "Access Security"
    report_date = Column(DateTime(timezone=True), nullable=False, index=True)
    description = Column(Text, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    report = relationship("AuditReport", back_populates="violations")

    def __repr__(self) -> str:
        return (
            f"<ComplianceViolation id={self.id} report_id={self.report_id} "
            f"type={self.violation_type} severity={self.severity}>"
        )
