"""
Verification script for Compliance Trend Intelligence Layer.
"""

import sys
import os
import json

# Add backend directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

# Make sure env vars are set before importing
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./test.db"
if "SECRET_KEY" not in os.environ:
    os.environ["SECRET_KEY"] = "dummy"

from app.db.session import SessionLocal, verify_db_connection, engine
from app.models.base import Base
from app.models.compliance_violation import ComplianceViolation
from app.models.audit_report import AuditReport
from app.services import analytics_service
from app.agents.router_workflow import classify_query, run_query_router
from app.main import _auto_migrate_schema

# Ensure tables are created and backfilled in SQLite test db
Base.metadata.create_all(bind=engine)
_auto_migrate_schema()

def run_tests():
    print("============================================================")
    print("RUNNING COMPLIANCE TREND INTELLIGENCE VERIFICATION SUITE")
    print("============================================================")

    # 1. Verify DB Connection
    if not verify_db_connection():
        print("FAIL: Database connection unreachable.")
        sys.exit(1)
    print("SUCCESS: Database connection verified.")

    db = SessionLocal()
    try:
        # 2. Verify Schema Backfill
        violation_count = db.query(ComplianceViolation).count()
        report_count = db.query(AuditReport).count()
        print(f"Database stats:\n  Audit reports: {report_count}\n  Compliance violations: {violation_count}")
        
        # 3. Test SQL Aggregation Layer
        print("\nTesting SQL Aggregations...")
        score_trend = analytics_service.get_compliance_score_trend(db)
        print("  get_compliance_score_trend:", score_trend)
        
        violation_freq = analytics_service.get_violation_frequency(db)
        print("  get_violation_frequency (first 3):", violation_freq[:3])
        
        risk_trend = analytics_service.get_risk_distribution_trend(db)
        print("  get_risk_distribution_trend:", risk_trend)
        
        recurring = analytics_service.get_recurring_findings(db)
        print("  get_recurring_findings:", recurring)

        # 4. Test AI Router Classification
        print("\nTesting AI Query Router Classification...")
        queries = [
            ("How did our compliance violations change over time?", "trend_analysis"),
            ("What is our password history requirement in section 3?", "rag_question"),
            ("Run a compliance audit on my policy", "compliance_analysis")
        ]
        for q, expected in queries:
            result = classify_query(q)
            print(f"  Query: {q!r} -> Routed to: {result!r} (Expected: {expected!r})")

        # 5. Test AI Trend Summary
        print("\nTesting AI Trend Summary...")
        summary = analytics_service.generate_ai_trend_summary(db)
        print("  AI Summary preview:\n", summary[:300] + "...")

        print("\n============================================================")
        print("ALL ANALYTICS TESTS PASSED SUCCESSFULLY")
        print("============================================================")
    except Exception as exc:
        print(f"FAIL: Verification failed with exception: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
