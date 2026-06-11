"""
Query Router Workflow.
Orchestrates routing of user prompts to RAG, Audit, or Trend analysis agents.
"""

import time
from typing import Any, Optional, TypedDict
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from app.core.config import settings
from app.core.logging import get_logger
from app.services.compliance_service import _call_ollama
from app.services.rag_service import retrieve_chunks, generate_answer
from app.services.analytics_service import generate_ai_trend_summary
from app.agents.workflow import run_compliance_workflow

logger = get_logger(__name__)

class RouterState(TypedDict, total=False):
    # Inputs
    query: str
    user_id: Optional[int]
    
    # Outputs
    route: str
    content: str
    saved_report_id: Optional[int]
    error: Optional[str]

def classify_query(query: str) -> str:
    """Classify the user's query into one of three execution categories."""
    prompt = f"""You are a Router Agent for an Enterprise Compliance Platform.
    
Classify the user query into exactly one of these categories:
1. "trend_analysis": If the user is asking about historical trends, changes over time, compliance scores rising/falling, recurring findings, department comparisons, or severity changes (e.g. "How did violations change last quarter?", "Show trend of risk categories", "Which department has the most findings?").
2. "compliance_analysis": If the user is asking to run a side-by-side gap audit or analyze a policy against a regulation (e.g. "Run a compliance report", "Audit our password policy against ISO 27001", "Analyze gap between regulation and policy").
3. "rag_question": If the user is asking a direct question about policy details, facts, rules, or requirements (e.g. "What is the password length requirement?", "Do we require MFA for admins?", "What does section 3.2 say?").

Query: "{query}"

CRITICAL: Return ONLY one of these strings: "trend_analysis", "compliance_analysis", or "rag_question". Do not include any other text, punctuation, or markdown.
"""
    try:
        response = _call_ollama(prompt).strip().lower()
        if "trend" in response:
            return "trend_analysis"
        if "compliance" in response or "audit" in response:
            return "compliance_analysis"
        return "rag_question"
    except Exception as exc:
        logger.warning(f"LLM classification failed: {exc}. Using keyword heuristics.")
        q_lower = query.lower()
        if any(w in q_lower for w in ["trend", "history", "change", "over time", "increase", "decrease", "quarter", "month", "recurring"]):
            return "trend_analysis"
        if any(w in q_lower for w in ["audit", "analyze", "gap", "compare policy"]):
            return "compliance_analysis"
        return "rag_question"

# ---- Node Functions ----

def classify_node(state: RouterState) -> RouterState:
    t = time.monotonic()
    logger.info("[router_workflow] classify_node ENTER")
    query = state.get("query", "")
    route = classify_query(query)
    logger.info(f"[router_workflow] classify_node EXIT - query routed to '{route}' in {time.monotonic()-t:.2f}s")
    return {**state, "route": route}

def rag_node(state: RouterState) -> RouterState:
    t = time.monotonic()
    logger.info("[router_workflow] rag_node ENTER")
    query = state.get("query", "")
    try:
        results = retrieve_chunks(query)
        chunks = results.get("documents", [])
        metadatas = results.get("metadata", [])
        distances = results.get("distances", [])
        
        formatted_chunks = []
        import uuid
        for doc, meta, dist in zip(chunks, metadatas, distances):
            fname = meta.get("filename") or meta.get("drive_file_name") or "Unknown"
            chunk_id = meta.get("id", str(uuid.uuid4())[:8])
            conf = max(0.0, 100.0 - (float(dist) * 100.0)) if dist is not None else 0.0
            page_num = meta.get("page_number", "N/A")
            heading = meta.get("section_heading", "N/A")
            header = f"[File Name: {fname} | Page: {page_num} | Chunk: {chunk_id} | Section: {heading} | Confidence: {conf:.1f}%]"
            formatted_chunks.append(f"{header}\n{doc}")
            
        answer = generate_answer(query, formatted_chunks, comparison_mode=False)
        return {**state, "content": answer}
    except Exception as exc:
        logger.error(f"[router_workflow] RAG node failed: {exc}", exc_info=True)
        return {**state, "error": str(exc)}

