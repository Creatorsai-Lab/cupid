"""
Quick test script to verify the full agent pipeline works.

Run: python test_agent.py
"""
import asyncio
from app.agents.graph import get_orchestrator


async def test_full_pipeline():
    print("🚀 Testing Full Agent Pipeline (Personalization → Research → Composer)...")
    print("-" * 10)

    orchestrator = get_orchestrator()

    # Simulate a user request
    result = await orchestrator.run(
        user_id="test-user-123",
        user_prompt="latest AI research trends in 2026",
        run_id="test-run-001",
        content_type="Text",
        target_platform="LinkedIn",
        content_length="Medium",
        tone="Genz",
        personalization={
            "name": "Test User",
            "nickname": "Tester",
            "bio": "AI researcher and practitioner who loves breaking down complex topics",
            "content_niche": "AI / Machine Learning",
            "content_goal": "thought_leadership",
            "content_intent": "insightful",
            "target_age_group": "professionals",
            "target_country": "United States",
            "target_audience": "developers and ML engineers",
            "usp": "I summarize research papers into practical engineering takeaways.",
        },
    )

    print("\n✅ Pipeline Execution Complete!")
    print(f"Status: {result.get('status')}")
    print(f"Run ID: {result.get('run_id')}")
    print(f"Agents Completed: {result.get('agents_completed')}")

    # Personalization results
    queries = result.get("personalization_queries", [])
    print(f"\n🎯 Personalization Agent:")
    print(f"  Generated {len(queries)} search queries:")
    for i, q in enumerate(queries, 1):
        print(f"    {i}. {q}")

    # Research results
    rd = result.get("research_data")
    if rd:
        print(f"\n📊 Research Agent:")
        print(f"  Search Results: {len(rd.get('top_search_results', []))}")
        print(f"  Pages Fetched: {len(rd.get('fetched_pages', []))}")
        
        top = rd.get("top_search_results") or []
        if top:
            print(f"\n  Top 3 Sources:")
            for i, item in enumerate(top[:3], 1):
                print(f"    {i}. {item.get('title', '')[:60]}...")
                print(f"       {item.get('domain', '')} (score: {float(item.get('score', 0)):.2f})")

    # Composer results
    composer_output = result.get("composer_output", [])
    composer_evidence = result.get("composer_evidence", [])
    composer_sources = result.get("composer_sources", [])
    
    if composer_output:
        print(f"\n✍️  Composer Agent:")
        print(f"  Generated {len(composer_output)} post variants")
        print(f"  Extracted {len(composer_evidence)} atomic facts")
        print(f"  Used {len(composer_sources)} top sources")
        
        print(f"\n  Generated Posts:")
        for i, variant in enumerate(composer_output, 1):
            quality = variant.get("quality", {})
            print(f"\n  [{i}] {variant.get('angle', 'unknown').upper()} (Source #{variant.get('source_rank', '?')})")
            print(f"      Platform: {variant.get('platform', 'unknown')}")
            print(f"      Length: {variant.get('char_count', 0)} chars")
            print(f"      Quality Score: {quality.get('composite', 0):.2f} {'✓' if quality.get('passes', False) else '✗'}")
            print(f"      - Length Fit: {quality.get('length_fit', 0):.2f}")
            print(f"      - Grounding: {quality.get('grounding', 0):.2f}")
            print(f"      - Persona Match: {quality.get('persona_match', 0):.2f}")
            print(f"      - Hook Strength: {quality.get('hook_strength', 0):.2f}")
            print(f"\n      Content Preview:")
            content = variant.get('content', '')
            preview = content[:200] + "..." if len(content) > 200 else content
            print(f"      {preview}")

    err = result.get("error")
    if err:
        print(f"\n❌ Error: {err}")
    
    print("\n" + "=" * 10)
    print("✨ Test Complete!")


if __name__ == "__main__":
    asyncio.run(test_full_pipeline())
