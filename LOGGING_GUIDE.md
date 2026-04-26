# Cupid Agent System - Comprehensive Logging Guide

## 🎯 Overview

Your Cupid multiagent system now has **production-grade structured logging** inspired by industry leaders like OpenAI, Anthropic, and Perplexity AI. Every agent operation is fully traced with colored console output for easy monitoring and debugging.

## 🌈 Features

### ✨ What's Logged

1. **Agent Lifecycle**
   - Agent start with full context
   - Processing steps
   - Agent completion with metrics
   - Error handling with stack traces

2. **Input/Output Tracking**
   - User prompts and persona data
   - Generated queries (Personalization)
   - Search results and fetched pages (Research)
   - Generated posts and quality scores (Composer)

3. **Performance Metrics**
   - LLM API call latency
   - Search API latency
   - Source ranking time
   - Evidence extraction time
   - Post generation time
   - Total pipeline duration

4. **Quality Metrics**
   - Number of queries generated
   - Pages fetched per query
   - Facts extracted from sources
   - Quality scores per variant
   - Pass/fail threshold tracking

## 📊 Log Output Example

```
2026-04-26 10:30:15 INFO     [router]  (run:abc12345) ======================================================================
2026-04-26 10:30:15 INFO     [router]  (run:abc12345) 🚀 PIPELINE START
2026-04-26 10:30:15 INFO     [router]  (run:abc12345) ======================================================================
2026-04-26 10:30:15 INFO     [router]  (run:abc12345)   Run ID: abc12345-6789-...
2026-04-26 10:30:15 INFO     [router]  (run:abc12345)   User ID: user-123
2026-04-26 10:30:15 INFO     [router]  (run:abc12345)   Prompt: AI trends in 2026...
2026-04-26 10:30:15 INFO     [router]  (run:abc12345)   Platform: LinkedIn
2026-04-26 10:30:15 INFO     [router]  (run:abc12345)   Tone: Hook First → Voice: hook_first
2026-04-26 10:30:15 INFO     [router]  (run:abc12345)   Length: Medium
2026-04-26 10:30:15 INFO     [router]  (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:15 INFO     [orchestrator] (run:abc12345) 🎯 Orchestrator initializing pipeline
2026-04-26 10:30:15 INFO     [orchestrator] (run:abc12345)   Graph nodes: ['personalization', 'research', 'composer']
2026-04-26 10:30:15 INFO     [orchestrator] (run:abc12345) 🚀 Executing LangGraph pipeline

2026-04-26 10:30:15 INFO     [personalization] (run:abc12345) ======================================================================
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345) 🚀 PERSONALIZATION AGENT START
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345) ======================================================================
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   user_prompt: AI trends in 2026
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   content_niche: AI / Machine Learning
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   content_goal: thought_leadership
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   target_audience: developers
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   target_country: United States
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345) ⚙️  STEP: Analyzing user persona
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   Niche: AI / Machine Learning
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   Goal: thought_leadership
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   Audience: developers
2026-04-26 10:30:15 INFO     [personalization] (run:abc12345)   Region: United States
2026-04-26 10:30:16 INFO     [personalization] (run:abc12345) ⚙️  STEP: Running LLM provider chain
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) 📊 METRIC [provider_used]: groq-llama-3.3-70b
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) 📊 METRIC [latency_ms]: 1234
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) 📊 METRIC [queries_generated]: 5
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) 📋 GENERATED QUERIES:
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   [1] FACTS        → AI research breakthroughs 2026 statistics
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   [2] RECENCY      → latest AI developments January 2026
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   [3] EXPERTISE    → leading AI researchers predictions 2026
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   [4] PRACTICAL    → implementing AI systems 2026 guide
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   [5] CONTRARIAN   → AI hype vs reality 2026 criticism
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) ✅ PERSONALIZATION AGENT COMPLETE
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   queries_generated: 5
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   provider: groq-llama-3.3-70b
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345)   latency_ms: 1234ms
2026-04-26 10:30:17 INFO     [personalization] (run:abc12345) ======================================================================

2026-04-26 10:30:17 INFO     [research] (run:abc12345) ======================================================================
2026-04-26 10:30:17 INFO     [research] (run:abc12345) 🚀 RESEARCH AGENT START
2026-04-26 10:30:17 INFO     [research] (run:abc12345) ======================================================================
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   queries_count: 5
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   niche: AI / Machine Learning
2026-04-26 10:30:17 INFO     [research] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:17 INFO     [research] (run:abc12345) 📋 INPUT QUERIES:
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   [1] AI research breakthroughs 2026 statistics
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   [2] latest AI developments January 2026
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   [3] leading AI researchers predictions 2026
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   [4] implementing AI systems 2026 guide
2026-04-26 10:30:17 INFO     [research] (run:abc12345)   [5] AI hype vs reality 2026 criticism
2026-04-26 10:30:17 INFO     [research] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:17 INFO     [research] (run:abc12345) ⚙️  STEP: Executing search pipeline
2026-04-26 10:30:25 INFO     [research] (run:abc12345) 📊 METRIC [pages_fetched]: 12
2026-04-26 10:30:25 INFO     [research] (run:abc12345) 📊 METRIC [unique_domains]: 8
2026-04-26 10:30:25 INFO     [research] (run:abc12345) 📊 METRIC [latency_ms]: 7856
2026-04-26 10:30:25 INFO     [research] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:25 INFO     [research] (run:abc12345) 📄 FETCHED PAGES:
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   [ 1] arxiv.org                      |   4523 chars | AI Breakthroughs in 2026: A Comprehensive Review
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   [ 2] techcrunch.com                 |   3201 chars | Latest AI Developments Shaping 2026
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   [ 3] mit.edu                        |   5678 chars | MIT Researchers Predict AI Future
2026-04-26 10:30:25 INFO     [research] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:25 INFO     [research] (run:abc12345) 🌐 DOMAIN DISTRIBUTION:
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   arxiv.org                      : 3 pages
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   techcrunch.com                 : 2 pages
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   mit.edu                        : 2 pages
2026-04-26 10:30:25 INFO     [research] (run:abc12345) ✅ RESEARCH AGENT COMPLETE
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   pages_fetched: 12
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   unique_domains: 8
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   latency_ms: 7856ms
2026-04-26 10:30:25 INFO     [research] (run:abc12345)   avg_page_length: 4134 chars
2026-04-26 10:30:25 INFO     [research] (run:abc12345) ======================================================================

2026-04-26 10:30:25 INFO     [composer] (run:abc12345) ======================================================================
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) 🚀 COMPOSER AGENT START
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) ======================================================================
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   platform: LinkedIn
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   tone: Hook First
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   voice: hook_first
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   length: Medium
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   pages_available: 12
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) ⚙️  STEP: Ranking sources - BM25 + persona boosting on 12 pages
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) 📊 METRIC [source_ranking_latency_ms]: 45
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) 🏆 TOP SOURCES SELECTED:
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   [1] arxiv.org                      | score=0.856 | AI Breakthroughs in 2026: A Comprehensive Review
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   [2] mit.edu                        | score=0.782 | MIT Researchers Predict AI Future
2026-04-26 10:30:25 INFO     [composer] (run:abc12345)   [3] techcrunch.com                 | score=0.734 | Latest AI Developments Shaping 2026
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:25 INFO     [composer] (run:abc12345) ⚙️  STEP: Distilling evidence - Extracting atomic facts from 3 sources
2026-04-26 10:30:27 INFO     [composer] (run:abc12345) 📊 METRIC [evidence_extraction_latency_ms]: 1567
2026-04-26 10:30:27 INFO     [composer] (run:abc12345) 📊 METRIC [facts_extracted]: 8
2026-04-26 10:30:27 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:27 INFO     [composer] (run:abc12345) 💎 EXTRACTED FACTS:
2026-04-26 10:30:27 INFO     [composer] (run:abc12345)   [STAT        ] Source 0 → AI research funding increased by 47% in 2026
2026-04-26 10:30:27 INFO     [composer] (run:abc12345)   [QUOTE       ] Source 1 → "AI will transform every industry by 2027" - Dr. Smith
2026-04-26 10:30:27 INFO     [composer] (run:abc12345)   [ENTITY      ] Source 0 → OpenAI released GPT-5 in January 2026
2026-04-26 10:30:27 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:27 INFO     [composer] (run:abc12345) ⚙️  STEP: Generating posts - 3 variants in parallel (voice=hook_first)
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) 📊 METRIC [generation_latency_ms]: 2834
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) ⚙️  STEP: Scoring variants - Multi-axis quality evaluation
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   Post 1 | arxiv.org                 | score=0.72 | len=456 | ✓
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   Post 2 | mit.edu                   | score=0.68 | len=423 | ✓
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   Post 3 | techcrunch.com            | score=0.65 | len=401 | ✓
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) 📊 QUALITY SUMMARY:
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   Posts generated: 3/3
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   Average score: 0.68
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   Passing threshold: 3/3
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) 📝 GENERATED POSTS:
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   [1] AI research funding jumped 47% in 2026. Here's what that means for developers...
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   [2] Most people think AI peaked. The data says otherwise...
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   [3] GPT-5 launched in January. Three things nobody's talking about...
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) ──────────────────────────────────────────────────────────────────────
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) ✅ COMPOSER AGENT COMPLETE
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   posts_generated: 3/3
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   avg_quality_score: 0.68
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   passing_threshold: 3/3
2026-04-26 10:30:30 INFO     [composer] (run:abc12345)   total_latency_ms: 4446ms
2026-04-26 10:30:30 INFO     [composer] (run:abc12345) ======================================================================

2026-04-26 10:30:30 INFO     [orchestrator] (run:abc12345) ✅ LangGraph pipeline complete
2026-04-26 10:30:30 INFO     [router] (run:abc12345) ======================================================================
2026-04-26 10:30:30 INFO     [router] (run:abc12345) ✅ PIPELINE COMPLETE
2026-04-26 10:30:30 INFO     [router] (run:abc12345)   Agents completed: ['personalization', 'research', 'composer']
2026-04-26 10:30:30 INFO     [router] (run:abc12345)   Status: completed
2026-04-26 10:30:30 INFO     [router] (run:abc12345) ======================================================================
```

