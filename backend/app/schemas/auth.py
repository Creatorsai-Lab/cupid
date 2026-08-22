"""
Request/response schemas for authentication endpoints.
Schemas are NOT database models. They define:
- What data the client must send (request schemas)
- What data the server returns (response schemas)
This separation means you never accidentally expose
sensitive fields (like hashed_password) in API responses.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Wraps user data in our standard API envelope."""

    success: bool = True
    data: UserResponse
    error: str | None = None
