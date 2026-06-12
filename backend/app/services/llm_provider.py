"""
LLM Provider Abstraction Layer.

Exposes two public APIs:

    get_llm()        → returns a LangChain-compatible chat model instance
                       (ChatGroq for production, OllamaWrapper for local dev)

    call_llm(prompt) → convenience wrapper that calls get_llm().invoke(messages)
                       and returns the response text as a plain string

Provider selection via LLM_PROVIDER environment variable:
    LLM_PROVIDER=groq      → ChatGroq via langchain-groq  (PRODUCTION default)
    LLM_PROVIDER=openai    → ChatOpenAI via langchain-openai
    LLM_PROVIDER=gemini    → ChatGoogleGenerativeAI via langchain-google-genai
    LLM_PROVIDER=ollama    → direct ollama SDK  (LOCAL DEVELOPMENT only)

All agents, services, and endpoints import from this module — never from
individual SDK packages directly.
"""

import time
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Public API — get_llm()
# ---------------------------------------------------------------------------


def get_llm():
    """
    Return a LangChain-compatible chat model for the configured provider.

    Supported return types:
      - groq   → langchain_groq.ChatGroq
      - openai → langchain_openai.ChatOpenAI  (if installed)
      - gemini → langchain_google_genai.ChatGoogleGenerativeAI  (if installed)
      - ollama → _OllamaDirectWrapper (thin wrapper around the ollama SDK)

    Usage::

        llm = get_llm()
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content="Hello")])
        text = response.content

    Raises:
        RuntimeError: If the provider is misconfigured (e.g., missing API key).
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    logger.info(f"[LLM] get_llm() — provider={provider!r}")

    if provider == "groq":
        return _build_groq()
    elif provider == "openai":
        return _build_openai()
    elif provider == "gemini":
        return _build_gemini()
    else:
        return _OllamaDirectWrapper()


# ---------------------------------------------------------------------------
# Public API — call_llm()
# ---------------------------------------------------------------------------


def call_llm(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Send a prompt to the configured LLM provider and return the text response.

    This is the primary entry point used by all services.  Internally it calls
    get_llm() and invokes the model using LangChain message objects (for
    langchain-compatible providers) or directly via the ollama SDK.

    Args:
        prompt: The user message / task description.
        system_prompt: Optional system instruction.

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: If the provider call fails.
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    logger.info(f"[LLM] call_llm() — provider={provider!r} | prompt_len={len(prompt)}")
    t = time.monotonic()

    try:
        if provider == "ollama":
            # Direct ollama SDK — no LangChain dependency needed for local dev
            result = _call_ollama_direct(prompt)
        else:
            # LangChain path — works for groq, openai, gemini
            from langchain_core.messages import HumanMessage, SystemMessage

            llm = get_llm()
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))

            response = llm.invoke(messages)
            result = response.content

        elapsed = time.monotonic() - t
        logger.info(
            f"[LLM] call_llm() — provider={provider!r} | "
            f"response received in {elapsed:.2f}s | {len(result)} chars"
        )
        return result

    except Exception as exc:
        elapsed = time.monotonic() - t
        logger.error(
            f"[LLM] call_llm() — provider={provider!r} | FAILED after {elapsed:.2f}s: {exc}",
            exc_info=True,
        )
        raise RuntimeError(f"LLM provider '{provider}' request failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Provider builders
# ---------------------------------------------------------------------------


def _build_groq():
    """Return a ChatGroq instance (langchain-groq)."""
    try:
        from langchain_groq import ChatGroq
    except ImportError as e:
        raise RuntimeError(
            "langchain-groq is not installed. Run: pip install langchain-groq"
        ) from e

    if not settings.GROQ_API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. "
            "Add it to your Render environment variables."
        )

    logger.info(f"[LLM] Building ChatGroq — model={settings.GROQ_MODEL!r}")
    return ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=settings.GROQ_MODEL,
        temperature=0,
        max_tokens=4096,
    )


def _build_openai():
    """Return a ChatOpenAI instance (langchain-openai)."""
    try:
        from langchain_openai import ChatOpenAI
    except ImportError as e:
        raise RuntimeError(
            "langchain-openai is not installed. Run: pip install langchain-openai"
        ) from e

    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    logger.info(f"[LLM] Building ChatOpenAI — model={settings.OPENAI_MODEL!r}")
    return ChatOpenAI(
        openai_api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        temperature=0,
        max_tokens=4096,
    )


def _build_gemini():
    """Return a ChatGoogleGenerativeAI instance (langchain-google-genai)."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as e:
        raise RuntimeError(
            "langchain-google-genai is not installed. "
            "Run: pip install langchain-google-genai"
        ) from e

    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not set.")

    logger.info(f"[LLM] Building ChatGoogleGenerativeAI — model={settings.GEMINI_MODEL!r}")
    return ChatGoogleGenerativeAI(
        google_api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
        temperature=0,
    )


# ---------------------------------------------------------------------------
# Ollama direct path (local dev, no LangChain dependency)
# ---------------------------------------------------------------------------