## 🎨 Color Coding

- **Cyan** - INFO level messages
- **Yellow** - WARNING level messages
- **Red** - ERROR level messages
- **Magenta** - CRITICAL level messages
- **Blue** - Personalization agent
- **Green** - Research agent
- **Magenta** - Composer agent
- **Cyan** - Orchestrator
- **Yellow** - Router

## 🔧 Configuration

### Log Levels

Set in `.env` or via `DEBUG` setting:

```bash
# Development (verbose)
DEBUG=true  # Sets log level to DEBUG

# Production (concise)
DEBUG=false  # Sets log level to INFO
```

### Programmatic Configuration

```python
from app.core.logging_config import setup_logging

# Initialize logging
setup_logging(level="DEBUG")  # or "INFO", "WARNING", "ERROR"
```

## 📝 Using the Logger

### In Agent Code

```python
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("my_agent")

# Agent lifecycle
logger.agent_start(run_id, param1="value1", param2="value2")
logger.agent_complete(run_id, metric1="value1", metric2="value2")
logger.agent_error(run_id, exception)

# Processing steps
logger.log_step(run_id, "Step name", "Optional details")

# Metrics
logger.log_metric(run_id, "metric_name", value)

# Input/Output
logger.log_input(run_id, "label", content, max_length=200)
logger.log_output(run_id, "label", content, max_length=200)

# Standard logging
logger.info("Message", run_id)
logger.warning("Warning message", run_id)
logger.error("Error message", run_id, exc_info=True)
```

