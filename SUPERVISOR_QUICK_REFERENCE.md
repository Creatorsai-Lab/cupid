# Supervisor Agent - Quick Reference

## 🚀 Quick Start

```bash
# Test the supervisor
cd backend
python test_supervisor.py

# Start backend
uvicorn app.main:app --reload

# Test via API (will be rejected - too short)
curl -X POST http://localhost:8000/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"prompt": "AI trends", "platform": "Web"}'
```

## 📊 Pipeline Flow

```
User Input
    ↓
🟡 SUPERVISOR (NEW!)
    ├─ ✓ Approved → Personalization
    └─ ✗ Rejected → Return Error
```

## ✅ Validation Rules

| Rule | Requirement | Example ❌ | Example ✅ |
|------|-------------|-----------|-----------|
| **Length** | Min 4 words | "AI trends" | "AI trends in 2026" |
| **Violence** | No violent content | "How to make weapons" | "Violence prevention tips" |
| **Sexual** | No adult content | "Adult content tips" | "Sexual health education" |
| **Hate** | No discrimination | "Racist jokes" | "Anti-racism campaign" |
| **Spam** | No promotional spam | "CLICK HERE NOW!!!" | "Marketing strategies" |

## 🎨 Log Colors

| Color | Agent |
|-------|-------|
| 🟡 Yellow | Supervisor |
| 🔵 Blue | Personalization |
| 🟢 Green | Research |
| 🟣 Magenta | Composer |

## 📝 Error Messages

### Too Short
```
Your prompt is too short (2 words). Please provide at least 4 words 
to help us understand what you want to create. 
Example: 'AI trends in healthcare 2026'
```

### Violence
```
Your prompt contains content related to violence which we cannot process. 
Please rephrase your request to focus on constructive, educational, or 
awareness topics.
```

### Sexual Content
```
Your prompt contains adult or sexual content which we cannot process. 
Please rephrase your request.
```

### Hate Speech
```
Your prompt contains language that may be offensive or discriminatory. 
Please rephrase your request to be respectful and inclusive.
```

### Spam
```
Your prompt appears to contain promotional or spam content. 
Please focus on creating genuine, valuable content.
```

## 🧪 Test Cases

```python
# Valid prompts (will pass)
✅ "AI trends in healthcare 2026"
✅ "Latest quantum computing developments"
✅ "Climate change solutions for cities"
✅ "Remote work productivity tips"

# Invalid prompts (will be rejected)
❌ "AI trends" (too short)
❌ "How to make weapons" (violence)
❌ "Adult content tips" (sexual)
❌ "CLICK HERE NOW!!!" (spam)
```

## 🔧 Quick Customization

### Change Minimum Words
```python
# In supervisor/agent.py, line ~100
if word_count < 6:  # Change from 4 to 6
```

### Add Keywords
```python
# In supervisor/agent.py, top of file
VIOLENCE_KEYWORDS.add("your_keyword")
SEXUAL_KEYWORDS.add("your_keyword")
```

## 📊 What Gets Logged

### Approved
```
🟡 SUPERVISOR AGENT START
  ✓ Length validation passed
  ✓ Content moderation passed
  ✓ Spam detection passed
✅ SUPERVISOR AGENT COMPLETE (status: approved)
```

### Rejected
```
🟡 SUPERVISOR AGENT START
  ⚠️  Validation failed: Too short
✅ SUPERVISOR AGENT COMPLETE (status: rejected)
```

## 📁 Files

### Created
- `backend/app/agents/supervisor/agent.py` - Main logic
- `backend/test_supervisor.py` - Test suite
- `SUPERVISOR_AGENT_GUIDE.md` - Full guide

### Modified
- `backend/app/agents/graph.py` - Added to pipeline
- `backend/app/core/logging_config.py` - Added color

## 🎯 Benefits

- ✅ Blocks inappropriate content
- ✅ Ensures quality inputs
- ✅ Saves API costs
- ✅ Clear error messages
- ✅ Fast validation (< 1ms)

## 📚 Full Documentation

See `SUPERVISOR_AGENT_GUIDE.md` for complete details.

---

**Quick Test**: `python backend/test_supervisor.py` 🚀
