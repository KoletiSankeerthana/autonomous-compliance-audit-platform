"""
Core application configuration.
All settings are loaded from environment variables via Pydantic Settings.
Never hard-code values here — use .env or system environment.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Centralised application configuration.
    Values are read from environment variables (case-insensitive).
    Override any value by setting the corresponding env var.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------------------------------------------------------------
    # Application
    # -----------------------------------------------------------------------
    APP_NAME: str = "Enterprise Compliance AI Platform"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # -----------------------------------------------------------------------
    # API
    # -----------------------------------------------------------------------
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000,http://localhost:8080,https://autonomous-compliance-audit-platfor.vercel.app"

    # -----------------------------------------------------------------------
    # Database (Supabase PostgreSQL)
    # -----------------------------------------------------------------------
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")

    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_RECYCLE: int = 300   # seconds
    DB_POOL_PRE_PING: bool = True
    DB_CONNECT_TIMEOUT: int = 10

    # -----------------------------------------------------------------------
    # Authentication
    # -----------------------------------------------------------------------
    SECRET_KEY: str = Field(
        ...,
        description="HS256 signing key — generate with: openssl rand -hex 32"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480    # 8 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    BCRYPT_ROUNDS: int = 12

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v) -> str:
        """Accept both a comma-separated string and a list for ALLOWED_ORIGINS."""
        if isinstance(v, list):
            return ",".join(v)
        return str(v)

    @property
    def allowed_origins_list(self) -> list[str]:
        """Return ALLOWED_ORIGINS as a Python list for middleware configuration."""
        import os
        # Fallback support for other common CORS environment variables
        origins_str = os.getenv("ALLOWED_ORIGINS") or os.getenv("BACKEND_CORS_ORIGINS") or os.getenv("CORS_ORIGINS") or self.ALLOWED_ORIGINS
        
        origins_list = []
        # If it's a JSON array format: e.g., ["origin1", "origin2"]
        if isinstance(origins_str, str) and origins_str.strip().startswith("[") and origins_str.strip().endswith("]"):
            import json
            try:
                origins = json.loads(origins_str)
                if isinstance(origins, list):
                    origins_list = [str(o).strip() for o in origins if o]
            except Exception:
                pass
        
        if not origins_list:
            if isinstance(origins_str, list):
                origins_list = [str(o).strip() for o in origins_str if o]
            else:
                origins_list = [o.strip() for o in str(origins_str).split(",") if o.strip()]
                
        # Ensure the production Vercel frontend origin is always included
        prod_origin = "https://autonomous-compliance-audit-platfor.vercel.app"
        if prod_origin not in origins_list:
            origins_list.append(prod_origin)
            
        return origins_list

    # -----------------------------------------------------------------------
    # LLM Provider (Groq / OpenAI / Gemini / Ollama)
    # Set LLM_PROVIDER to: groq | openai | gemini | ollama
    # ollama = local development only (requires Ollama running at localhost)
    # -----------------------------------------------------------------------
    LLM_PROVIDER: str = "ollama"   # Override with LLM_PROVIDER=groq in production

    # Groq (recommended for production — free tier at console.groq.com)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama3-8b-8192"

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # Ollama (local development only — keep for backwards compatibility)
    OLLAMA_MODEL: str = "llama3"
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # -----------------------------------------------------------------------
    # ChromaDB
    # -----------------------------------------------------------------------
    CHROMA_DB_PATH: str = "./chroma_db"
    CHROMA_COLLECTION_NAME: str = "documents"
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8000

    # -----------------------------------------------------------------------
    # File Storage
    # -----------------------------------------------------------------------
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: list[str] = [".pdf"]

    # -----------------------------------------------------------------------
    # Logging
    # -----------------------------------------------------------------------
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "text"

    # -----------------------------------------------------------------------
    # MCP Integrations
    # -----------------------------------------------------------------------
    MCP_LOCAL_FILES_DIR: str = "./mcp_documents"

    GOOGLE_DRIVE_ENABLED: bool = True
    GOOGLE_SERVICE_ACCOUNT_FILE: str = ""
    GOOGLE_DRIVE_FOLDER_ID: str = ""
    # Legacy alias — kept for backwards compat
    GOOGLE_DRIVE_CREDENTIALS_JSON: str = ""

    NOTION_API_TOKEN: str = ""
    NOTION_DATABASE_ID: str = ""

    # -----------------------------------------------------------------------
    # Admin Bootstrap
    # -----------------------------------------------------------------------
    ADMIN_EMAIL: str = "admin@company.com"
    ADMIN_PASSWORD: str = Field(
        "ChangeMe123!",
        description="Default admin password — must be changed on first login"
    )

    # -----------------------------------------------------------------------
    # Workflow
    # -----------------------------------------------------------------------
    # Maximum seconds the full AI workflow is allowed to run before aborting.
    # Covers all agent LLM calls in aggregate. Default 300s = 5 minutes.
    WORKFLOW_TIMEOUT_SECONDS: int = 300

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL must be set in .env")
        # Handle SQLAlchemy 2.0+ psycopg 3 driver format
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or v in ("changeme", "secret", "your-secret-key"):
            raise ValueError(
                "SECRET_KEY must be a strong random value. "
                "Generate one: openssl rand -hex 32"
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return the cached singleton Settings instance.
    Use as a FastAPI dependency: Depends(get_settings)
    """
    return Settings()


# Module-level convenience reference
settings = get_settings()