### LLM API Calls

```python
from app.core.logging_config import log_api_call

log_api_call(
    logger=logger,
    run_id=run_id,
    provider="groq",
    model="llama-3.3-70b",
    prompt_tokens=1234,
    completion_tokens=567,
    latency_ms=1500,
)
```

### Search API Calls

```python
from app.core.logging_config import log_search_call

log_search_call(
    logger=logger,
    run_id=run_id,
    query="AI trends 2026",
    results_count=15,
    latency_ms=2500,
)
```

## 📊 Monitoring Best Practices

### 1. Track Key Metrics

Monitor these metrics for performance optimization:

- **Personalization latency** - Should be < 3s with Groq
- **Research latency** - Typically 5-10s depending on sources
- **Composer latency** - Should be < 5s for 3 variants
- **Total pipeline** - Target < 20s end-to-end

### 2. Quality Thresholds

Watch for quality score trends:

- **Composite score** - Should average > 0.60
- **Passing rate** - Target > 80% of variants passing threshold
- **Grounding score** - Should be > 0.50 (factual accuracy)

### 3. Error Patterns

Monitor for:

- **Provider fallbacks** - If Groq fails frequently, check API key/quota
- **Empty results** - Research returning no pages indicates search issues
- **Low quality scores** - May indicate prompt tuning needed

