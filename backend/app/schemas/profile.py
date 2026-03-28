"""
Schemas for user profile (persona data).
"""

from pydantic import BaseModel, Field


class ProfileUpdate(BaseModel):
    """What the frontend sends when saving persona data."""
    bio: str | None = Field(None, max_length=2000)
    field: str | None = Field(None, max_length=255)
    skills: str | None = Field(None, max_length=1000)
    geography: str | None = Field(None, max_length=255)
    audience: str | None = Field(None, max_length=1000)


class ProfileResponse(BaseModel):
    """What the server returns."""
    bio: str | None = None
    field: str | None = None
    skills: str | None = None
    geography: str | None = None
    audience: str | None = None

    model_config = {"from_attributes": True}


class ProfileApiResponse(BaseModel):
    success: bool = True
    data: ProfileResponse | None = None
    error: str | None = None