def _call_ollama_direct(prompt: str) -> str:
    """Call a local Ollama instance using the ollama SDK (development only)."""
    try:
        import ollama
    except ImportError as e:
        raise RuntimeError(
            "ollama package is not installed. Run: pip install ollama\n"
            "Note: For production use LLM_PROVIDER=groq instead."
        ) from e

    logger.info(
        f"[LLM] Calling Ollama at {settings.OLLAMA_BASE_URL} — model={settings.OLLAMA_MODEL!r}"
    )
    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


class _OllamaDirectWrapper:
    """
    Thin wrapper around the ollama SDK that exposes a LangChain-compatible
    .invoke(messages) interface.  Used when LLM_PROVIDER=ollama so that
    get_llm() always returns something invocable.
    """

    class _FakeAIMessage:
        """Mimics langchain_core.messages.AIMessage.content."""
        def __init__(self, content: str):
            self.content = content

    def invoke(self, messages) -> "_OllamaDirectWrapper._FakeAIMessage":
        # Extract text content from LangChain message objects or plain dicts
        if messages:
            last = messages[-1]
            if hasattr(last, "content"):
                prompt = last.content
            elif isinstance(last, dict):
                prompt = last.get("content", "")
            else:
                prompt = str(last)
        else:
            prompt = ""

        text = _call_ollama_direct(prompt)
        return self._FakeAIMessage(content=text)


# ---------------------------------------------------------------------------
# Health check helper  (used by GET /api/v1/health)
# ---------------------------------------------------------------------------


def check_llm_health() -> dict:
    """
    Verify the configured LLM provider is reachable and functional.

    Returns a dict:
        {
            "status":   "healthy" | "unhealthy",
            "provider": "groq" | "openai" | "gemini" | "ollama",
            "detail":   "Groq API reachable — model: llama3-8b-8192"
        }
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    logger.info(f"[LLM Health] Checking provider={provider!r}")

    try:
        if provider == "groq":
            return _health_groq()
        elif provider == "openai":
            return _health_openai()
        elif provider == "gemini":
            return _health_gemini()
        else:
            return _health_ollama()
    except Exception as exc:
        logger.error(f"[LLM Health] {provider!r} check raised: {exc}")
        return {
            "status": "unhealthy",
            "provider": provider,
            "detail": str(exc),
        }


def _health_groq() -> dict:
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        return {
            "status": "unhealthy",
            "provider": "groq",
            "detail": "langchain-groq not installed — run: pip install langchain-groq",
        }

    if not settings.GROQ_API_KEY:
        return {
            "status": "unhealthy",
            "provider": "groq",
            "detail": "GROQ_API_KEY not set in environment variables",
        }

    # Minimal ping to verify API key and connectivity
    from langchain_core.messages import HumanMessage
    llm = ChatGroq(
        groq_api_key=settings.GROQ_API_KEY,
        model_name=settings.GROQ_MODEL,
        temperature=0,
        max_tokens=1,
    )
    llm.invoke([HumanMessage(content="ping")])
    return {
        "status": "healthy",
        "provider": "groq",
        "detail": f"Groq API reachable — model: {settings.GROQ_MODEL}",
    }


def _health_openai() -> dict:
    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        return {
            "status": "unhealthy",
            "provider": "openai",
            "detail": "langchain-openai not installed",
        }

    if not settings.OPENAI_API_KEY:
        return {
            "status": "unhealthy",
            "provider": "openai",
            "detail": "OPENAI_API_KEY not set",
        }

    from langchain_core.messages import HumanMessage
    llm = ChatOpenAI(
        openai_api_key=settings.OPENAI_API_KEY,
        model=settings.OPENAI_MODEL,
        temperature=0,
        max_tokens=1,
    )
    llm.invoke([HumanMessage(content="ping")])
    return {
        "status": "healthy",
        "provider": "openai",
        "detail": f"OpenAI API reachable — model: {settings.OPENAI_MODEL}",
    }


def _health_gemini() -> dict:
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError:
        return {
            "status": "unhealthy",
            "provider": "gemini",
            "detail": "langchain-google-genai not installed",
        }

    if not settings.GEMINI_API_KEY:
        return {
            "status": "unhealthy",
            "provider": "gemini",
            "detail": "GEMINI_API_KEY not set",
        }

    from langchain_core.messages import HumanMessage
    llm = ChatGoogleGenerativeAI(
        google_api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
        temperature=0,
    )
    llm.invoke([HumanMessage(content="ping")])
    return {
        "status": "healthy",
        "provider": "gemini",
        "detail": f"Gemini API reachable — model: {settings.GEMINI_MODEL}",
    }


def _health_ollama() -> dict:
    import requests

    try:
        resp = requests.get(settings.OLLAMA_BASE_URL, timeout=2)
        if resp.status_code == 200:
            return {
                "status": "healthy",
                "provider": "ollama",
                "detail": (
                    f"Ollama reachable at {settings.OLLAMA_BASE_URL} "
                    f"— model: {settings.OLLAMA_MODEL}"
                ),
            }
        return {
            "status": "unhealthy",
            "provider": "ollama",
            "detail": f"Ollama returned HTTP {resp.status_code}",
        }
    except Exception as exc:
        return {
            "status": "unhealthy",
            "provider": "ollama",
            "detail": f"Ollama unreachable at {settings.OLLAMA_BASE_URL}: {exc}",
        }
