"""
Composer Agent — generates 3 platform-ready post variants from research data.

Public API::

    # LangGraph node (direct usage)
    from app.agents.composer import composer_node
    graph.add_node("composer", composer_node)

    # Compiled subgraph (swarm orchestration)
    from app.agents.composer import build_composer_graph
    composer = build_composer_graph().compile()
"""
from app.agents.composer.agent import build_composer_graph, composer_node

__all__ = [
    "composer_node",
    "build_composer_graph",
]