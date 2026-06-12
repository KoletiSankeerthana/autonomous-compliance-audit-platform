"""
LangGraph workflow orchestration.

Graph topology:
  START
    -> retrieve_documents
      -> run_compliance_agent
        -> run_risk_agent
          -> run_report_agent
            -> persist_report
              -> END

State flows through the graph as a typed dict.
Each node is a pure function that accepts and returns state.

Execution is wrapped in a ThreadPoolExecutor with a hard deadline
(WORKFLOW_TIMEOUT_SECONDS from config) to prevent indefinite hangs.
If LangGraph fails or times out, the nodes execute sequentially as fallback.
"""

import time
from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from typing import Any, Optional, TypedDict

from app.agents.compliance_agent import ComplianceAgent
from app.agents.report_agent import ReportAgent
from app.agents.risk_agent import RiskAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.services.rag_service import get_chunks_by_type

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# State schema
# ---------------------------------------------------------------------------


class WorkflowState(TypedDict, total=False):
    """Typed state shared across all nodes in the workflow graph."""
    # Input
    policy_type: str
    regulation_type: str
    triggered_by_user_id: Optional[int]

    # Populated by retrieve_documents
    policy_chunks: list[str]
    regulation_chunks: list[str]

    # Populated by compliance agent
    compliance_analysis: dict

    # Populated by risk agent
    risk_assessment: dict

    # Populated by report agent
    final_report: dict

    # Populated by persist_report
    saved_report_id: Optional[int]

    # Set by any node on failure
    error: Optional[str]


# ---------------------------------------------------------------------------
# Agent singletons
# ---------------------------------------------------------------------------

_compliance_agent = ComplianceAgent()
_risk_agent = RiskAgent()
_report_agent = ReportAgent()


# ---------------------------------------------------------------------------
# Node functions — each logs entry/exit with elapsed time
# ---------------------------------------------------------------------------


def retrieve_documents(state: WorkflowState) -> WorkflowState:
    """Fetch policy and regulation chunks from ChromaDB."""
    t = time.monotonic()
    logger.info("Chroma retrieval started")
    logger.info("[retrieve_documents] ENTER")
    try:
        policy_type = state.get("policy_type", "policy")
        regulation_type = state.get("regulation_type", "regulation")

        policy_chunks = get_chunks_by_type(policy_type)
        regulation_chunks = get_chunks_by_type(regulation_type)

        logger.info(
            f"[retrieve_documents] EXIT in {time.monotonic()-t:.2f}s — "
            f"policy={len(policy_chunks)} chunks regulation={len(regulation_chunks)} chunks"
        )

        if not policy_chunks:
            return {**state, "error": f"No documents of type '{policy_type}' found in ChromaDB. Upload a PDF first."}
        if not regulation_chunks:
            return {**state, "error": f"No documents of type '{regulation_type}' found in ChromaDB. Upload a PDF first."}

        return {**state, "policy_chunks": policy_chunks, "regulation_chunks": regulation_chunks}

    except Exception as exc:
        logger.error(f"[retrieve_documents] EXCEPTION: {exc}", exc_info=True)
        return {**state, "error": f"retrieve_documents failed: {exc}"}


def run_compliance_agent(state: WorkflowState) -> WorkflowState:
    """Execute the ComplianceAgent to produce a structured gap analysis."""
    if state.get("error"):
        logger.warning("[run_compliance_agent] SKIPPED — upstream error present")
        return state

    t = time.monotonic()
    logger.info("Ollama request started")
    logger.info("[run_compliance_agent] ENTER")
    try:
        result = _compliance_agent.run(state)

        if "error" in result:
            logger.error(f"[run_compliance_agent] AGENT ERROR: {result['error']}")
            return {**state, "error": result["error"]}

        logger.info("Ollama response received")
        logger.info(f"[run_compliance_agent] EXIT in {time.monotonic()-t:.2f}s")
        return {**state, **result}

    except Exception as exc:
        logger.error(f"[run_compliance_agent] EXCEPTION: {exc}", exc_info=True)
        return {**state, "error": f"run_compliance_agent failed: {exc}"}


