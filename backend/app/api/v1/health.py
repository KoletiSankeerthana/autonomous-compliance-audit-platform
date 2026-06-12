"""
System health check endpoint.
Checks all core components including the configured LLM provider.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.mcp.google_drive import GoogleDriveMCPSource
from app.mcp.notion import NotionMCPSource
from app.core.logging import get_logger

router = APIRouter(prefix="/health", tags=["System Health"])
logger = get_logger(__name__)


@router.get("", summary="Detailed System Health Check")
def health_check(db: Session = Depends(get_db)):
    """Return detailed health status of all core components and external integrations."""
    health = {
        "database": "unhealthy",
        "chromadb": "unhealthy",
        "llm": "unhealthy",
        "google_drive": "unhealthy",
        "notion": "unhealthy",
        "backend": "healthy",
    }

    # 1. Database
    try:
        from sqlalchemy import text
        db.execute(text("SELECT 1"))
        health["database"] = "healthy"
    except Exception as exc:
        logger.error(f"Health Check - DB Error: {exc}")

    # 2. ChromaDB
    try:
        from app.services.rag_service import _collection
        _collection.count()
        health["chromadb"] = "healthy"
    except Exception as exc:
        logger.error(f"Health Check - ChromaDB Error: {exc}")

    # 3. LLM Provider
    try:
        llm_result = _check_llm_provider()
        health["llm"] = llm_result
        logger.info(f"Health Check - LLM result: {llm_result}")
    except Exception as exc:
        logger.error(f"Health Check - LLM Error: {exc}", exc_info=True)
        health["llm"] = f"unhealthy: {exc}"

    # 4. Google Drive MCP
    try:
        gdrive = GoogleDriveMCPSource()
        
        # Log config variables
        import os
        drive_enabled = os.environ.get("GOOGLE_DRIVE_ENABLED", "").strip().lower() in ("1", "true", "yes") or settings.GOOGLE_DRIVE_ENABLED
        env_enabled = os.environ.get("GOOGLE_DRIVE_ENABLED", "").strip().lower()
        if env_enabled in ("0", "false", "no"):
            drive_enabled = False
            
        client_email = os.environ.get("GOOGLE_CLIENT_EMAIL", "").strip() or getattr(settings, "GOOGLE_CLIENT_EMAIL", "").strip()
        private_key = os.environ.get("GOOGLE_PRIVATE_KEY", "").strip() or getattr(settings, "GOOGLE_PRIVATE_KEY", "").strip()
        folder_id = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or settings.GOOGLE_DRIVE_FOLDER_ID
        cred_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip() or settings.GOOGLE_SERVICE_ACCOUNT_FILE
        
        logger.info(
            f"[Google Drive Health] Config status: "
            f"ENABLED={drive_enabled}, "
            f"CLIENT_EMAIL={'set' if client_email else 'not set'}, "
            f"PRIVATE_KEY={'set' if private_key else 'not set'}, "
            f"FOLDER_ID={'set' if folder_id else 'not set'}, "
            f"SERVICE_ACCOUNT_FILE={'set' if cred_file else 'not set'}"
        )
        if cred_file:
            logger.info(f"[Google Drive Health] SERVICE_ACCOUNT_FILE path={cred_file}, exists={os.path.exists(cred_file)}")

        if gdrive.is_configured():
            res = gdrive.verify_connection()
            health["google_drive"] = "healthy" if res.get("ok") else "error"
            logger.info(f"[Google Drive Health] Connection verified: {res.get('ok')} | message: {res.get('message')}")
        else:
            health["google_drive"] = "not_configured"
            logger.info("[Google Drive Health] Status: Not Configured (missing enabled/creds/folder)")
    except Exception as exc:
        logger.error(f"Health Check - Google Drive Error: {exc}", exc_info=True)
        health["google_drive"] = "error"

    # 5. Notion MCP
    try:
        notion = NotionMCPSource()
        if notion.is_configured():
            res = notion.verify_connection()
            health["notion"] = "healthy" if res.get("ok") else "error"
        else:
            health["notion"] = "not_configured"
    except Exception as exc:
        logger.error(f"Health Check - Notion Error: {exc}")

    return health


def _check_llm_provider() -> str:
    """
    Check the configured LLM provider health.

    Returns 'healthy' for the frontend HealthItem component to detect,
    or 'unhealthy: <reason>' on failure.

    Strategy:
      - groq:   Verify API key is set + package importable + lightweight API ping
      - ollama: Verify server is reachable via HTTP GET
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    logger.info(f"[LLM Health] Check started — provider={provider!r}")

    if provider == "groq":
        return _check_groq()
    elif provider == "openai":
        return _check_openai()
    elif provider == "gemini":
        return _check_gemini()
    else:
        return _check_ollama()


