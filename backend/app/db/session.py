"""
SQLAlchemy engine and session configuration.
Designed for Supabase (PostgreSQL) with connection pool hardening.
"""

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_connect_args: dict = {}

if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args=_connect_args,
        echo=settings.DEBUG,  # Log SQL only in DEBUG mode
    )
else:
    sslmode = (
        "prefer"
        if "localhost" in settings.DATABASE_URL or "127.0.0.1" in settings.DATABASE_URL
        else "require"
    )
    _connect_args = {
        "sslmode": sslmode,
        "connect_timeout": settings.DB_CONNECT_TIMEOUT,
    }
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_recycle=settings.DB_POOL_RECYCLE,
        pool_pre_ping=settings.DB_POOL_PRE_PING,
        connect_args=_connect_args,
        echo=settings.DEBUG,  # Log SQL only in DEBUG mode
    )


@event.listens_for(engine, "connect")
def _set_search_path(dbapi_connection, _connection_record) -> None:
    """Ensure the public schema is always in the search path (PostgreSQL only)."""
    if not settings.DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO public")
        cursor.close()


# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # Avoid lazy-load errors after commit
)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db() -> Session:
    """
    FastAPI dependency that provides a scoped database session.
    Rolls back on exception and always closes the session.

    Usage:
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def verify_db_connection() -> bool:
    """
    Confirm the database is reachable.
    Used by the /health endpoint and startup checks.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection verified.")
        return True
    except Exception as exc:
        logger.error(f"Database connection check failed: {exc}")
        return False