def run_risk_agent(state: WorkflowState) -> WorkflowState:
    """Execute the RiskAgent to classify issues and build mitigation roadmap."""
    if state.get("error"):
        logger.warning("[run_risk_agent] SKIPPED — upstream error present")
        return state

    t = time.monotonic()
    logger.info("[run_risk_agent] ENTER")
    try:
        result = _risk_agent.run(state)

        if "error" in result:
            logger.error(f"[run_risk_agent] AGENT ERROR: {result['error']}")
            return {**state, "error": result["error"]}

        logger.info(f"[run_risk_agent] EXIT in {time.monotonic()-t:.2f}s")
        return {**state, **result}

    except Exception as exc:
        logger.error(f"[run_risk_agent] EXCEPTION: {exc}", exc_info=True)
        return {**state, "error": f"run_risk_agent failed: {exc}"}


def run_report_agent(state: WorkflowState) -> WorkflowState:
    """Execute the ReportAgent to synthesise the final audit report."""
    if state.get("error"):
        logger.warning("[run_report_agent] SKIPPED — upstream error present")
        return state

    t = time.monotonic()
    logger.info("[run_report_agent] ENTER")
    try:
        result = _report_agent.run(state)

        if "error" in result:
            logger.error(f"[run_report_agent] AGENT ERROR: {result['error']}")
            return {**state, "error": result["error"]}

        logger.info(f"[run_report_agent] EXIT in {time.monotonic()-t:.2f}s")
        return {**state, **result}

    except Exception as exc:
        logger.error(f"[run_report_agent] EXCEPTION: {exc}", exc_info=True)
        return {**state, "error": f"run_report_agent failed: {exc}"}


def persist_report(state: WorkflowState, db=None) -> WorkflowState:
    """
    Persist the final report to the database.
    db is injected at call time — not through LangGraph's state.
    """
    if state.get("error"):
        logger.warning("[persist_report] SKIPPED — upstream error present")
        return state

    if not db:
        logger.warning("[persist_report] No db session provided — skipping persistence.")
        return state

    t = time.monotonic()
    logger.info("[persist_report] ENTER")
    try:
        final_report: dict = state.get("final_report", {})
        if not final_report:
            return {**state, "error": "No final_report in state to persist."}

        from app.crud.audit_report import crud_audit_report

        report_dict = {
            "risk": final_report.get("risk_level", "Unknown"),
            "compliance_score": final_report.get("compliance_score", 0),
            "violation_count": final_report.get("total_violations", 0),
            "issues": final_report.get("issues", []),
            "recommendations": final_report.get("recommendations", []),
            "audit_timestamp": final_report.get("audit_timestamp", ""),
            "auditor": final_report.get("auditor", "Compliance AI Platform"),
        }

        saved = crud_audit_report.create_from_dict(
            db,
            report=report_dict,
            user_id=state.get("triggered_by_user_id"),
        )
        logger.info(
            f"[persist_report] EXIT in {time.monotonic()-t:.2f}s — saved id={saved.id}"
        )
        return {**state, "saved_report_id": saved.id}

    except Exception as exc:
        logger.error(f"[persist_report] EXCEPTION: {exc}", exc_info=True)
        return {**state, "error": f"persist_report failed: {exc}"}


# ---------------------------------------------------------------------------
# Sequential executor (used as fallback and by the timeout wrapper)
# ---------------------------------------------------------------------------


def _run_sequential(initial_state: WorkflowState) -> WorkflowState:
    """Execute all workflow nodes in sequence without LangGraph."""
    state = retrieve_documents(initial_state)
    state = run_compliance_agent(state)
    state = run_risk_agent(state)
    state = run_report_agent(state)
    return state


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


