"""
Workflow router.
POST /api/v1/workflow/run — execute the full multi-agent compliance pipeline
GET  /api/v1/workflow/status/{id} — retrieve completed workflow result
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.agents.workflow import WorkflowState, run_compliance_workflow
from app.core.dependencies import get_current_user
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.user import User

router = APIRouter(prefix="/workflow", tags=["AI Workflow"])
logger = get_logger(__name__)


class WorkflowRunRequest(BaseModel):
    """Request body for triggering a workflow run."""
    policy_type: str = "policy"
    regulation_type: str = "regulation"


class WorkflowRunResponse(BaseModel):
    """Summary result returned after a workflow run."""
    success: bool
    saved_report_id: Optional[int] = None
    risk_level: Optional[str] = None
    compliance_score: Optional[int] = None
    total_violations: Optional[int] = None
    executive_summary: Optional[str] = None
    error: Optional[str] = None


@router.post(
    "/run",
    response_model=WorkflowRunResponse,
    status_code=status.HTTP_200_OK,
    summary="Run the full multi-agent compliance workflow",
)
def run_workflow(
    payload: WorkflowRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes the complete AI pipeline:
    Document Retrieval -> Compliance Agent -> Risk Agent -> Report Agent -> Persist

    Returns the final report summary including the saved audit report ID.
    """
    logger.info("Request received: Run Workflow")
    logger.info("Authentication validated")

    logger.info("Report generation started")
    try:
        final_state: WorkflowState = run_compliance_workflow(
            policy_type=payload.policy_type,
            regulation_type=payload.regulation_type,
            user_id=current_user.id,
            db=db,
        )
    except Exception as e:
        logger.exception("Workflow failed")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "error": f"Workflow failed: {str(e)}"}
        )

    if final_state.get("error"):
        error_msg = final_state["error"]
        logger.error(f"Workflow failed: {error_msg}")
        
        # Categorise/Improve errors:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
        friendly_error = error_msg
        if "ChromaDB" in error_msg or "retrieve_documents" in error_msg:
            friendly_error = "Chroma retrieval failed"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        elif any(kw in error_msg for kw in ["LLM", "provider", "Ollama", "connection", "API key", "groq", "openai", "gemini"]):
            friendly_error = "LLM provider unavailable"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            from app.core.config import settings
            logger.warning(f"LLM failure in workflow: provider={settings.LLM_PROVIDER!r}")
        elif any(kw in error_msg for kw in ["Database", "persist", "Session"]):
            friendly_error = "Database connection failed"
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            
        return JSONResponse(
            status_code=status_code,
            content={"success": False, "error": friendly_error}
        )

    final_report = final_state.get("final_report", {})

    logger.info(
        f"Workflow complete: saved_id={final_state.get('saved_report_id')} "
        f"user_id={current_user.id}"
    )
    logger.info("Report generation completed")

    return WorkflowRunResponse(
        success=True,
        saved_report_id=final_state.get("saved_report_id"),
        risk_level=final_report.get("risk_level"),
        compliance_score=final_report.get("compliance_score"),
        total_violations=final_report.get("total_violations"),
        executive_summary=final_report.get("executive_summary"),
    )

