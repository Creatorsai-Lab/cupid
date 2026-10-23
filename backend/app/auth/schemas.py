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


class UserResponse(BaseModel):
    id: uuid.UUID
    full_name: str
    # One or both is set: Google accounts have an email, phone accounts a phone.
    email: EmailStr | None
    phone: str | None
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Wraps user data in our standard API envelope."""

    success: bool = True
    data: UserResponse
    error: str | None = None


class LoginEventResponse(BaseModel):
    id: uuid.UUID
    method: str
    ip_address: str
    user_agent: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


class LoginHistoryResponse(BaseModel):
    success: bool = True
    data: list[LoginEventResponse]
    error: str | None = None


# ── Phone OTP login ───────────────────────────────────────────


class OtpSendRequest(BaseModel):
    # Any common format ("+91 99999-99999", "9999999999"); normalized server-side.
    phone: str = Field(min_length=10, max_length=20)


class OtpSendData(BaseModel):
    expires_in: int
    resend_in: int


class OtpSendResponse(BaseModel):
    success: bool = True
    data: OtpSendData
    error: str | None = None


class OtpVerifyRequest(BaseModel):
    phone: str = Field(min_length=10, max_length=20)
    code: str = Field(pattern=r"^\d{6}$")


class OtpVerifyResponse(AuthResponse):
    # Frontend route to go to next: /settings for a new account, else /create.
    next: str
