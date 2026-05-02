"""
Integration tests for streaming agent pipeline.

Run: pytest tests/integration/test_streaming_pipeline.py -v
"""
import pytest
from app.agents.graph import get_orchestrator


@pytest.mark.asyncio
class TestStreamingPipeline:
    """Test suite for streaming agent pipeline."""
    
    async def test_streaming_yields_updates(self):
        """Test that streaming yields intermediate state updates."""
        orchestrator = get_orchestrator()
        
        prompt = "AI trends in healthcare 2026"
        personalization = {
            "content_niche": "Healthcare Technology",
            "target_audience": "Healthcare professionals",
        }
        
        updates = []
        async for state in orchestrator.run_streaming(
            user_id="test-user",
            user_prompt=prompt,
            run_id="test-streaming-001",
            personalization=personalization,
        ):
            updates.append({
                "current_agent": state.get("current_agent"),
                "agents_completed": state.get("agents_completed", []),
                "queries_count": len(state.get("personalization_queries", [])),
                "has_error": state.get("error") is not None,
            })
        
        # Verify we got multiple updates (at least 3: supervisor, personalization, research)
        assert len(updates) >= 3, f"Expected at least 3 updates, got {len(updates)}"
        
        # Verify supervisor completed first
        assert "supervisor" in updates[0]["agents_completed"]
        
        # Verify personalization generated queries
        personalization_update = next(
            (u for u in updates if "personalization" in u["agents_completed"]),
            None
        )
        assert personalization_update is not None
        assert personalization_update["queries_count"] > 0, "Personalization should generate queries"
        
        # Verify agents completed in order
        final_update = updates[-1]
        expected_order = ["supervisor", "personalization", "research", "composer"]
        for agent in expected_order:
            if agent in final_update["agents_completed"]:
                # Verify order is maintained
                completed = final_update["agents_completed"]
                for i, expected_agent in enumerate(expected_order):
                    if expected_agent in completed:
                        assert completed.index(expected_agent) == i, \
                            f"Agent {expected_agent} completed out of order"
    
    async def test_supervisor_rejection_stops_pipeline(self):
        """Test that supervisor rejection stops the pipeline."""
        orchestrator = get_orchestrator()
        
        # Use a prompt that will be rejected (too short)
        prompt = "AI"
        
        updates = []
        async for state in orchestrator.run_streaming(
            user_id="test-user",
            user_prompt=prompt,
            run_id="test-rejection-001",
        ):
            updates.append({
                "current_agent": state.get("current_agent"),
                "agents_completed": state.get("agents_completed", []),
                "error": state.get("error"),
            })
        
        # Should only have supervisor update
        assert len(updates) == 1, f"Expected 1 update (supervisor only), got {len(updates)}"
        
        # Verify supervisor rejected
        assert updates[0]["current_agent"] == "supervisor"
        assert updates[0]["error"] is not None
        assert "too short" in updates[0]["error"].lower()
        
        # Verify no other agents ran
        assert updates[0]["agents_completed"] == ["supervisor"]
    
    async def test_personalization_queries_in_stream(self):
        """Test that personalization queries appear in stream."""
        orchestrator = get_orchestrator()
        
        prompt = "Machine learning best practices 2026"
        
        queries_found = False
        async for state in orchestrator.run_streaming(
            user_id="test-user",
            user_prompt=prompt,
            run_id="test-queries-001",
        ):
            queries = state.get("personalization_queries", [])
            if queries:
                queries_found = True
                # Verify we got 5 queries (standard output)
                assert len(queries) == 5, f"Expected 5 queries, got {len(queries)}"
                # Verify queries are non-empty strings
                for q in queries:
                    assert isinstance(q, str)
                    assert len(q) > 0
                break
        
        assert queries_found, "Personalization queries not found in stream"


# Run with: pytest tests/integration/test_streaming_pipeline.py -v
# Run with markers: pytest tests/integration/ -v -m asyncio
