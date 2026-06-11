"""
FastAPI dependency injection providers.
Import these in route handlers via Depends().

Usage:
    @router.get("/protected")
    def protected(current_user: User = Depends(get_current_user)):
        ...

    @router.delete("/admin-only")
    def admin_only(_: User = Depends(require_role(["admin"]))):
        ...
"""

from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User, UserRole

logger = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Extract and validate the Bearer JWT from the Authorization header.
    Returns the authenticated User ORM object.
    Raises HTTP 401 if the token is missing, invalid, or the user does not exist.
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        logger.warning(f"Token validation failed: {exc}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject (sub) is missing.",
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with this token no longer exists.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated.",
        )

    return user


def require_role(allowed_roles: list[str]) -> Callable:
    """
    Factory that returns a dependency enforcing role-based access control.

    Args:
        allowed_roles: List of role names that may access the endpoint.
                       Example: ["admin"], ["admin", "auditor"]

    Returns:
        A FastAPI dependency function that raises HTTP 403 when the user's
        role is not in the allowed list.
    """
    def _check_role(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role.value not in allowed_roles:
            logger.warning(
                f"Access denied: user_id={current_user.id} "
                f"role={current_user.role.value} "
                f"required_roles={allowed_roles}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Insufficient permissions. "
                    f"Required role(s): {', '.join(allowed_roles)}."
                ),
            )
        return current_user

    return _check_role


def get_admin(current_user: User = Depends(get_current_user)) -> User:
    """Shorthand dependency that enforces the admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required.",
        )
    return current_user
