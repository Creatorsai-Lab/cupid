# Cupid Agent Pipeline - Quick Start Guide

## 🚀 What Was Fixed

Your multiagent system was **stuck on the personalization agent** because the router was bypassing the LangGraph orchestrator. Now it's fixed and optimized!

### Main Issues Resolved
1. ✅ **Router now uses orchestrator** - Proper LangGraph flow
2. ✅ **Added user_voice mapping** - Composer gets correct tone
3. ✅ **Consolidated 3 files into 1** - Cleaner codebase
4. ✅ **Enhanced test coverage** - Full pipeline testing

## 📁 File Structure (After Optimization)

```
backend/app/agents/
├── graph.py                    # ✅ Fixed - Now sets user_voice
├── state.py                    # ✓ Unchanged
├── personalization/
│   ├── agent.py               # ✓ Working correctly
│   └── local_heuristic.py     # ✓ Working correctly
├── research/
│   ├── agent.py               # ✓ Working correctly
│   └── search.py              # ✓ Working correctly
└── composer/
    ├── agent.py               # ✅ Updated imports
    ├── composer_utils.py      # ✨ NEW - Consolidated utilities
    ├── platform_rules.py      # ✓ Kept as requested
    └── prompts.py             # ✓ Kept as requested

backend/app/routers/
└── agents.py                  # ✅ Fixed - Uses orchestrator

backend/
└── test_agent.py              # ✅ Enhanced - Full pipeline test
```

## 🧪 Testing Your Agents

### 1. Quick Test (Recommended)
```bash
cd backend
python test_agent.py
```

**Expected Output**:
```
🚀 Testing Full Agent Pipeline...
----------------------------------------------------------------------
----- Personalization Agent Start -----
[personalization] queries  : 5 generated
----- Personalization Agent Done -----
----- Research Agent Start -----
[research] fetched   : 8 pages across 6 domains
----- Research Agent Done -----
----- Composer Agent Start -----
[composer] done     : 3/3 posts produced | avg score=0.68
----- Composer Agent Done -----

✅ Pipeline Execution Complete!
Status: completed
Agents Completed: ['personalization', 'research', 'composer']

🎯 Personalization Agent:
  Generated 5 search queries:
    1. AI research breakthroughs 2026
    2. latest machine learning papers
    ...

📊 Research Agent:
  Search Results: 15
  Pages Fetched: 8

✍️  Composer Agent:
  Generated 3 post variants
  Extracted 8 atomic facts
  Used 3 top sources
```

### 2. API Test (Full Stack)
```bash
# Terminal 1: Start backend
cd backend
uvicorn app.main:app --reload

# Terminal 2: Test API
curl -X POST http://localhost:8000/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "prompt": "AI trends in 2026",
    "platform": "LinkedIn",
    "tone": "Hook First",
    "length": "Medium"
  }'

# Response:
{
  "run_id": "abc-123-def",
  "status": "pending",
  "message": "Agent pipeline started..."
}

# Poll for results:
curl http://localhost:8000/api/v1/agents/runs/abc-123-def \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## 🎯 How the Pipeline Works Now

### Flow Diagram
```
User Request
    ↓
API Router (agents.py)
    ↓
Orchestrator.run() ← ✨ THIS WAS THE FIX
    ↓
LangGraph Pipeline
    ├─ 1. Personalization Agent
    │     ├─ Groq LLM (Llama 3.3 70B)
    │     ├─ Fallback: Hugging Face
    │     └─ Fallback: Local heuristic
    │     → Outputs: 5 search queries
    │
    ├─ 2. Research Agent
    │     ├─ Tavily Search API
    │     ├─ Web scraping
    │     └─ Content extraction
    │     → Outputs: Top search results + fetched pages
    │
    └─ 3. Composer Agent
          ├─ Source Ranking (BM25 + persona)
          ├─ Evidence Distillation (LLM)
          ├─ Parallel Generation (3 variants)
          └─ Quality Scoring (deterministic)
          → Outputs: 3 platform-ready posts
    ↓
Final State
    ↓
Response to User
```

## 🔧 Configuration

### Required API Keys (.env)
```bash
# LLM Providers (at least one required)
GROQ_API_KEY=gsk_...              # Primary (recommended)
HUGGINGFACE_API_KEY=hf_...        # Fallback

# Search (required for research agent)
TAVILY_API_KEY=tvly-...

