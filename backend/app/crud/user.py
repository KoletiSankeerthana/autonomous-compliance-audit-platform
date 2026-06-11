"""User CRUD operations."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.user import User, UserRole


class CRUDUser(CRUDBase[User]):
    """User-specific database operations."""

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """Look up a user by email address (case-sensitive)."""
        return db.query(User).filter(User.email == email).first()

    def create_user(
        self,
        db: Session,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.AUDITOR,
    ) -> User:
        """Create and persist a new user."""
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role,
            is_active=True,
        )
        return self.create(db, obj=user)

    def update_last_login(self, db: Session, user: User) -> User:
        """Record the current UTC timestamp as the user's last login."""
        try:
            user.last_login_at = datetime.now(tz=timezone.utc)
            db.commit()
            db.refresh(user)
            return user
        except Exception:
            db.rollback()
            raise

    def update_role(self, db: Session, user: User, new_role: UserRole) -> User:
        """Change a user's role."""
        try:
            user.role = new_role
            db.commit()
            db.refresh(user)
            return user
        except Exception:
            db.rollback()
            raise

    def set_active(self, db: Session, user: User, *, active: bool) -> User:
        """Activate or deactivate a user account."""
        try:
            user.is_active = active
            db.commit()
            db.refresh(user)
            return user
        except Exception:
            db.rollback()
            raise

    def update_password(self, db: Session, user: User, hashed_password: str) -> User:
        """Update a user's hashed password."""
        try:
            user.hashed_password = hashed_password
            db.commit()
            db.refresh(user)
            return user
        except Exception:
            db.rollback()
            raise

    def list_all(self, db: Session, *, skip: int = 0, limit: int = 50) -> list[User]:
        """Return all users ordered by creation date descending."""
        return (
            db.query(User)
            .order_by(User.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


crud_user = CRUDUser(User)
