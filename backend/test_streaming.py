"""
Quick test to verify streaming updates work.

Run: python test_streaming.py
"""
import asyncio
from app.agents.graph import get_orchestrator


async def test_streaming():
    """Test that streaming yields intermediate states."""
    print("=" * 70)
    print("🧪 TESTING STREAMING PIPELINE")
    print("=" * 70)
    print()
    
    orchestrator = get_orchestrator()
    
    prompt = "AI trends in healthcare 2026"
    personalization = {
        "content_niche": "Healthcare Technology",
        "target_audience": "Healthcare professionals",
    }
    
    print(f"📝 Prompt: {prompt}")
    print(f"👤 Niche: {personalization['content_niche']}")
    print()
    print("─" * 70)
    print("📡 STREAMING UPDATES:")
    print("─" * 70)
    
    update_count = 0
    async for state in orchestrator.run_streaming(
        user_id="test-user",
        user_prompt=prompt,
        run_id="test-run-123",
        personalization=personalization,
    ):
        update_count += 1
        current = state.get("current_agent", "unknown")
        completed = state.get("agents_completed", [])
        queries = state.get("personalization_queries", [])
        error = state.get("error")
        
        print(f"\n[Update {update_count}]")
        print(f"  Current agent: {current}")
        print(f"  Completed: {completed}")
        print(f"  Queries: {len(queries)} generated")
        if queries:
            for i, q in enumerate(queries[:3], 1):
                print(f"    {i}. {q}")
        if error:
            print(f"  ❌ Error: {error[:100]}")
    
    print()
    print("─" * 70)
    print(f"✅ Received {update_count} streaming updates")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_streaming())
