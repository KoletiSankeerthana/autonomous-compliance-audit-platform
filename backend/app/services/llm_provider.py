"""
LLM Provider Abstraction Layer.

Provides a single `call_llm(prompt)` function that routes to the configured
provider (Groq, OpenAI, Gemini, or Ollama for local dev) based on the
LLM_PROVIDER environment variable.

Usage:
    from app.services.llm_provider import call_llm

    response_text = call_llm("Analyse this document for compliance gaps...")

Provider selection via env var:
    LLM_PROVIDER=groq      → Groq API (default for production)
    LLM_PROVIDER=openai    → OpenAI API
    LLM_PROVIDER=gemini    → Google Gemini API
    LLM_PROVIDER=ollama    → Local Ollama (development only)
"""

import time
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Provider dispatch
# ---------------------------------------------------------------------------


def call_llm(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Send a prompt to the configured LLM provider and return the text response.

    Args:
        prompt: The user message / task description.
        system_prompt: Optional system instruction. If None, a sensible default
                       is applied per provider.

    Returns:
        The model's text response as a plain string.

    Raises:
        RuntimeError: If the provider call fails with a non-retriable error.
    """
    provider = settings.LLM_PROVIDER.lower().strip()
    logger.info(f"[LLM] Provider={provider!r} | Sending request...")
    t = time.monotonic()

    try:
        if provider == "groq":
            result = _call_groq(prompt, system_prompt)
        elif provider == "openai":
            result = _call_openai(prompt, system_prompt)
        elif provider == "gemini":
            result = _call_gemini(prompt, system_prompt)
        else:
            # Default: Ollama (local dev)
            result = _call_ollama(prompt)

        elapsed = time.monotonic() - t
        logger.info(f"[LLM] Provider={provider!r} | Response received in {elapsed:.2f}s | {len(result)} chars")
        return result

    except Exception as exc:
        elapsed = time.monotonic() - t
        logger.error(
            f"[LLM] Provider={provider!r} | FAILED after {elapsed:.2f}s: {exc}",
            exc_info=True,
        )
        raise RuntimeError(f"LLM provider '{provider}' request failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


def _call_groq(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Call the Groq API (Llama 3 / Mixtral inference)."""
    try:
        from groq import Groq
    except ImportError:
        raise RuntimeError(
            "groq package is not installed. Run: pip install groq"
        )

    api_key = settings.GROQ_API_KEY
    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to your environment variables."
        )

    client = Groq(api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _call_openai(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Call the OpenAI Chat Completions API."""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "openai package is not installed. Run: pip install openai"
        )

    api_key = settings.OPENAI_API_KEY
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your environment variables."
        )

    client = OpenAI(api_key=api_key)

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.1,
        max_tokens=4096,
    )
    return response.choices[0].message.content


def _call_gemini(prompt: str, system_prompt: Optional[str] = None) -> str:
    """Call the Google Gemini API."""
    try:
        import google.generativeai as genai
    except ImportError:
        raise RuntimeError(
            "google-generativeai package is not installed. "
            "Run: pip install google-generativeai"
        )

    api_key = settings.GEMINI_API_KEY
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Add it to your environment variables."
        )

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    full_prompt = prompt
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{prompt}"

    response = model.generate_content(full_prompt)
    return response.text


def _call_ollama(prompt: str) -> str:
    """Call a local Ollama instance (development only)."""
    try:
        import ollama
    except ImportError:
        raise RuntimeError(
            "ollama package is not installed. Run: pip install ollama"
        )

    response = ollama.chat(
        model=settings.OLLAMA_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response["message"]["content"]


# ---------------------------------------------------------------------------
# Health check helper
# ---------------------------------------------------------------------------


def check_llm_health() -> dict:
    """
    Verify the configured LLM provider is reachable and functional.

    Returns:
        {
            "status": "healthy" | "unhealthy",
            "provider": "groq",
            "detail": "Groq API reachable — model: llama3-8b-8192"
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
        logger.error(f"[LLM Health] {provider!r} check failed: {exc}")
        return {
            "status": "unhealthy",
            "provider": provider,
            "detail": str(exc),
        }


def _health_groq() -> dict:
    try:
        from groq import Groq
    except ImportError:
        return {
            "status": "unhealthy",
            "provider": "groq",
            "detail": "groq package not installed",
        }

    if not settings.GROQ_API_KEY:
        return {
            "status": "unhealthy",
            "provider": "groq",
            "detail": "GROQ_API_KEY not set",
        }

    client = Groq(api_key=settings.GROQ_API_KEY)
    # Minimal token call to verify API key validity
    client.chat.completions.create(
        model=settings.GROQ_MODEL,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
    )
    return {
        "status": "healthy",
        "provider": "groq",
        "detail": f"Groq API reachable — model: {settings.GROQ_MODEL}",
    }


def _health_openai() -> dict:
    try:
        from openai import OpenAI
    except ImportError:
        return {
            "status": "unhealthy",
            "provider": "openai",
            "detail": "openai package not installed",
        }

    if not settings.OPENAI_API_KEY:
        return {
            "status": "unhealthy",
            "provider": "openai",
            "detail": "OPENAI_API_KEY not set",
        }

    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=1,
    )
    return {
        "status": "healthy",
        "provider": "openai",
        "detail": f"OpenAI API reachable — model: {settings.OPENAI_MODEL}",
    }


def _health_gemini() -> dict:
    try:
        import google.generativeai as genai
    except ImportError:
        return {
            "status": "unhealthy",
            "provider": "gemini",
            "detail": "google-generativeai package not installed",
        }

    if not settings.GEMINI_API_KEY:
        return {
            "status": "unhealthy",
            "provider": "gemini",
            "detail": "GEMINI_API_KEY not set",
        }

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)
    model.generate_content("ping")
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
                "detail": f"Ollama reachable at {settings.OLLAMA_BASE_URL} — model: {settings.OLLAMA_MODEL}",
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