# Optional
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...
```

### Provider Priority
1. **Groq** (Llama 3.3 70B) - Fast, high quality, generous free tier
2. **Hugging Face** (Llama 3.2 3B) - Fallback, free tier
3. **Local Heuristic** - Zero-LLM fallback (personalization only)

## 📊 Understanding the Output

### Personalization Agent
- **Input**: User prompt + persona
- **Output**: 5 orthogonal search queries
- **Angles**: Facts, Recency, Expertise, Practical, Contrarian

### Research Agent
- **Input**: 5 search queries
- **Output**: Top search results + fetched page content
- **Sources**: Tavily API + web scraping

### Composer Agent
- **Input**: Research data + persona + platform rules
- **Output**: 3 post variants (one per top source)
- **Voices**: Hook First, Data Driven, Story Led

### Quality Scores (0.0 - 1.0)
- **Length Fit** (20%): Within platform limits
- **Grounding** (35%): References actual facts
- **Persona Match** (20%): Matches user voice
- **Hook Strength** (25%): First-line quality
- **Composite**: Weighted average (threshold: 0.45)

## 🐛 Troubleshooting

### Issue: "No LLM providers configured"
**Solution**: Add at least one API key to `.env`:
```bash
GROQ_API_KEY=gsk_your_key_here
```

### Issue: "Research returned no usable pages"
**Solution**: Check Tavily API key:
```bash
TAVILY_API_KEY=tvly_your_key_here
```

### Issue: "Composer generated 0 posts"
**Cause**: No research data available
**Solution**: Ensure research agent completes successfully first

### Issue: Pipeline still seems stuck
**Debug Steps**:
1. Check logs for error messages
2. Verify all API keys are valid
3. Test each agent individually
4. Check network connectivity

## 📈 Performance Expectations

### Typical Execution Times
- **Personalization**: 1-3 seconds (with Groq)
- **Research**: 5-10 seconds (depends on sources)
- **Composer**: 3-5 seconds (parallel generation)
- **Total Pipeline**: 10-20 seconds

### Resource Usage
- **Memory**: ~200MB per request
- **CPU**: Minimal (mostly I/O bound)
- **Network**: ~5-10 API calls per request

## 🎨 Customization

### Add New Platform
Edit `backend/app/agents/composer/platform_rules.py`:
```python
PLATFORM_RULES["TikTok"] = PlatformRule(
    name="TikTok",
    max_chars=2200,
    target_chars=150,
    min_chars=50,
    use_hashtags=True,
    max_hashtags=5,
    format_hint="Ultra-short hook. Gen-Z voice.",
    structure="single_block",
)
```

### Add New Voice Angle
Edit `backend/app/agents/composer/prompts.py`:
```python
ANGLE_PROMPTS["educational"] = """
You are a social media copywriter specializing in EDUCATIONAL posts...
"""
```

### Adjust Quality Weights
Edit `backend/app/agents/composer/composer_utils.py`:
```python
_WEIGHTS = {
    "length_fit": 0.15,      # Reduce length importance
    "grounding": 0.40,       # Increase grounding importance
    "persona_match": 0.20,
    "hook_strength": 0.25,
}
```

## 📚 Code Organization

### Composer Utilities (composer_utils.py)
```python
# SOURCE RANKING
rank_sources(pages, prompt, persona, top_k=3)
  → Returns top K sources with rank_score

# EVIDENCE DISTILLATION  
distill_evidence(llm, prompt, sources)
  → Returns list of atomic facts

# QUALITY SCORING
score_variant(content, facts, persona, rule)
  → Returns QualityScore dataclass
```

### Platform Rules (platform_rules.py)
```python
rule_for(platform: str) → PlatformRule
  → Returns platform-specific constraints
```

### Prompts (prompts.py)
```python
ANGLE_PROMPTS = {
    "hook_first": "...",
    "data_driven": "...",
    "story_led": "...",
}

build_user_message(topic, facts, persona, rule, ...)
  → Returns formatted prompt for LLM
```

## 🚀 Production Deployment

### Environment Variables
```bash
# Production settings
APP_ENV=production
DEBUG=false
SECRET_KEY=<strong-random-key>

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/db

# Redis (for caching)
REDIS_URL=redis://host:6379/0

# API Keys
GROQ_API_KEY=...
TAVILY_API_KEY=...
```

### Monitoring
- Add logging to track agent execution times
- Monitor API rate limits (Groq, Tavily)
- Track quality scores over time
- Alert on pipeline failures

### Scaling
- Use Redis for caching research results
- Implement request queuing for high load
- Consider dedicated workers for long-running tasks
- Add rate limiting per user

## 🎉 Success Criteria

Your pipeline is working correctly when:
- ✅ All 3 agents complete in sequence
- ✅ Personalization generates 5 queries
- ✅ Research fetches 5+ pages
- ✅ Composer generates 3 variants
- ✅ Quality scores > 0.45
- ✅ Total execution < 30 seconds
- ✅ No errors in logs

## 📞 Need Help?

Check these files for detailed documentation:
- `AGENT_FIXES_SUMMARY.md` - Complete fix details
- `backend/app/agents/composer/prompts.py` - Prompt engineering
- `backend/app/agents/composer/platform_rules.py` - Platform specs
- `backend/test_agent.py` - Example usage

Happy building! 🚀
