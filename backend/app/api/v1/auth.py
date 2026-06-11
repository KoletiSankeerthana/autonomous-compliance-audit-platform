"""
Authentication router.
POST /api/v1/auth/register  — admin creates a new user
POST /api/v1/auth/login     — returns JWT access + refresh tokens
POST /api/v1/auth/refresh   — exchange refresh token for new access token
GET  /api/v1/auth/me        — returns the authenticated user profile
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.dependencies import get_admin, get_current_user
from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.crud.user import crud_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["Authentication"])
logger = get_logger(__name__)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
):
    """
    Create a new platform user.
    """
    existing = crud_user.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with email '{payload.email}' already exists.",
        )

    role = UserRole(payload.role)
    user = crud_user.create_user(
        db,
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=role,
    )
    logger.info(f"User created: id={user.id} email={user.email} role={role.value}")
    return user


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and obtain JWT tokens",
)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Validate credentials and return an access token and refresh token.
    The access token expires in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes.
    """
    user = crud_user.get_by_email(db, payload.email)
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    crud_user.update_last_login(db, user)

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "role": user.role.value},
    )
    refresh_token = create_refresh_token(subject=str(user.id))

    logger.info(f"User authenticated: id={user.id} email={user.email}")

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
)
def refresh_token(payload: RefreshRequest, db: Session = Depends(get_db)):
    """Exchange a valid refresh token for a new access token."""
    try:
        token_data = decode_refresh_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )

    user_id = token_data.get("sub")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive.",
        )

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "role": user.role.value},
    )
    new_refresh = create_refresh_token(subject=str(user.id))

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def me(current_user: User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return current_user
