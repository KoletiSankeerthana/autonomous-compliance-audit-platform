"""AuditReport CRUD operations."""

import json
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.audit_report import AuditReport


class CRUDAuditReport(CRUDBase[AuditReport]):
    """AuditReport-specific database operations."""

    def create_from_dict(
        self,
        db: Session,
        *,
        report: dict,
        user_id: Optional[int] = None,
    ) -> AuditReport:
        """
        Persist a compliance report dict to the database.
        issues and recommendations are JSON-serialised before storage.
        """
        issues = report.get("issues", [])
        recommendations = report.get("recommendations", [])

        record = AuditReport(
            risk=report.get("risk", "Unknown"),
            compliance_score=int(report.get("compliance_score", 0)),
            violation_count=int(report.get("violation_count", 0)),
            issues=json.dumps(issues) if isinstance(issues, list) else issues,
            recommendations=(
                json.dumps(recommendations)
                if isinstance(recommendations, list)
                else recommendations
            ),
            audit_timestamp=report.get("audit_timestamp", ""),
            auditor=report.get("auditor", "Compliance AI Auditor"),
            created_by_user_id=user_id,
        )

        # Map and attach structured violations
        from app.models.compliance_violation import ComplianceViolation
        from datetime import datetime
        
        try:
            report_dt = datetime.strptime(report.get("audit_timestamp", ""), "%Y-%m-%d %H:%M:%S")
        except Exception:
            report_dt = datetime.now()

        structured_violations = report.get("structured_violations", [])
        violation_records = []
        for v in structured_violations:
            violation_records.append(
                ComplianceViolation(
                    violation_type=v.get("violation_type", "Other"),
                    severity=v.get("severity", "Medium"),
                    department=v.get("department", "General"),
                    compliance_score=int(report.get("compliance_score", 0)),
                    regulation_category=v.get("regulation_category", "General"),
                    report_date=report_dt,
                    description=v.get("description", ""),
                )
            )
        record.violations = violation_records

        return self.create(db, obj=record)

    def get_ordered(
        self,
        db: Session,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> list[AuditReport]:
        """Return reports ordered by creation timestamp descending."""
        return (
            db.query(AuditReport)
            .order_by(AuditReport.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_dashboard_stats(self, db: Session) -> dict:
        """
        Compute aggregated statistics for the dashboard.
        All counts and averages are computed in a single DB round-trip where possible.
        """
        total_audits = db.query(AuditReport).count()

        high_risk = (
            db.query(AuditReport).filter(AuditReport.risk == "High").count()
        )
        medium_risk = (
            db.query(AuditReport).filter(AuditReport.risk == "Medium").count()
        )
        low_risk = (
            db.query(AuditReport).filter(AuditReport.risk == "Low").count()
        )

        avg_score = 0.0
        if total_audits > 0:
            result = db.query(func.avg(AuditReport.compliance_score)).scalar()
            avg_score = round(float(result), 2) if result is not None else 0.0

        return {
            "total_audits": total_audits,
            "high_risk": high_risk,
            "medium_risk": medium_risk,
            "low_risk": low_risk,
            "average_compliance_score": avg_score,
        }

    def get_monthly_trend(self, db: Session, *, months: int = 12) -> list[dict]:
        """
        Return per-month audit count and average compliance score
        for the last N months.
        """
        from sqlalchemy import extract, text

        if "sqlite" in db.bind.url.drivername:
            rows = db.execute(
                text("""
                    SELECT
                        strftime('%Y-%m', created_at) AS month,
                        COUNT(*)                      AS audit_count,
                        ROUND(AVG(compliance_score), 2) AS average_score
                    FROM audit_reports
                    WHERE created_at >= datetime('now', '-' || :months || ' month')
                    GROUP BY month
                    ORDER BY month ASC
                """),
                {"months": months},
            ).fetchall()
        else:
            rows = db.execute(
                text("""
                    SELECT
                        TO_CHAR(created_at, 'YYYY-MM') AS month,
                        COUNT(*)::int                  AS audit_count,
                        ROUND(AVG(compliance_score), 2)::float AS average_score
                    FROM audit_reports
                    WHERE created_at >= NOW() - INTERVAL ':months months'
                    GROUP BY month
                    ORDER BY month ASC
                """),
                {"months": months},
            ).fetchall()

        return [
            {
                "month": row[0],
                "audit_count": row[1],
                "average_score": float(row[2]) if row[2] else 0.0,
            }
            for row in rows
        ]

    def get_risk_distribution(self, db: Session) -> list[dict]:
        """Return risk level counts as percentages for pie charts."""
        total = db.query(AuditReport).count()
        if total == 0:
            return []

        rows = (
            db.query(AuditReport.risk, func.count(AuditReport.id))
            .group_by(AuditReport.risk)
            .all()
        )

        return [
            {
                "risk_level": row[0],
                "count": row[1],
                "percentage": round((row[1] / total) * 100, 1),
            }
            for row in rows
        ]


crud_audit_report = CRUDAuditReport(AuditReport)