## 🔍 Debugging Tips

### Find Specific Run

```bash
# Grep for specific run ID
tail -f backend.log | grep "abc12345"

# Follow a specific agent
tail -f backend.log | grep "\[personalization\]"

# Watch for errors
tail -f backend.log | grep "ERROR"
```

### Performance Analysis

```bash
# Extract latency metrics
grep "latency_ms" backend.log | grep "abc12345"

# Count queries per run
grep "queries_generated" backend.log | grep "abc12345"

# Check quality scores
grep "avg_quality_score" backend.log | grep "abc12345"
```

### Common Issues

**Issue**: No logs appearing
```bash
# Check logging is initialized
grep "Cupid API Starting" backend.log

# Verify log level
grep "Log Level" backend.log
```

**Issue**: Too verbose
```bash
# Set to INFO level
export DEBUG=false
# or in .env
DEBUG=false
```

**Issue**: Missing run_id in logs
```bash
# Ensure run_id is passed to all logger calls
logger.info("Message", run_id)  # ✓ Correct
logger.info("Message")          # ✗ Missing run_id
```

## 🚀 Production Deployment

### Log Aggregation

For production, consider:

1. **File Logging**
   ```python
   # Add file handler in logging_config.py
   file_handler = logging.FileHandler("cupid.log")
   file_handler.setFormatter(ColoredFormatter())
   root_logger.addHandler(file_handler)
   ```

2. **JSON Logging**
   ```python
   # Use JSON formatter for structured logs
   import json
   
   class JSONFormatter(logging.Formatter):
       def format(self, record):
           return json.dumps({
               "timestamp": self.formatTime(record),
               "level": record.levelname,
               "agent": getattr(record, "agent", None),
               "run_id": getattr(record, "run_id", None),
               "message": record.getMessage(),
           })
   ```

3. **External Services**
   - **Datadog** - APM and log aggregation
   - **Sentry** - Error tracking
   - **CloudWatch** - AWS logging
   - **ELK Stack** - Elasticsearch, Logstash, Kibana

### Metrics Dashboard

Track these KPIs:

- **Throughput**: Requests per minute
- **Latency**: P50, P95, P99 response times
- **Error rate**: Failed requests / total requests
- **Quality**: Average quality score over time
- **Cost**: API calls per request (LLM + Search)

## 📚 Files Modified

- ✅ `backend/app/core/logging_config.py` - New logging system
- ✅ `backend/app/main.py` - Initialize logging on startup
- ✅ `backend/app/agents/personalization/agent.py` - Added comprehensive logging
- ✅ `backend/app/agents/research/agent.py` - Added comprehensive logging
- ✅ `backend/app/agents/composer/agent.py` - Added comprehensive logging
- ✅ `backend/app/agents/graph.py` - Added orchestrator logging
- ✅ `backend/app/routers/agents.py` - Added router logging

## 🎉 Benefits

✅ **Full Visibility** - See exactly what each agent is doing
✅ **Performance Tracking** - Monitor latency and throughput
✅ **Quality Monitoring** - Track quality scores over time
✅ **Easy Debugging** - Colored output with run ID tracking
✅ **Production Ready** - Structured logging for aggregation
✅ **Industry Standard** - Follows best practices from AI leaders

Your Cupid system now has enterprise-grade observability! 🚀
