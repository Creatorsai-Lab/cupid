"""
LangGraph Agent Orchestrator — Cupid's multi-agent pipeline.

Current flow:
    User Input → Supervisor Agent → Personalization Agent → Research Agent → Composer Agent → Output

The supervisor agent validates input before passing to the pipeline.
The graph is stateless - all state lives in MemoryState and PostgreSQL.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import uuid

from langgraph.graph import StateGraph, END

from app.agents.state import MemoryState
from app.agents.supervisor import supervisor_node
from app.agents.research import research_node
from app.agents.personalization import personalization_node
from app.agents.composer import composer_node
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("orchestrator")

class AgentsOrchestrator:
    """
    Orchestrates the Cupid agents pipeline using LangGraph.
    Current flow:
        START → supervisor → personalization → research → composer → END
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
        - Conditional routing (supervisor can reject)
        """
        # Create graph with MemoryState
        workflow = StateGraph(MemoryState)

        # Add agent nodes
        workflow.add_node("supervisor", supervisor_node)
        workflow.add_node("personalization", personalization_node)
        workflow.add_node("research", research_node)
        workflow.add_node("composer", composer_node)

        # Define flow with conditional routing
        workflow.set_entry_point("supervisor")
        
        # Supervisor can either approve (continue) or reject (end)
        workflow.add_conditional_edges(
            "supervisor",
            lambda state: "approved" if not state.get("error") else "rejected",
            {
                "approved": "personalization",
                "rejected": END,
            }
        )
        
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
        target_platform: str = "Twitter",
        content_length: str = "Medium",
        tone: str = "Formal",
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
        
        logger.info("🎯 Orchestrator initializing pipeline", run_id_final)
        logger.info(f"  Graph nodes: {list(self.graph.nodes.keys())}", run_id_final)
        
        # Map tone to user_voice for composer
        tone_to_voice = {
            "Hook First": "hook_first",
            "Data Driven": "data_driven",
            "Story Led": "story_led",
        }
        user_voice = tone_to_voice.get(tone, "hook_first")
        
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
            "user_voice": user_voice,
            "personalization": personalization or {},
            "personalization_queries": [],
            "agents_completed": [],
            "status": "running",
            "error": None,
        }

        logger.info("🚀 Executing LangGraph pipeline", run_id_final)
        
        # Execute graph
        final_state = await self.compiled_graph.ainvoke(initial_state)
        
        # Check if supervisor rejected or if there's an error
        if final_state.get("error"):
            final_state["status"] = "failed"
            logger.warning(f"❌ Pipeline rejected: {final_state.get('error', '')[:100]}", run_id_final)
        else:
            # Mark as completed only if no errors
            final_state["status"] = "completed"
            logger.info("✅ LangGraph pipeline complete", run_id_final)
        
        return final_state  # type: ignore

    async def run_streaming(
        self,
        user_id: str,
        user_prompt: str,
        run_id: str | None = None,
        content_type: str = "Text",
        target_platform: str = "Twitter",
        content_length: str = "Medium",
        tone: str = "Formal",
        personalization: dict | None = None,
    ):
        """
        Execute the agent pipeline with streaming state updates.
        
        Yields intermediate state after each agent completes, allowing
        real-time progress updates to the frontend.
        
        Args:
            Same as run()
            
        Yields:
            MemoryState after each agent node completes
        """
        run_id_final = run_id or str(uuid.uuid4())
        
        logger.info("🎯 Orchestrator initializing streaming pipeline", run_id_final)
        
        # Map tone to user_voice for composer
        tone_to_voice = {
            "Hook First": "hook_first",
            "Data Driven": "data_driven",
            "Story Led": "story_led",
        }
        user_voice = tone_to_voice.get(tone, "hook_first")
        
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
            "user_voice": user_voice,
            "personalization": personalization or {},
            "personalization_queries": [],
            "agents_completed": [],
            "status": "running",
            "error": None,
        }

        logger.info("🚀 Executing streaming LangGraph pipeline", run_id_final)
        
        # Stream state updates from graph
        async for state_update in self.compiled_graph.astream(initial_state):
            # LangGraph astream yields dict with node name as key
            # e.g., {"supervisor": {...state...}}
            for node_name, node_state in state_update.items():
                logger.info(f"📡 Streaming update from node: {node_name}", run_id_final)
                yield node_state


# Singleton instance
_orchestrator: AgentsOrchestrator | None = None


def get_orchestrator() -> AgentsOrchestrator:
    """Get or create the global orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentsOrchestrator()
    return _orchestrator
