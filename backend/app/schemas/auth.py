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
from pydantic import BaseModel, EmailStr, Field

# REQUEST SCHEMAS
# ── Registration ───────────────────────────────────────────
class UserCreate(BaseModel):
    """Schema for user registration request."""
    full_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, max_length=128)
    
# ── Login ──────────────────────────────────────────────────
class LoginRequest(BaseModel):
    """Schema for login request (obtaining JWT)."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")

class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    email: EmailStr
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}
    #  from_attributes=True lets Pydantic read from SQLAlchemy model
    #  attributes directly (user.name instead of user["name"])
class AuthResponse(BaseModel):
    """Wraps user data in our standard API envelope."""
    success: bool = True
    data: UserResponse
    error: str | None = None
