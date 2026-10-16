"""
Research Agent — autonomous web research for Cupid.

Public API::

    # As a LangGraph node (direct usage)
    from app.agents.legacy.research import research_node

    graph.add_node("research", research_node)

    # As a compiled subgraph (swarm orchestration)
    from app.agents.legacy.research import build_research_graph

    research = build_research_graph().compile()
    orchestrator.add_node("research", research)

    # Standalone search pipeline (testing / other agents)
    from app.agents.legacy.research.search import SearchPipeline

    results = await SearchPipeline().run(["query1", "query2"])
"""

from app.agents.legacy.research.agent import build_research_graph, research_node
from app.agents.legacy.research.search import SearchPipeline, SearchResult

__all__ = [
    "research_node",
    "build_research_graph",
    "SearchPipeline",
    "SearchResult",
]
