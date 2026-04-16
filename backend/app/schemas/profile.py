"""
Schemas for user personalization (single source of truth).\n+Matches frontend `PersonalizationForm`.\n+"""

from pydantic import BaseModel, Field


class PersonalizationUpdate(BaseModel):
    """
    What the frontend sends when saving persona data.\n+    Mirrors `PersonalizationForm` in the Settings page.\n+    """

    name: str | None = Field(None, max_length=255)
    nickname: str | None = Field(None, max_length=255)
    bio: str | None = Field(None, max_length=4000)

    content_niche: str | None = Field(None, max_length=255)
    content_goal: str | None = Field(None, max_length=255)
    content_intent: str | None = Field(None, max_length=255)

    target_age_group: str | None = Field(None, max_length=255)
    target_country: str | None = Field(None, max_length=255)
    target_audience: str | None = Field(None, max_length=255)

    usp: str | None = Field(None, max_length=4000)


class PersonalizationResponse(BaseModel):
    """What the server returns."""

    name: str
    nickname: str | None = None
    bio: str | None = None

    content_niche: str | None = None
    content_goal: str | None = None
    content_intent: str | None = None

    target_age_group: str | None = None
    target_country: str | None = None
    target_audience: str | None = None

    usp: str | None = None

    model_config = {"from_attributes": True}


class PersonalizationApiResponse(BaseModel):
    success: bool = True
    data: PersonalizationResponse | None = None
    error: str | None = None
