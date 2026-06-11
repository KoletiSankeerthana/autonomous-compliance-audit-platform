"""
AuditReport ORM model.
issues and recommendations are stored as JSON-encoded TEXT for broad
PostgreSQL compatibility without requiring the JSONB extension.
"""

from sqlalchemy import Column, DateTime, Index, Integer, String, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.models.base import Base


class AuditReport(Base):
    """Persisted compliance audit report produced by the AI pipeline."""

    __tablename__ = "audit_reports"

    violations = relationship("ComplianceViolation", back_populates="report", cascade="all, delete-orphan")

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    risk = Column(String(20), nullable=False, index=True)

    compliance_score = Column(Integer, nullable=False, index=True)

    violation_count = Column(Integer, nullable=False, default=0)

    # JSON-encoded list of issue strings
    issues = Column(Text, nullable=False, default="[]")

    # JSON-encoded list of recommendation strings
    recommendations = Column(Text, nullable=False, default="[]")

    # ISO-8601 string: "2026-06-03 11:00:00"
    audit_timestamp = Column(String(30), nullable=False, index=True)

    auditor = Column(
        String(100),
        nullable=False,
        default="Compliance AI Auditor",
    )

    # The user who triggered this audit (nullable for system-generated)
    created_by_user_id = Column(Integer, nullable=True, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("idx_risk_timestamp", "risk", "audit_timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditReport id={self.id} risk={self.risk} "
            f"score={self.compliance_score}>"
        )