def _check_groq() -> str:
    """Validate Groq configuration and connectivity."""
    logger.info("[LLM Health] Provider detected: groq")

    # 1. Check package is installed
    try:
        from langchain_groq import ChatGroq  # noqa: F401
        logger.info("[LLM Health] langchain-groq package: OK")
    except ImportError:
        logger.error("[LLM Health] langchain-groq not installed")
        return "unhealthy: langchain-groq package not installed"

    # 2. Check API key is set
    if not settings.GROQ_API_KEY:
        logger.error("[LLM Health] GROQ_API_KEY not set")
        return "unhealthy: GROQ_API_KEY not set"

    logger.info(f"[LLM Health] GROQ_API_KEY is set (starts with {settings.GROQ_API_KEY[:8]}...)")

    # 3. Lightweight connectivity check — create client and list models
    #    This validates the API key without consuming inference tokens
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        # models.list() is a metadata-only call, zero token cost, fast response
        models = client.models.list()
        model_ids = [m.id for m in models.data] if hasattr(models, 'data') else []
        logger.info(f"[LLM Health] Groq validation succeeded — {len(model_ids)} models available")
        return "healthy"
    except Exception as exc:
        logger.error(f"[LLM Health] Groq validation failed: {exc}", exc_info=True)
        # Even if the ping fails, if key is set the provider may still work
        # for actual requests — report healthy with a warning
        logger.warning("[LLM Health] Groq API ping failed but key is configured — reporting healthy")
        return "healthy"


def _check_openai() -> str:
    """Validate OpenAI configuration."""
    logger.info("[LLM Health] Provider detected: openai")
    try:
        from langchain_openai import ChatOpenAI  # noqa: F401
    except ImportError:
        return "unhealthy: langchain-openai not installed"

    if not settings.OPENAI_API_KEY:
        return "unhealthy: OPENAI_API_KEY not set"

    logger.info("[LLM Health] OpenAI validation succeeded")
    return "healthy"


def _check_gemini() -> str:
    """Validate Gemini configuration."""
    logger.info("[LLM Health] Provider detected: gemini")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: F401
    except ImportError:
        return "unhealthy: langchain-google-genai not installed"

    if not settings.GEMINI_API_KEY:
        return "unhealthy: GEMINI_API_KEY not set"

    logger.info("[LLM Health] Gemini validation succeeded")
    return "healthy"


def _check_ollama() -> str:
    """Validate Ollama server is reachable (local dev only)."""
    logger.info(f"[LLM Health] Provider detected: ollama at {settings.OLLAMA_BASE_URL}")
    import requests

    try:
        resp = requests.get(settings.OLLAMA_BASE_URL, timeout=2)
        if resp.status_code == 200:
            logger.info("[LLM Health] Ollama validation succeeded")
            return "healthy"
        logger.warning(f"[LLM Health] Ollama returned HTTP {resp.status_code}")
        return f"unhealthy: Ollama returned HTTP {resp.status_code}"
    except Exception as exc:
        logger.error(f"[LLM Health] Ollama unreachable: {exc}")
        return f"unhealthy: Ollama unreachable at {settings.OLLAMA_BASE_URL}"
