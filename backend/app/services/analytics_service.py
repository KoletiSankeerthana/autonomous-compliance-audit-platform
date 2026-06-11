"""
Analytics Aggregation Service.
Handles SQL-based analytics compilation and LLM trend summary generation.
"""

import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.models.compliance_violation import ComplianceViolation
from app.models.audit_report import AuditReport
from app.services.compliance_service import _call_ollama
from app.core.logging import get_logger

logger = get_logger(__name__)

def _parse_query_dates(query: str) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parses a query string to extract a start date and an end date based on date/timeline cues.
    Returns (start_date, end_date) as timezone-aware datetime objects in UTC (or None).
    """
    if not query:
        return None, None
        
    now = datetime.now(timezone.utc)
    query_lower = query.lower()

    # 1. "from [year] to [year]" / "between [year] and [year]" / "[year] - [year]"
    range_pattern = re.search(r'(?:from|between)?\s*(\d{4})\s*(?:to|and|-)\s*(\d{4})', query_lower)
    if range_pattern:
        start_year = int(range_pattern.group(1))
        end_year = int(range_pattern.group(2))
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        start_dt = datetime(start_year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(end_year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return start_dt, end_dt

    # 2. "past [N] years" / "last [N] years"
    past_years_pattern = re.search(r'(?:past|last)\s+(\d+)\s+years?', query_lower)
    if past_years_pattern:
        years = int(past_years_pattern.group(1))
        start_dt = now - timedelta(days=years * 365)
        return start_dt, now

    # 3. "past [N] months" / "last [N] months"
    past_months_pattern = re.search(r'(?:past|last)\s+(\d+)\s+months?', query_lower)
    if past_months_pattern:
        months = int(past_months_pattern.group(1))
        start_dt = now - timedelta(days=months * 30)
        return start_dt, now

    # 4. "in [year]" / "during [year]" / "for [year]"
    single_year_pattern = re.search(r'\b(?:in|during|for)\s+(\d{4})\b', query_lower)
    if single_year_pattern:
        year = int(single_year_pattern.group(1))
        start_dt = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_dt = datetime(year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return start_dt, end_dt

    # 5. "since [year]" / "from [year]"
    since_pattern = re.search(r'\b(?:since|from)\s+(\d{4})\b', query_lower)
    if since_pattern:
        year = int(since_pattern.group(1))
        start_dt = datetime(year, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        return start_dt, None

    # 6. "before [year]" / "until [year]" / "to [year]"
    before_pattern = re.search(r'\b(?:before|until|to)\s+(\d{4})\b', query_lower)
    if before_pattern:
        year = int(before_pattern.group(1))
        end_dt = datetime(year - 1, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return None, end_dt

    return None, None

def get_compliance_score_trend(
    db: Session, 
    months: int = 12,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> list[dict]:
    """Compile monthly average compliance scores."""
    params = {}
    where_clauses = []
    
    if start_date:
        where_clauses.append("report_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where_clauses.append("report_date <= :end_date")
        params["end_date"] = end_date
        
    if not start_date and not end_date:
        if "sqlite" in db.bind.url.drivername:
            where_clauses.append("report_date >= datetime('now', '-' || :months || ' month')")
        else:
            where_clauses.append("report_date >= NOW() - INTERVAL ':months months'")
        params["months"] = months

    where_str = " AND ".join(where_clauses)
    
    if "sqlite" in db.bind.url.drivername:
        sql = f"""
            SELECT 
                strftime('%Y-%m', report_date) AS period,
                ROUND(AVG(compliance_score), 1) AS avg_score
            FROM compliance_violations
            WHERE {where_str}
            GROUP BY period
            ORDER BY period ASC
        """
    else:
        sql = f"""
            SELECT 
                TO_CHAR(report_date, 'YYYY-MM') AS period,
                ROUND(AVG(compliance_score), 1)::float AS avg_score
            FROM compliance_violations
            WHERE {where_str}
            GROUP BY period
            ORDER BY period ASC
        """
        
    query = text(sql)
    rows = db.execute(query, params).fetchall()
    return [{"period": r[0], "score": float(r[1]) if r[1] is not None else 100.0} for r in rows]

def get_violation_frequency(
    db: Session, 
    months: int = 12,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> list[dict]:
    """Count violations grouped by violation_type and department."""
    query = db.query(
        ComplianceViolation.violation_type,
        ComplianceViolation.department,
        func.count(ComplianceViolation.id)
    )
    
    if start_date or end_date:
        if start_date:
            query = query.filter(ComplianceViolation.report_date >= start_date)
        if end_date:
            query = query.filter(ComplianceViolation.report_date <= end_date)
    else:
        # Fallback to relative time
        if "sqlite" in db.bind.url.drivername:
            query = query.filter(ComplianceViolation.report_date >= text(f"datetime('now', '-{months} month')"))
        else:
            query = query.filter(ComplianceViolation.report_date >= text(f"NOW() - INTERVAL '{months} months'"))
            
    rows = (
        query.group_by(ComplianceViolation.violation_type, ComplianceViolation.department)
        .all()
    )
    return [
        {
            "type": r[0],
            "department": r[1],
            "count": r[2]
        }
        for r in rows
    ]

def get_risk_distribution_trend(
    db: Session, 
    months: int = 12,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> list[dict]:
    """Compile monthly distribution of violation severities."""
    params = {}
    where_clauses = []
    
    if start_date:
        where_clauses.append("report_date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        where_clauses.append("report_date <= :end_date")
        params["end_date"] = end_date
        
    if not start_date and not end_date:
        if "sqlite" in db.bind.url.drivername:
            where_clauses.append("report_date >= datetime('now', '-' || :months || ' month')")
        else:
            where_clauses.append("report_date >= NOW() - INTERVAL ':months months'")
        params["months"] = months
        
    where_str = " AND ".join(where_clauses)
    
    if "sqlite" in db.bind.url.drivername:
        sql = f"""
            SELECT 
                strftime('%Y-%m', report_date) AS period,
                severity,
                COUNT(*) AS count
            FROM compliance_violations
            WHERE {where_str}
            GROUP BY period, severity
            ORDER BY period ASC
        """
    else:
        sql = f"""
            SELECT 
                TO_CHAR(report_date, 'YYYY-MM') AS period,
                severity,
                COUNT(*)::int AS count
            FROM compliance_violations
            WHERE {where_str}
            GROUP BY period, severity
            ORDER BY period ASC
        """
        
    query = text(sql)
    rows = db.execute(query, params).fetchall()
    
    # Restructure into a timeline array: [{"period": "2026-06", "Critical": 5, "High": 2, ...}]
    data_by_period = {}
    for r in rows:
        period, severity, count = r[0], r[1], r[2]
        if period not in data_by_period:
            data_by_period[period] = {"period": period, "Critical": 0, "High": 0, "Medium": 0, "Low": 0}
        data_by_period[period][severity] = count
        
    return sorted(list(data_by_period.values()), key=lambda x: x["period"])

def get_recurring_findings(
    db: Session, 
    limit: int = 5,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> list[dict]:
    """Rank top violation categories and list common description themes."""
    query = db.query(
        ComplianceViolation.violation_type,
        func.count(ComplianceViolation.id)
    )
    if start_date:
        query = query.filter(ComplianceViolation.report_date >= start_date)
    if end_date:
        query = query.filter(ComplianceViolation.report_date <= end_date)
        
    rows = (
        query.group_by(ComplianceViolation.violation_type)
        .order_by(func.count(ComplianceViolation.id).desc())
        .limit(limit)
        .all()
    )
    return [{"type": r[0], "count": r[1]} for r in rows]

def generate_ai_trend_summary(db: Session, query_prompt: str = "") -> str:
    """Compile recent stats and feed to LLM to produce a narrative summary."""
    # 0. Parse start/end dates from query
    start_date, end_date = _parse_query_dates(query_prompt)
    
    # 1. Fetch statistics
    score_trend = get_compliance_score_trend(db, 6, start_date=start_date, end_date=end_date)
    violation_freq = get_recurring_findings(db, 5, start_date=start_date, end_date=end_date)
    
    # Get total violations count
    total_query = db.query(ComplianceViolation)
    if start_date:
        total_query = total_query.filter(ComplianceViolation.report_date >= start_date)
    if end_date:
        total_query = total_query.filter(ComplianceViolation.report_date <= end_date)
        
    total_violations = total_query.count()
    critical_count = total_query.filter(ComplianceViolation.severity == "Critical").count()
    high_count = total_query.filter(ComplianceViolation.severity == "High").count()
    medium_count = total_query.filter(ComplianceViolation.severity == "Medium").count()
    
    # 2. Format as context prompt
    score_str = ", ".join([f"{s['period']}: {s['score']}%" for s in score_trend])
    freq_str = ", ".join([f"{f['type']}: {f['count']} findings" for f in violation_freq])
    
    timeframe_str = ""
    if start_date or end_date:
        start_str = start_date.strftime("%Y-%m-%d") if start_date else "inception"
        end_str = end_date.strftime("%Y-%m-%d") if end_date else "present"
        timeframe_str = f"Timeframe: {start_str} to {end_str}\n"
        
    context = f"""You are a Principal AI Compliance Director reporting to the board.
    
We have compiled the following historical compliance metrics:
{timeframe_str}- Total Identified Violations: {total_violations}
- Severity breakdown: Critical: {critical_count}, High: {high_count}, Medium: {medium_count}
- Average Compliance Score Trend: {score_str if score_str else "No data for this period"}
- Top Recurring Findings: {freq_str if freq_str else "No data for this period"}

User request/focus: {query_prompt if query_prompt else "Provide an executive summary of compliance trends."}

INSTRUCTION:
Write a highly professional, concise, narrative trend summary (2-3 sentences max). Cite statistics directly.
Example: "Critical violations increased 23% during the last quarter, mainly driven by MFA and access control policy failures. Average compliance score stabilized at 82.5%."
Do not include any greeting or conversational filler. Output the executive summary directly.
"""
    try:
        if total_violations == 0:
            return "No audit logs or violations recorded yet for this period. Generate compliance reports or adjust the query filters to view trends."
        return _call_ollama(context)
    except Exception as exc:
        logger.error(f"Failed to generate trend summary: {exc}")
        return "Failed to generate AI trend summary due to LLM timeout."