def compliance_node(state: RouterState) -> RouterState:
    t = time.monotonic()
    logger.info("[router_workflow] compliance_node ENTER")
    user_id = state.get("user_id")
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        # Run standard compliance workflow
        res = run_compliance_workflow(
            policy_type="policy",
            regulation_type="regulation",
            user_id=user_id,
            db=db,
        )
        if res.get("error"):
            return {**state, "error": res["error"]}
        
        report_data = res.get("final_report", {})
        saved_id = res.get("saved_report_id")
        
        summary = (
            f"### Compliance Audit Report Generated (ID: {saved_id})\n\n"
            f"**Risk level**: {report_data.get('risk_level')}\n"
            f"**Compliance Score**: {report_data.get('compliance_score')}%\n"
            f"**Total Violations**: {report_data.get('total_violations')}\n\n"
            f"**Executive Summary**:\n{report_data.get('executive_summary')}\n"
        )
        return {**state, "content": summary, "saved_report_id": saved_id}
    except Exception as exc:
        logger.error(f"[router_workflow] Compliance node failed: {exc}", exc_info=True)
        return {**state, "error": str(exc)}
    finally:
        db.close()

def trend_node(state: RouterState) -> RouterState:
    t = time.monotonic()
    logger.info("[router_workflow] trend_node ENTER")
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        query = state.get("query", "")
        summary = generate_ai_trend_summary(db, query)
        return {**state, "content": summary}
    except Exception as exc:
        logger.error(f"[router_workflow] Trend node failed: {exc}", exc_info=True)
        return {**state, "error": str(exc)}
    finally:
        db.close()

# ---- LangGraph Construction ----

try:
    from langgraph.graph import StateGraph, START, END
    
    def build_router_workflow() -> Any:
        graph = StateGraph(RouterState)
        
        graph.add_node("classify", classify_node)
        graph.add_node("rag", rag_node)
        graph.add_node("compliance", compliance_node)
        graph.add_node("trend", trend_node)
        
        graph.add_edge(START, "classify")
        
        # Conditional edge based on classification
        def route_decision(state: RouterState) -> str:
            return state.get("route", "rag_question")
            
        graph.add_conditional_edges(
            "classify",
            route_decision,
            {
                "rag_question": "rag",
                "compliance_analysis": "compliance",
                "trend_analysis": "trend"
            }
        )
        
        graph.add_edge("rag", END)
        graph.add_edge("compliance", END)
        graph.add_edge("trend", END)
        
        return graph.compile()
        
    _USE_LANGGRAPH = True
except ImportError:
    _USE_LANGGRAPH = False

def _run_sequential(initial_state: RouterState) -> RouterState:
    state = classify_node(initial_state)
    route = state.get("route")
    if route == "trend_analysis":
        state = trend_node(state)
    elif route == "compliance_analysis":
        state = compliance_node(state)
    else:
        state = rag_node(state)
    return state

def run_query_router(query: str, user_id: Optional[int] = None) -> RouterState:
    """Unified entry point to run query routing and execution."""
    timeout = settings.WORKFLOW_TIMEOUT_SECONDS
    initial_state: RouterState = {"query": query, "user_id": user_id}
    
    t_start = time.monotonic()
    logger.info(f"[router_workflow] Executing query: {query[:100]!r}")
    
    state = initial_state
    if _USE_LANGGRAPH:
        try:
            graph = build_router_workflow()
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(graph.invoke, initial_state)
                try:
                    state = future.result(timeout=timeout)
                except FutureTimeoutError:
                    future.cancel()
                    state = _run_sequential(initial_state)
        except Exception as exc:
            logger.error(f"[router_workflow] LangGraph failed: {exc}", exc_info=True)
            state = _run_sequential(initial_state)
    else:
        state = _run_sequential(initial_state)
        
    elapsed = time.monotonic() - t_start
    logger.info(f"[router_workflow] Query resolution complete in {elapsed:.2f}s (Route: {state.get('route')})")
    return state
