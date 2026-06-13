"""
Enterprise Compliance & Audit Intelligence Platform
FastAPI application entry point.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

import os

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.db.session import engine, verify_db_connection
from app.models.base import Base
from app.models.user import User, UserRole

# Ensure all models are imported so Base.metadata is populated
import app.models.audit_report  # noqa: F401
import app.models.compliance_violation  # noqa: F401

configure_logging()
logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Autonomous Enterprise Compliance & Audit Intelligence Platform. "
        "Provides AI-powered document analysis, compliance gap assessment, "
        "risk classification, and structured audit reporting."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

def _get_cors_headers(request: Request) -> dict:
    headers = {}
    origin = request.headers.get("origin")
    if origin:
        # Fallback check for allowed origins list
        if origin in settings.allowed_origins_list:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
            headers["Access-Control-Allow-Methods"] = "*"
            headers["Access-Control-Allow-Headers"] = "*"
        elif "*" in settings.allowed_origins_list:
            headers["Access-Control-Allow-Origin"] = "*"
            headers["Access-Control-Allow-Methods"] = "*"
            headers["Access-Control-Allow-Headers"] = "*"
    return headers


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    logger.error(
        f"HTTP exception: status={exc.status_code} detail={exc.detail} | "
        f"path={request.url.path} method={request.method}"
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
        },
        headers=_get_cors_headers(request),
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Unhandled exception: {exc} | "
        f"path={request.url.path} method={request.method}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "An unexpected error occurred.",
            "detail": str(exc) if settings.ENVIRONMENT == "development" else "Internal server error.",
        },
        headers=_get_cors_headers(request),
    )

# ---------------------------------------------------------------------------
# Startup / shutdown lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
def on_startup():
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"CORS Allowed Origins: {settings.allowed_origins_list}")

    # Verify environment variables
    db_url = settings.DATABASE_URL
    sanitized_db_url = db_url
    if db_url and "@" in db_url:
        try:
            prefix, rest = db_url.split("@", 1)
            subprefix, auth = prefix.rsplit("//", 1)
            if ":" in auth:
                username, _ = auth.split(":", 1)
                sanitized_db_url = f"{subprefix}//{username}:***@{rest}"
            else:
                sanitized_db_url = f"{subprefix}//***@{rest}"
        except Exception:
            sanitized_db_url = "postgresql+psycopg://***@***"
    
    logger.info(f"Effective DATABASE_URL: {sanitized_db_url}")
    logger.info(f"Effective LLM_PROVIDER: {settings.LLM_PROVIDER}")
    logger.info(f"Effective GROQ_MODEL: {settings.GROQ_MODEL}")
    logger.info(f"Effective CHROMA_HOST: {settings.CHROMA_HOST}")
    logger.info(f"Effective CHROMA_PORT: {settings.CHROMA_PORT}")

    # Log LLM provider configuration
    provider = settings.LLM_PROVIDER.lower().strip()
    if provider == "groq":
        key_set = bool(settings.GROQ_API_KEY)
        logger.info(f"LLM Provider: Groq | Model: {settings.GROQ_MODEL} | API key set: {key_set}")
        if not key_set:
            logger.warning("GROQ_API_KEY is not set — LLM calls will fail in production. Set it in Render env vars.")
    elif provider == "openai":
        key_set = bool(settings.OPENAI_API_KEY)
        logger.info(f"LLM Provider: OpenAI | Model: {settings.OPENAI_MODEL} | API key set: {key_set}")
    elif provider == "gemini":
        key_set = bool(settings.GEMINI_API_KEY)
        logger.info(f"LLM Provider: Gemini | Model: {settings.GEMINI_MODEL} | API key set: {key_set}")
    else:
        logger.info(f"LLM Provider: Ollama (local dev) | URL: {settings.OLLAMA_BASE_URL} | Model: {settings.OLLAMA_MODEL}")
        if "localhost" in settings.OLLAMA_BASE_URL or "127.0.0.1" in settings.OLLAMA_BASE_URL:
            logger.warning(
                "LLM_PROVIDER=ollama with localhost URL — this will fail in production on Render. "
                "Set LLM_PROVIDER=groq and GROQ_API_KEY in Render environment variables."
            )

    # Create database tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified / created.")

    # Auto-migrate schema changes
    _auto_migrate_schema()

    # Verify database connectivity
    if not verify_db_connection():
        logger.error("Database connection failed on startup. Check DATABASE_URL.")
    else:
        logger.info("Database connection verified.")

    # Log Google Drive MCP config status on startup
    import os
    gdrive_enabled = os.environ.get("GOOGLE_DRIVE_ENABLED", "").strip().lower() in ("1", "true", "yes") or settings.GOOGLE_DRIVE_ENABLED
    env_enabled = os.environ.get("GOOGLE_DRIVE_ENABLED", "").strip().lower()
    if env_enabled in ("0", "false", "no"):
        gdrive_enabled = False
        
    gdrive_email = os.environ.get("GOOGLE_CLIENT_EMAIL", "").strip() or getattr(settings, "GOOGLE_CLIENT_EMAIL", "").strip()
    gdrive_pkey = os.environ.get("GOOGLE_PRIVATE_KEY", "").strip() or getattr(settings, "GOOGLE_PRIVATE_KEY", "").strip()
    gdrive_folder = os.environ.get("GOOGLE_DRIVE_FOLDER_ID", "").strip() or settings.GOOGLE_DRIVE_FOLDER_ID
    gdrive_file = os.environ.get("GOOGLE_SERVICE_ACCOUNT_FILE", "").strip() or settings.GOOGLE_SERVICE_ACCOUNT_FILE
    
    logger.info("----- Google Drive MCP Config Status -----")
    logger.info(f"GOOGLE_DRIVE_ENABLED loaded: {gdrive_enabled}")
    logger.info(f"GOOGLE_CLIENT_EMAIL loaded: {bool(gdrive_email)} (value: {gdrive_email or 'None'})")
    logger.info(f"GOOGLE_PRIVATE_KEY loaded: {bool(gdrive_pkey)}")
    logger.info(f"GOOGLE_DRIVE_FOLDER_ID loaded: {bool(gdrive_folder)} (value: {gdrive_folder or 'None'})")
    logger.info(f"GOOGLE_SERVICE_ACCOUNT_FILE loaded: {bool(gdrive_file)} (value: {gdrive_file or 'None'})")
    if gdrive_file:
        logger.info(f"GOOGLE_SERVICE_ACCOUNT_FILE exists on disk: {os.path.exists(gdrive_file)}")
    logger.info("------------------------------------------")

    # Bootstrap default admin user if no users exist
    _bootstrap_admin()

    # Ensure upload directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    logger.info(f"Upload directory: {settings.UPLOAD_DIR}")


def _auto_migrate_schema():
    """Ensure missing columns like created_by_user_id are automatically added."""
    from sqlalchemy import text, inspect
    try:
        with engine.connect() as conn:
            if "sqlite" in engine.url.drivername:
                inspector = inspect(engine)
                columns = [c["name"] for c in inspector.get_columns("audit_reports")]
                has_column = "created_by_user_id" in columns
            else:
                result = conn.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'audit_reports' AND column_name = 'created_by_user_id'
                """)).fetchone()
                has_column = result is not None
            
            if not has_column:
                logger.info("Column created_by_user_id is missing from audit_reports. Adding column...")
                conn.execute(text("""
                    ALTER TABLE audit_reports 
                    ADD COLUMN created_by_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL
                """))
                conn.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_audit_reports_user 
                    ON audit_reports (created_by_user_id)
                """))
                conn.commit()
                logger.info("Column created_by_user_id added successfully.")

        # Backfill existing audits into compliance_violations if empty
        from app.db.session import SessionLocal
        from app.models.audit_report import AuditReport
        from app.models.compliance_violation import ComplianceViolation
        import json
        from datetime import datetime
        
        db = SessionLocal()
        try:
            violation_count = db.query(ComplianceViolation).count()
            if violation_count == 0:
                reports = db.query(AuditReport).all()
                if reports:
                    logger.info(f"Backfilling structured compliance_violations for {len(reports)} existing reports...")
                    for r in reports:
                        try:
                            # Parse audit timestamp to datetime
                            try:
                                report_dt = datetime.strptime(r.audit_timestamp, "%Y-%m-%d %H:%M:%S")
                            except Exception:
                                report_dt = r.created_at or datetime.now()

                            # Deserialise issues
                            issues = []
                            if r.issues:
                                try:
                                    issues = json.loads(r.issues)
                                except Exception:
                                    issues = [r.issues]
                                    
                            for issue in issues:
                                issue_lower = issue.lower()
                                
                                severity = "Medium"
                                if any(kw in issue_lower for kw in ["critical", "mfa", "encryption", "credentials"]):
                                    severity = "Critical"
                                elif any(kw in issue_lower for kw in ["high", "password", "access", "unauthorized"]):
                                    severity = "High"
                                elif any(kw in issue_lower for kw in ["low", "minor", "version", "formatting"]):
                                    severity = "Low"
                                    
                                v_type = "Other"
                                if any(kw in issue_lower for kw in ["mfa", "auth", "login", "password", "privilege"]):
                                    v_type = "Access Control"
                                elif any(kw in issue_lower for kw in ["encrypt", "aes", "ssl", "tls", "rest", "transit"]):
                                    v_type = "Data Encryption"
                                elif any(kw in issue_lower for kw in ["audit", "log", "history", "record"]):
                                    v_type = "Audit Logging"
                                elif any(kw in issue_lower for kw in ["privacy", "gdpr", "personal", "pii"]):
                                    v_type = "Data Privacy"
                                    
                                dept = "General"
                                if any(kw in issue_lower for kw in ["it", "system", "administrator", "network"]):
                                    dept = "IT"
                                elif any(kw in issue_lower for kw in ["finance", "billing", "payment"]):
                                    dept = "Finance"
                                elif any(kw in issue_lower for kw in ["hr", "employee", "staff"]):
                                    dept = "HR"

                                db.add(
                                    ComplianceViolation(
                                        report_id=r.id,
                                        violation_type=v_type,
                                        severity=severity,
                                        department=dept,
                                        compliance_score=r.compliance_score,
                                        regulation_category="Compliance Standards",
                                        report_date=report_dt,
                                        description=issue,
                                    )
                                )
                        except Exception as e:
                            logger.error(f"Failed to backfill report {r.id}: {e}")
                    db.commit()
                    logger.info("Database backfill completed successfully.")
        except Exception as e:
            logger.error(f"Schema backfill check failed: {e}")
        finally:
            db.close()
    except Exception as exc:
        logger.error(f"Auto-migration of schema failed: {exc}", exc_info=True)


@app.on_event("shutdown")
def on_shutdown():
    logger.info(f"{settings.APP_NAME} shutting down.")


def _bootstrap_admin():
    """Create a default admin user on application startup if no admin exists."""
    from sqlalchemy.orm import Session
    from app.db.session import SessionLocal
    from app.core.security import hash_password

    db: Session = SessionLocal()
    try:
        admin_exists = db.query(User).filter(User.role == UserRole.ADMIN).first()
        if not admin_exists:
            existing_user = db.query(User).filter(User.email == "admin@company.com").first()
            if existing_user:
                existing_user.role = UserRole.ADMIN
                existing_user.full_name = "System Administrator"
                existing_user.hashed_password = hash_password("Admin123!")
                existing_user.is_active = True
            else:
                admin = User(
                    email="admin@company.com",
                    full_name="System Administrator",
                    hashed_password=hash_password("Admin123!"),
                    role=UserRole.ADMIN,
                    is_active=True,
                )
                db.add(admin)
            db.commit()
            logger.info("Default admin account created")
        else:
            logger.info("Admin account already exists")
    except Exception as exc:
        logger.error(f"Admin bootstrap failed: {exc}")
        db.rollback()
    finally:
        db.close()

# ---------------------------------------------------------------------------
# Versioned API routes
# ---------------------------------------------------------------------------

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# ---------------------------------------------------------------------------
# Root and health endpoints (unversioned, no auth required)
# ---------------------------------------------------------------------------

@app.get("/", tags=["System"])
@app.head("/", tags=["System"])
def root():
    return {
        "platform": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "operational",
        "docs": "/docs",
        "api": settings.API_V1_PREFIX,
    }


@app.get("/health", tags=["System"])
def health():
    """
    Health check endpoint.
    Returns 200 if the application is running and the database is reachable.
    """
    db_ok = verify_db_connection()
    return JSONResponse(
        status_code=status.HTTP_200_OK if db_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "healthy" if db_ok else "degraded",
            "database": "connected" if db_ok else "unreachable",
            "version": settings.APP_VERSION,
        },
    )
