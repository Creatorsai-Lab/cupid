"""
Quick test script to verify the research agent works.

Run: python test_agent.py
"""
import asyncio
from app.agents.graph import get_orchestrator


async def test_research_agent():
    print("🚀 Testing Research Agent...")
    print("-" * 50)

    orchestrator = get_orchestrator()

    # Simulate a user request
    result = await orchestrator.run(
        user_id="test-user-123",
        user_prompt="latest AI research trends",
        run_id="test-run-001",
        content_type="Text",
        target_platform="All",
        content_length="Medium",
        tone="Informative",
        personalization={
            "name": "Test User",
            "nickname": "Tester",
            "bio": "AI researcher and practitioner",
            "content_niche": "AI / Machine Learning",
            "content_goal": "thought_leadership",
            "content_intent": "insightful",
            "target_age_group": "professionals",
            "target_country": "United States",
            "target_audience": "developers",
            "usp": "I summarize research papers into practical engineering takeaways.",
        },
    )

    print("\n✅ Agent Execution Complete!")
    print(f"Status: {result.get('status')}")
    print(f"Run ID: {result.get('run_id')}")
    print(f"Agents Completed: {result.get('agents_completed')}")

    rd = result.get("research_data")
    if rd:
        print(f"\n📊 Research Results:")
        print(f"  Keywords Generated: {len(rd.get('generated_keywords', []))}")
        print(f"  Search Results: {len(rd.get('top_search_results', []))}")
        print(f"  Pages Fetched: {len(rd.get('fetched_pages', []))}")
        print(f"\n  Keywords: {rd.get('generated_keywords', [])}")

        top = rd.get("top_search_results") or []
        if top:
            print(f"\n  Top 3 Sources:")
            for i, item in enumerate(top[:3], 1):
                print(f"    {i}. {item.get('title', '')[:60]}...")
                print(f"       {item.get('domain', '')} (score: {float(item.get('score', 0)):.2f})")

    err = result.get("error")
    if err:
        print(f"\n❌ Error: {err}")


if __name__ == "__main__":
    asyncio.run(test_research_agent())
