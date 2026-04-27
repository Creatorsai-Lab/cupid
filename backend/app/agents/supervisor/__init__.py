"""
Supervisor Agent — Input validation and content moderation.

Validates user prompts before passing to the agent pipeline.
"""
from app.agents.supervisor.agent import supervisor_node

__all__ = ["supervisor_node"]
