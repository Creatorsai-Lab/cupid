https://medium.com/@vedantparmarsingh/how-i-built-a-multi-agent-ai-system-that-changed-my-development-workflow-forever-2fede7780d0f

https://www.freecodecamp.org/news/build-and-deploy-multi-agent-ai-with-python-and-docker/


## Architecture Reference
1. https://www.anthropic.com/engineering/
1. https://www.anthropic.com/engineering/multi-agent-research-system
https://github.com/FareedKhan-dev/Multi-Agent-AI-System/blob/main/multi_agent.ipynb
1. https://github.com/langchain-ai/social-media-agent
2. https://github.com/openai/swarm/
3. https://github.com/langchain-ai/langgraph-swarm-py


## Inspiration Reference
2. https://github.com/Haileamlak/conca

## Social Media API for developers
https://zernio.com/
https://www.outstand.so/blog/best-unified-social-media-apis-for-devs

## NEWS API
https://newsdata.io/blog/best-free-news-api/


## Competitor
1. Jasper AI
2. Copy.ai

### Key points
- There is a downside: in practice, these architectures burn through tokens fast. Agents typically use about 4× more tokens than chat interactions, and multi-agent systems use about 15× more tokens than chats. For economic viability, multi-agent systems require tasks where the value of the task is high enough to pay for the increased performance. Further, some domains that require all agents to share the same context or involve many dependencies between agents are not a good fit for multi-agent systems today
- Traditional approaches using Retrieval Augmented Generation (RAG) use static retrieval. That is, they fetch some set of chunks that are most similar to an input query and use these chunks to generate a response. In contrast, our architecture uses a multi-step search that dynamically finds relevant information, adapts to new findings, and analyzes results to formulate high-quality answers
- Multi-agent systems have key differences from single-agent systems, including a rapid growth in coordination complexity. Early agents made errors like spawning 50 subagents for simple queries, scouring the web endlessly for nonexistent sources, and distracting each other with excessive updates. Since each agent is steered by a prompt, **prompt engineering was our primary lever for improving these behaviors**. _Below are some principles we learned for prompting agents:_
    - Think like your agents: Effective prompting relies on developing an accurate mental model of the agent, 
    - Teach the orchestrator how to delegate: Each subagent needs an objective, an output format, guidance on the tools and sources to use, and clear task boundaries. Without detailed task descriptions, agents duplicate work, leave gaps, or fail to find necessary information
    - Scale effort to query complexity:Agents struggle to judge appropriate effort for different tasks, so we embedded scaling rules in the prompts. Simple fact-finding requires just 1 agent with 3-10 tool calls, direct comparisons might need 2-4 subagents with 10-15 calls each, and complex research might use more than 10 subagents with clearly divided responsibilities.
    - Tool design and selection are critical: each tool needs a distinct purpose and a clear description.
    - Let agents improve themselves: Even create a tool-testing agent—when given a flawed MCP tool, it attempts to use the tool and then rewrites the tool description to avoid failures. By testing the tool dozens of times, this agent found key nuances and bugs
    - Parallel tool calling transforms speed and performance: For speed, we use two kinds of parallelization: (1) the lead agent spins up 3-5 subagents in parallel rather than serially; (2) the subagents use 3+ tools in parallel.
- Prompting strategies should focus on developing effective heuristics rather than rigid rules.. Think about how skilled humans approach research tasks and encoded these strategies in prompts—strategies like decomposing difficult questions into smaller tasks, carefully evaluating the quality of sources, adjusting search approaches based on new information, and recognizing when to focus on depth (investigating one topic in detail) vs. breadth (exploring many topics in parallel)
- Place all agent components into a single container, which meant the session, agent harness, and sandbox all shared an environment. There were benefits to this approach, including that file edits are direct syscalls, and there were no service boundaries to design.
- **Context engineering vs. prompt engineering**: context engineering is the natural progression of prompt engineering. Prompt engineering refers to methods for writing and organizing LLM instructions for optimal outcomes (see our docs for an overview and useful prompt engineering strategies). Context engineering refers to the set of strategies for curating and maintaining the optimal set of tokens (information) during LLM inference

### Effective evaluation of agents
-  Traditional evaluations often assume that the AI follows the same steps each time: given input X, the system should follow path Y to produce output Z. But multi-agent systems don't work this way. Even with identical starting points, agents might take completely different valid paths to reach their goal. One agent might search three sources while another searches ten, or they might use different tools to find the same answer. Because we don’t always know what the right steps are, we usually can't just check if agents followed the “correct” steps we prescribed in advance. Instead, we need flexible evaluation methods that judge whether agents achieved the right outcomes while also following a reasonable process.
- Start with a **set of about 20 queries** representing real usage patterns. Testing these queries often allowed to clearly see the impact of changes. 
- **LLM-as-judge evaluation scales when done well**. Research outputs are difficult to evaluate programmatically, since they are free-form text and rarely have a single correct answer. LLMs are a natural fit for grading outputs. We used an LLM judge that evaluated each output against criteria in a rubric: factual accuracy (do claims match sources?), citation accuracy (do the cited sources match the claims?), completeness (are all requested aspects covered?), source quality (did it use primary sources over lower-quality secondary sources?), and tool efficiency (did it use the right tools a reasonable number of times?)
- Add source quality heuristics in prompts to choose good ssource content instead of SEO optimized, click-bait content.
- Adding full production tracing let us diagnose why agents failed and fix issues systematically. Beyond standard observability, we monitor agent decision patterns and interaction structures. This high-level observability help to diagnose root causes, discover unexpected behaviors, and fix common failures.
- **Deployment needs careful coordination:** Agent systems are highly stateful webs of prompts, tools, and execution logic that run almost continuously. This means that whenever we deploy updates, agents might be anywhere in their process. We therefore need to prevent our well-meaning code changes from breaking existing agents. We can’t update every agent to the new version at the same time. Instead, we use **[rainbow deployments](https://brandon.dimcheff.com/2018/02/rainbow-deploys-with-kubernetes/)** to avoid disrupting running agents, by gradually shifting traffic from old to new versions while keeping both running simultaneously.