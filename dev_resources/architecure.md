# Cupid Platform Archiecture

## Agent 1: Supervisor Agent

## Agent 2: Researcher Agent

1. Take user input and generate search keywords
2. Retrieve web content piece (corpus) from generated search keywords
3. Rank and personalized pick the relevent pieces and preapre to forward downstream composer agent

- Focus on robustness, safety and not broken
- Proper error handling and retry
- Ranking best content based on three factor user input intent, relevency and personazliation info.

---
## AI thoughts of Research agent:

Use async functions with clear input/output contracts. Not Subagents because these are for cross-domain workflows (research + code + design), not for sequential data processing. This should be a workflow, not an autonomous agent loop

1. keyword_gen layer (keyword_gen.py)

The LLM generates the queries (Stage 1), then your code executes them in parallel

2. Retrieval Layer (Parallel Search) (retriever.py)

- Retriever is a TOOL, not an Agent — Don't use an LLM to call the search API. Use deterministic code. after getting keywords
- Use Tavily as your primary search API. It was purpose-built for AI agents, returns structured JSON with clean content snippets, and has the best architectural fit for RAG/agent pipelines
- Brave Search API as a secondary/fallback — it scored highest in the 2026 agentic search benchmark (Agent Score: 14.89, latency: 669ms)
Exa for semantic discovery when keyword search fails (it uses neural embeddings, not keyword matching)
- For content extraction, run a fallback chain rather than a single method:
- Deduplicate results by URL + content hash before scoring
- Parallel Execution — All search queries fire simultaneously. Don't sequential-loop through queri

Latency consideration:
An independent December 2025 benchmark ran 50 real queries through five APIs: Exa averaged 1.18 seconds (the fastest), Tavily 1.885 seconds, both at a 100% success rate.

Budget-friendly alternative:
Serper + Jina Reader drops the bill to $11 per month, 88% off Tavily. But you'll need to handle content extraction yourself.

Critical: Don't use just one API call per query. Run all 3-5 queries in parallel (Promise.all / asyncio.gather), then merge and deduplicate by URL. This is how you get your 15-25 raw pieces in under 3 seconds.

3. Scoring and ranking layer (scoring.py)

4. Best Results (result_pool.py)



ok I got it lets build it, First I will build and test the agent in separate system and  then will add in main project. So all you models, config and files will be in same folder.
