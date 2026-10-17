"""The voice each tone writes in (decision D2): the one copy, read by the studio.

Moved here unchanged from the old /generate endpoint. Today three tones have a
voice of their own and the rest use DEFAULT_VOICE; Phase 5 maps every Tone to
a voice spec, with a test that fails when a tone has none.
"""

from app.agents.models import Tone

DEFAULT_VOICE = "hook_first"

TONE_TO_VOICE: dict[Tone, str] = {
    "Hook First": "hook_first",
    "Data Driven": "data_driven",
    "Story Led": "story_led",
}
