# Logging Quick Reference Card

## 🚀 Quick Start

```bash
# Start backend with logging
cd backend
uvicorn app.main:app --reload

# Test with full logging
python test_agent.py
```

## 📊 What You'll See

```
======================================================================
🚀 PIPELINE START
======================================================================
  Run ID: abc12345-6789-...
  Prompt: AI trends in 2026
  Platform: LinkedIn
  Tone: Hook First → Voice: hook_first

🔵 PERSONALIZATION AGENT
  ✓ 5 queries generated in 1.2s
  ✓ Provider: groq-llama-3.3-70b

🟢 RESEARCH AGENT
  ✓ 12 pages fetched from 8 domains in 7.8s
  ✓ Top sources: arxiv.org, mit.edu, techcrunch.com

🟣 COMPOSER AGENT
  ✓ 3 posts generated in 4.4s
  ✓ Average quality: 0.68
  ✓ All posts passing threshold

✅ PIPELINE COMPLETE (15.2s total)
======================================================================
```

## 🎨 Color Guide

| Color | Meaning |
|-------|---------|
| 🔵 Blue | Personalization agent |
| 🟢 Green | Research agent |
| 🟣 Magenta | Composer agent |
| 🔷 Cyan | Orchestrator / INFO |
| 🟡 Yellow | Router / WARNING |
| 🔴 Red | ERROR |

## 📝 Log Symbols

| Symbol | Meaning |
|--------|---------|
| 🚀 | Agent/Pipeline start |
| ✅ | Agent/Pipeline complete |
| ❌ | Error/Failure |
| ⚙️ | Processing step |
| 📊 | Metric |
| 📋 | List/Collection |
| 📄 | Document/Page |
| 🏆 | Top result |
| 💎 | Extracted fact |
| 📝 | Generated content |
| 🌐 | Domain/Network |
| 🔍 | Search |
| 🤖 | LLM call |

## 🔍 Common Grep Commands

```bash
# Follow specific run
tail -f backend.log | grep "abc12345"

# Watch specific agent
tail -f backend.log | grep "\[personalization\]"
tail -f backend.log | grep "\[research\]"
tail -f backend.log | grep "\[composer\]"

# Monitor errors
tail -f backend.log | grep "ERROR"

# Track performance
grep "latency_ms" backend.log
grep "METRIC" backend.log

# Check quality
grep "quality_score" backend.log
grep "passing_threshold" backend.log
```

## 📊 Key Metrics

### Personalization
- `queries_generated` - Should be 5
- `latency_ms` - Target < 3000ms
- `provider_used` - groq-llama-3.3-70b (primary)

### Research
- `pages_fetched` - Typically 8-15
- `unique_domains` - Source diversity
- `latency_ms` - Typically 5000-10000ms

### Composer
- `posts_generated` - Should be 3/3
- `avg_quality_score` - Target > 0.60
- `passing_threshold` - Target 3/3
- `total_latency_ms` - Target < 5000ms

## 🔧 Configuration

```bash
# .env file
DEBUG=true   # Verbose logging (development)
DEBUG=false  # Concise logging (production)
```

## 🐛 Debugging Checklist

### Pipeline Stuck?
```bash
# Check which agent is running
tail -f backend.log | grep "AGENT START"

# Look for errors
tail -f backend.log | grep "ERROR"
```

### Low Quality Scores?
```bash
# Check quality breakdown
grep "quality" backend.log | grep "abc12345"

# Review generated posts
grep "GENERATED POSTS" backend.log
```

### Slow Performance?
```bash
# Extract all latency metrics
grep "latency_ms" backend.log | grep "abc12345"

# Check provider fallbacks
grep "provider_used" backend.log
```

## 📈 Performance Targets

| Metric | Target | Acceptable | Investigate |
|--------|--------|------------|-------------|
| Personalization | < 2s | < 5s | > 5s |
| Research | < 8s | < 15s | > 15s |
| Composer | < 5s | < 10s | > 10s |
| Total Pipeline | < 15s | < 30s | > 30s |
| Quality Score | > 0.65 | > 0.50 | < 0.50 |
| Pass Rate | 100% | > 66% | < 66% |

## 🎯 Quick Troubleshooting

### No logs appearing
```bash
# Check logging initialized
grep "Cupid API Starting" backend.log
```

### Too verbose
```bash
# Set INFO level
export DEBUG=false
```

### Missing run_id
```python
# Always pass run_id
logger.info("Message", run_id)  # ✓
logger.info("Message")          # ✗
```

### Colors not showing
```bash
# Ensure terminal supports ANSI colors
# Or redirect to file without colors
python app.py 2>&1 | tee backend.log
```

## 📚 Documentation

- **Full Guide**: `LOGGING_GUIDE.md`
- **Implementation**: `LOGGING_IMPLEMENTATION_SUMMARY.md`
- **Code**: `backend/app/core/logging_config.py`

## 🎉 Quick Test

```bash
cd backend
python test_agent.py

# Expected: Colored output with all 3 agents completing
# Time: ~15-20 seconds
# Result: 3 posts generated with quality scores
```

## 💡 Pro Tips

1. **Use run_id** - Always pass it for request tracing
2. **Monitor latency** - Track trends over time
3. **Watch quality** - Alert on drops below 0.50
4. **Check providers** - Groq should be primary
5. **Review errors** - Set up alerts for ERROR logs

## 🚨 Alert Thresholds

Set up alerts for:
- ❌ Error rate > 5%
- ⚠️ Latency P95 > 30s
- ⚠️ Quality score < 0.50
- ⚠️ Pass rate < 66%
- ⚠️ Provider fallback > 10%

---

**Need help?** Check `LOGGING_GUIDE.md` for detailed examples!
