"""
Personalization Agent — generates tailored search queries from user profile + prompt.

Public API::

    from app.agents.personalization import personalization_node

    graph.add_node("personalization", personalization_node)
"""

from app.agents.personalization.agent import (
    build_personalization_graph,
    personalization_node,
)

__all__ = [
    "personalization_node",
    "build_personalization_graph",
]
