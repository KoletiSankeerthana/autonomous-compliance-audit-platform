"""User response schemas — never expose hashed_password."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, field_validator


class UserResponse(BaseModel):
    """Safe user representation returned to API clients."""
    id: int
    email: EmailStr
    full_name: str
    role: str
    is_active: bool
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class UserUpdateRequest(BaseModel):
    """Admin-only payload to update a user's role or active status."""
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    """User's own password change request."""
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def validate_new_password_length(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 bytes.")
        return v


class UserListResponse(BaseModel):
    """Paginated user list."""
    total: int
    users: list[UserResponse]
