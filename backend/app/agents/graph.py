"""
LangGraph Agent Orchestrator — Cupid's multi-agent pipeline.

Current flow (V1):
    User Input → Personalization Agent → Research Agent → Output

Future versions will add:
    User Input → Personalization → Research → Composer → Output

The graph is stateless - all state lives in MemoryState and PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from langgraph.graph import StateGraph, END

from app.agents.state import MemoryState
from app.agents.research import research_node
from app.agents.personalization import personalization_node
from app.agents.composer import composer_node

class AgentsOrchestrator:
    """
    Orchestrates the Cupid agents pipeline using LangGraph.
    Current flow (V1):
        START → personalization → research → END
    """

    def __init__(self):
        self.graph = self._build_graph()
        self.compiled_graph = self.graph.compile()

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph StateGraph.

        The graph defines:
        - Nodes (agents)
        - Edges (flow between agents)
        - Conditional routing (future)
        """
        # Create graph with MemoryState
        workflow = StateGraph(MemoryState)

        # Add agent nodes
        workflow.add_node("personalization", personalization_node)
        workflow.add_node("research", research_node)
        workflow.add_node("composer", composer_node)

        # Define flow
        workflow.set_entry_point("personalization")
        workflow.add_edge("personalization", "research")
        workflow.add_edge("research", "composer")
        workflow.add_edge("composer", END)

        return workflow

    async def run(
        self,
        user_id: str,
        user_prompt: str,
        run_id: str | None = None,
        content_type: str = "Text",
        target_platform: str = "All",
        content_length: str = "Medium",
        tone: str = "Casual",
        personalization: dict | None = None,
    ) -> MemoryState:
        """
        Execute the agent pipeline.

        Args:
            user_id: User ID from database
            user_prompt: User's input text
            run_id: Optional run ID. If omitted, a UUID is generated.
            content_type: Type of content to generate
            target_platform: Target social media platform
            content_length: Desired content length
            tone: Content tone
            personalization: User personalization data (from Settings form)

        Returns:
            Final MemoryState after all agents complete
        """
        run_id_final = run_id or str(uuid.uuid4())
        # Initialize state
        initial_state: dict[str, Any] = {
            "run_id": run_id_final,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc),
            "user_prompt": user_prompt,
            "content_type": content_type,
            "target_platform": target_platform,
            "content_length": content_length,
            "tone": tone,
            "personalization": personalization or {},
            "personalization_queries": [],
            "agents_completed": [],
            "status": "running",
            "error": None,
        }

        # Execute graph
        final_state = await self.compiled_graph.ainvoke(initial_state)
        # Mark as completed
        final_state["status"] = "completed"
        return final_state  # type: ignore


# Singleton instance
_orchestrator: AgentsOrchestrator | None = None


def get_orchestrator() -> AgentsOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentsOrchestrator()
    return _orchestrator
