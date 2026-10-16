"""Studio output: content as typed, addressable blocks (plan D10).

The editor will target single blocks ("shorten paragraph 2", "regenerate the
image on slide 3"), so content is never stored as one plain string.
"""

from typing import Literal

from pydantic import Field

from app.agents.models import ContractModel


class TextBlock(ContractModel):
    kind: Literal["text"] = "text"
    role: str | None = None  # "hook", "body", "cta", "hashtags", …
    text: str = Field(min_length=1)


# Grows into a discriminated union as specialists arrive:
# Annotated[TextBlock | ImageBlock | SlideBlock | SceneBlock, Field(discriminator="kind")]
Block = TextBlock


class ContentPiece(ContractModel):
    id: str
    deliverable: str  # "linkedin_post", "x_thread", "carousel", …
    variant: int = Field(ge=1)
    blocks: tuple[Block, ...] = Field(min_length=1)
    source_ids: tuple[str, ...] = ()
    status: Literal["ready", "degraded", "failed"] = "ready"
