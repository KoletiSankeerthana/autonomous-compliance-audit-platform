"""
User ORM model.
Supports three roles: admin, auditor, compliance_officer.
Passwords are stored as bcrypt hashes — never plaintext.
"""

import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.sql import func

from app.models.base import Base


class UserRole(str, enum.Enum):
    """
    Role hierarchy:
    - admin: full platform access, user management
    - auditor: create and view audit reports
    - compliance_officer: view reports and analytics, read-only
    """
    ADMIN = "admin"
    AUDITOR = "auditor"
    COMPLIANCE_OFFICER = "compliance_officer"


class User(Base):
    """Platform user with role-based access control."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    full_name = Column(String(150), nullable=False)

    hashed_password = Column(String(255), nullable=False)

    role = Column(
        Enum(UserRole, name="user_role", create_constraint=True),
        nullable=False,
        default=UserRole.AUDITOR,
        index=True,
    )

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    last_login_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role.value}>"
