"""
Compliance and audit report router.
POST /api/v1/compliance/report     — generate structured report + save to DB
POST /api/v1/compliance/risk       — assess risk without saving
GET  /api/v1/compliance/history    — list all audit reports
GET  /api/v1/compliance/history/{id} — get single report
DELETE /api/v1/compliance/history/{id} — delete report
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.dependencies import get_admin, get_current_user
from app.core.logging import get_logger
from app.crud.audit_report import crud_audit_report
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import (
    AuditReportListItem,
    AuditReportResponse,
    ComplianceReportResponse,
)
from app.schemas.dashboard import RiskAssessmentResponse
from app.services.compliance_service import (
    assess_risk,
    calculate_compliance_score,
    generate_compliance_report,
)
from app.services.rag_service import get_chunks_by_type

router = APIRouter(prefix="/compliance", tags=["Compliance"])
logger = get_logger(__name__)


@router.post(
    "/report",
    response_model=ComplianceReportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a compliance report and persist to database",
)
def create_compliance_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Orchestrates the full compliance pipeline:
    1. Retrieve policy and regulation chunks from ChromaDB
    2. Call the LLM to produce a structured JSON report
    3. Persist to Supabase and return the saved record
    """
    logger.info("Request received: Generate Compliance Report")
    logger.info("Authentication validated")

    logger.info("Chroma retrieval started")
    try:
        policy_chunks = get_chunks_by_type("policy")
        regulation_chunks = get_chunks_by_type("regulation")
    except Exception as exc:
        logger.error(f"Chroma retrieval failed: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"success": False, "error": "Chroma retrieval failed"}
        )

    if not policy_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No policy documents found. Upload a policy PDF first.",
        )
    if not regulation_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No regulation documents found. Upload a regulation PDF first.",
        )

    logger.info("Report generation started")
    logger.info("Ollama request started")
    from app.core.config import settings
    try:
        report = generate_compliance_report(policy_chunks, regulation_chunks)
        logger.info("Ollama response received")
    except Exception as exc:
        logger.error(f"Ollama report generation failed: {exc}", exc_info=True)
        if "localhost:11434" in settings.OLLAMA_BASE_URL or "127.0.0.1:11434" in settings.OLLAMA_BASE_URL:
            logger.warning("Ollama unavailable in Render environment")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"success": False, "error": "Ollama connection failed"}
        )

    if "raw_response" in report:
        logger.error(
            f"LLM returned unparseable output: {report['raw_response'][:300]}"
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "The AI model returned an invalid response. "
                "Please retry the request."
            ),
        )

    try:
        saved = crud_audit_report.create_from_dict(
            db,
            report=report,
            user_id=current_user.id,
        )
    except Exception as exc:
        logger.error(f"Database save compliance report failed: {exc}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": "Database connection failed"}
        )

    logger.info(
        f"Compliance report saved: id={saved.id} "
        f"risk={saved.risk} user_id={current_user.id}"
    )
    logger.info("Report generation completed")

    import json

    return ComplianceReportResponse(
        violation=report.get("violation", False),
        issues=(
            json.loads(saved.issues)
            if isinstance(saved.issues, str)
            else saved.issues
        ),
        recommendations=(
            json.loads(saved.recommendations)
            if isinstance(saved.recommendations, str)
            else saved.recommendations
        ),
        risk=saved.risk,
        compliance_score=saved.compliance_score,
        violation_count=saved.violation_count,
        audit_timestamp=saved.audit_timestamp,
        auditor=saved.auditor,
        id=saved.id,
    )


@router.post(
    "/risk",
    response_model=RiskAssessmentResponse,
    summary="Perform a risk assessment without persisting",
)
def assess_compliance_risk(
    current_user: User = Depends(get_current_user),
):
    """
    Run the compliance pipeline and return a risk assessment.
    No database write occurs.
    """
    policy_chunks = get_chunks_by_type("policy")
    regulation_chunks = get_chunks_by_type("regulation")

    if not policy_chunks or not regulation_chunks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Both policy and regulation documents are required. "
                "Upload both document types before running a risk assessment."
            ),
        )

    report = generate_compliance_report(policy_chunks, regulation_chunks)

    if "raw_response" in report:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="AI model returned an invalid response. Please retry.",
        )

    issues = report.get("issues", [])
    return RiskAssessmentResponse(
        risk=assess_risk(issues),
        issue_count=len(issues),
        compliance_score=calculate_compliance_score(issues),
    )


@router.get(
    "/history",
    response_model=list[AuditReportListItem],
    summary="List all audit reports",
)
def list_audit_reports(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = crud_audit_report.get_ordered(db, skip=skip, limit=limit)
    logger.info(f"Audit history: returned {len(reports)} records")
    return reports


@router.get(
    "/history/{report_id}",
    response_model=AuditReportResponse,
    summary="Get a single audit report by ID",
)
def get_audit_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = crud_audit_report.get(db, report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit report {report_id} not found.",
        )
    return report


@router.delete(
    "/history/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an audit report (admin only)",
)
def delete_audit_report(
    report_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin),
):
    deleted = crud_audit_report.delete(db, report_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit report {report_id} not found.",
        )
    logger.info(f"Audit report deleted: id={report_id}")
