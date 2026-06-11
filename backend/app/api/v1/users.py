"""
User management router (admin only).
GET    /api/v1/users          — list all users
GET    /api/v1/users/{id}     — get user by ID
PATCH  /api/v1/users/{id}     — update role or active status
DELETE /api/v1/users/{id}     — deactivate (soft delete)
POST   /api/v1/users/{id}/reset-password — admin password reset
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_admin
from app.core.logging import get_logger
from app.core.security import hash_password
from app.crud.user import crud_user
from app.db.session import get_db
from app.models.user import User, UserRole
from app.schemas.user import (
    ChangePasswordRequest,
    UserListResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/users", tags=["User Management"])
logger = get_logger(__name__)


@router.get(
    "",
    response_model=UserListResponse,
    summary="List all users (admin only)",
)
def list_users(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin),
):
    users = crud_user.list_all(db, skip=skip, limit=limit)
    total = crud_user.count(db)
    return UserListResponse(total=total, users=users)


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user by ID (admin only)",
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin),
):
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )
    return user


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Update user role or status (admin only)",
)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin),
):
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )

    if payload.role is not None:
        try:
            new_role = UserRole(payload.role)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid role: {payload.role}",
            )
        crud_user.update_role(db, user, new_role)
        logger.info(
            f"Role updated: user_id={user_id} "
            f"new_role={new_role.value} by admin_id={admin.id}"
        )

    if payload.is_active is not None:
        crud_user.set_active(db, user, active=payload.is_active)
        logger.info(
            f"Account {'activated' if payload.is_active else 'deactivated'}: "
            f"user_id={user_id} by admin_id={admin.id}"
        )

    if payload.full_name is not None:
        try:
            user.full_name = payload.full_name
            db.commit()
            db.refresh(user)
        except Exception:
            db.rollback()
            raise

    return user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate a user account (admin only)",
)
def deactivate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin),
):
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )

    if user.id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrators cannot deactivate their own account.",
        )

    crud_user.set_active(db, user, active=False)
    logger.info(f"User deactivated: user_id={user_id} by admin_id={admin.id}")


@router.post(
    "/{user_id}/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reset a user's password (admin only)",
)
def reset_password(
    user_id: int,
    payload: ChangePasswordRequest,
    db: Session = Depends(get_db),
    _admin: User = Depends(get_admin),
):
    user = crud_user.get(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found.",
        )

    crud_user.update_password(db, user, hash_password(payload.new_password))
    logger.info(f"Password reset: user_id={user_id}")