try:
    from langgraph.graph import END, START, StateGraph

    def build_compliance_workflow() -> Any:
        """
        Construct and compile the LangGraph StateGraph.
        Returns a compiled graph that can be invoked with:
            graph.invoke(initial_state)
        """
        graph = StateGraph(WorkflowState)

        graph.add_node("retrieve_documents", retrieve_documents)
        graph.add_node("run_compliance_agent", run_compliance_agent)
        graph.add_node("run_risk_agent", run_risk_agent)
        graph.add_node("run_report_agent", run_report_agent)

        graph.add_edge(START, "retrieve_documents")
        graph.add_edge("retrieve_documents", "run_compliance_agent")
        graph.add_edge("run_compliance_agent", "run_risk_agent")
        graph.add_edge("run_risk_agent", "run_report_agent")
        graph.add_edge("run_report_agent", END)

        return graph.compile()

    _USE_LANGGRAPH = True
    logger.info("LangGraph workflow compiled successfully.")

except ImportError:
    logger.warning(
        "langgraph not installed. Falling back to sequential execution. "
        "Install with: pip install langgraph"
    )
    _USE_LANGGRAPH = False

    def build_compliance_workflow():
        """Fallback: sequential node execution without LangGraph."""
        return None


# ---------------------------------------------------------------------------
# Public runner
# ---------------------------------------------------------------------------


def run_compliance_workflow(
    policy_type: str = "policy",
    regulation_type: str = "regulation",
    user_id: Optional[int] = None,
    db=None,
) -> WorkflowState:
    """
    Entry point for the compliance workflow.

    Execution strategy:
    1. If LangGraph is available, invoke the compiled graph inside a
       ThreadPoolExecutor with a hard deadline of WORKFLOW_TIMEOUT_SECONDS.
    2. If LangGraph times out or raises, fall back to sequential node execution
       (also guarded by the same timeout).
    3. persist_report is always called with the db session directly, since
       LangGraph does not support injecting FastAPI dependencies into nodes.

    This guarantees the function always returns — it will never hang indefinitely.
    """
    timeout = settings.WORKFLOW_TIMEOUT_SECONDS
    initial_state: WorkflowState = {
        "policy_type": policy_type,
        "regulation_type": regulation_type,
        "triggered_by_user_id": user_id,
    }

    t_total = time.monotonic()
    logger.info(
        f"[workflow] START — policy_type={policy_type} regulation_type={regulation_type} "
        f"user_id={user_id} timeout={timeout}s"
    )

    state: WorkflowState = initial_state

    if _USE_LANGGRAPH:
        try:
            graph = build_compliance_workflow()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future: Future = executor.submit(graph.invoke, initial_state)
                try:
                    state = future.result(timeout=timeout)
                    logger.info(
                        f"[workflow] LangGraph execution complete in "
                        f"{time.monotonic()-t_total:.2f}s"
                    )
                except FutureTimeoutError:
                    logger.error(
                        f"[workflow] LangGraph timed out after {timeout}s. "
                        f"Falling back to sequential execution."
                    )
                    future.cancel()
                    state = _run_sequential(initial_state)
        except Exception as exc:
            logger.error(
                f"[workflow] LangGraph execution raised: {exc}. "
                f"Falling back to sequential execution.",
                exc_info=True,
            )
            state = _run_sequential(initial_state)
    else:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future: Future = executor.submit(_run_sequential, initial_state)
            try:
                state = future.result(timeout=timeout)
            except FutureTimeoutError:
                logger.error(
                    f"[workflow] Sequential execution timed out after {timeout}s."
                )
                future.cancel()
                state = {
                    **initial_state,
                    "error": f"Workflow timed out after {timeout}s. "
                    f"The LLM may be overloaded or unavailable.",
                }

    # Persist separately so we can pass the db session
    if db is not None and not state.get("error"):
        try:
            state = persist_report(state, db=db)
        except Exception as exc:
            logger.error(f"[workflow] Database persistence failed: {exc}", exc_info=True)
            state = {**state, "error": f"Database persistence failed: {exc}"}

    elapsed = time.monotonic() - t_total
    if state.get("error"):
        logger.error(f"[workflow] COMPLETE WITH ERROR in {elapsed:.2f}s: {state['error']}")
    else:
        logger.info(
            f"[workflow] COMPLETE in {elapsed:.2f}s — "
            f"saved_id={state.get('saved_report_id')}"
        )

    return state
