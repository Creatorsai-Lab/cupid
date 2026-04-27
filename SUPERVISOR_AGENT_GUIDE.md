# Supervisor Agent - Input Validation & Content Moderation

## 🎯 Overview

The Supervisor Agent is the **first agent** in the Cupid pipeline, acting as a gatekeeper that validates user input before passing it to the personalization agent. This ensures quality, safety, and compliance with content policies.

## 🏗️ Architecture

### Pipeline Flow

```
User Input
    ↓
🟡 SUPERVISOR AGENT (NEW!)
    ├─ ✓ Approved → Continue to Personalization
    └─ ✗ Rejected → Return error to user
         ↓
🔵 Personalization Agent
    ↓
🟢 Research Agent
    ↓
🟣 Composer Agent
    ↓
Output
```

### Conditional Routing

The supervisor uses **LangGraph conditional edges** to route based on validation:

```python
workflow.add_conditional_edges(
    "supervisor",
    lambda state: "approved" if not state.get("error") else "rejected",
    {
        "approved": "personalization",  # Continue pipeline
        "rejected": END,                 # Stop and return error
    }
)
```

## ✅ Validation Checks

### 1. Length Validation
**Rule**: Minimum 4 words

**Why**: Short prompts lack context and produce poor results.

**Examples**:
- ❌ "AI trends" (2 words)
- ❌ "Write about tech" (3 words)
- ✅ "AI trends in healthcare 2026" (5 words)
- ✅ "Latest developments in quantum computing" (5 words)

**Error Message**:
```
Your prompt is too short (2 words). Please provide at least 4 words 
to help us understand what you want to create. 
Example: 'AI trends in healthcare 2026'
```

---

### 2. Violence Detection
**Rule**: Block content promoting violence

**Keywords Detected**:
- kill, murder, assault, attack, weapon, gun, knife, bomb
- terrorist, violence, shoot, stab, torture, abuse, harm
- death, suicide, homicide, massacre, slaughter, genocide

**Allowed Contexts** (educational/awareness):
- "violence prevention"
- "anti-violence campaign"
- "stop violence"
- "violence awareness"
- "domestic violence support"
- "violence statistics"
- "violence research"

**Examples**:
- ❌ "How to make a bomb"
- ❌ "Best weapons for self-defense"
- ✅ "Violence prevention strategies in schools"
- ✅ "Domestic violence awareness campaign ideas"

**Error Message**:
```
Your prompt contains content related to violence which we cannot process. 
Please rephrase your request to focus on constructive, educational, or 
awareness topics. If you're discussing violence prevention or awareness, 
please make that context clear.
```

---

### 3. Sexual Content Detection
**Rule**: Block adult/sexual content

**Keywords Detected**:
- sex, sexual, porn, pornography, nude, naked, explicit
- nsfw, adult content, erotic, xxx, intercourse
- prostitution, escort, hookup, onlyfans, strip

**Allowed Contexts** (health/education):
- "sexual health"
- "sexual education"
- "sexual harassment prevention"
- "sexual assault awareness"
- "sexual wellness"
- "sex education"

**Examples**:
- ❌ "Adult content creation tips"
- ❌ "How to start an OnlyFans"
- ✅ "Sexual health education for teens"
- ✅ "Sexual harassment prevention in workplace"

**Error Message**:
```
Your prompt contains adult or sexual content which we cannot process. 
Please rephrase your request. If you're discussing health, education, 
or awareness topics, please make that context clear 
(e.g., 'sexual health education').
```

---

### 4. Hate Speech Detection
**Rule**: Block discriminatory or offensive content

**Keywords Detected**:
- hate, racist, racism, nazi, fascist, supremacist
- bigot, discrimination, slur, offensive, derogatory, prejudice

**Examples**:
- ❌ "Why [group] are inferior"
- ❌ "Racist jokes compilation"
- ✅ "Anti-racism campaign ideas"
- ✅ "Combating discrimination in hiring"

**Error Message**:
```
Your prompt contains language that may be offensive or discriminatory. 
Please rephrase your request to be respectful and inclusive. 
We're here to help create positive, constructive content.
```

---

### 5. Spam Detection
**Rule**: Block promotional spam and low-quality content

**Patterns Detected**:
- "click here", "buy now", "limited time", "act now"
- "free money", "get rich", "work from home"
- "make $XXX", "guaranteed"
- Shortened URLs (bit.ly, tinyurl)
- Excessive capitalization (>50% caps)
- Excessive punctuation (>5 !?)

**Examples**:
- ❌ "CLICK HERE NOW!!! LIMITED TIME OFFER!!!"
- ❌ "Make $10,000 working from home guaranteed"
- ✅ "Remote work productivity tips"
- ✅ "Effective marketing strategies for startups"

**Error Message**:
```
Your prompt appears to contain promotional or spam content. 
Please focus on creating genuine, valuable content for your audience.
```

---

## 📊 Validation Flow

```python
def validate_prompt(prompt: str) -> tuple[bool, str | None]:
    """Run all validation checks."""
    
    # 1. Length validation (4+ words)
    if len(prompt.split()) < 4:
        return False, "Too short..."
    
    # 2. Violence check
    if contains_violence(prompt):
        return False, "Violence detected..."
    
    # 3. Sexual content check
    if contains_sexual_content(prompt):
        return False, "Sexual content detected..."
    
    # 4. Hate speech check
    if contains_hate_speech(prompt):
        return False, "Hate speech detected..."
    
    # 5. Spam check
    if is_spam(prompt):
        return False, "Spam detected..."
    
    return True, None  # All checks passed
```

## 🎨 Log Output

### Approved Prompt
```
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) 🚀 SUPERVISOR AGENT START
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   user_prompt: AI trends in healthcare 2026
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   prompt_length: 28 chars, 5 words
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ⚙️  STEP: Validating prompt - Running content moderation checks
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ✓ Length validation passed
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ✓ Content moderation passed
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ✓ Spam detection passed
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ✅ SUPERVISOR AGENT COMPLETE
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   status: approved
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   prompt_words: 5
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================

[Pipeline continues to Personalization Agent...]
```

### Rejected Prompt (Too Short)
```
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) 🚀 SUPERVISOR AGENT START
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   user_prompt: AI trends
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   prompt_length: 9 chars, 2 words
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ⚙️  STEP: Validating prompt - Running content moderation checks
2026-04-27 12:00:15 WARNING [supervisor] (run:abc12345) Validation failed: Your prompt is too short (2 words)...
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ✅ SUPERVISOR AGENT COMPLETE
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   status: rejected
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   reason: Your prompt is too short (2 words). Please provide at least 4 words...
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================

[Pipeline stops, error returned to user]
```

### Rejected Prompt (Violence)
```
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) 🚀 SUPERVISOR AGENT START
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   user_prompt: How to make weapons at home
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   prompt_length: 28 chars, 6 words
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ⚙️  STEP: Validating prompt - Running content moderation checks
2026-04-27 12:00:15 WARNING [supervisor] (run:abc12345) Validation failed: Your prompt contains content related to violence...
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ✅ SUPERVISOR AGENT COMPLETE
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   status: rejected
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345)   reason: Your prompt contains content related to violence which we cannot process...
2026-04-27 12:00:15 INFO [supervisor] (run:abc12345) ======================================================================

[Pipeline stops, error returned to user]
```

## 🧪 Testing

### Test Valid Prompts
```bash
cd backend
python -c "
from app.agents.supervisor.agent import validate_prompt

# Test valid prompts
prompts = [
    'AI trends in healthcare 2026',
    'Latest developments in quantum computing',
    'Climate change solutions for cities',
    'Remote work productivity tips',
]

for prompt in prompts:
    is_valid, error = validate_prompt(prompt)
    print(f'✓ {prompt}: {is_valid}')
"
```

### Test Invalid Prompts
```bash
cd backend
python -c "
from app.agents.supervisor.agent import validate_prompt

# Test invalid prompts
prompts = [
    'AI trends',  # Too short
    'How to make weapons',  # Violence
    'Adult content tips',  # Sexual
    'CLICK HERE NOW!!!',  # Spam
]

for prompt in prompts:
    is_valid, error = validate_prompt(prompt)
    print(f'✗ {prompt}')
    print(f'  Error: {error}')
    print()
"
```

### Test via API
```bash
# Test rejected prompt (too short)
curl -X POST http://localhost:8000/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "prompt": "AI trends",
    "platform": "Web",
    "tone": "Casual"
  }'

# Expected response:
{
  "run_id": "abc-123",
  "status": "failed",
  "error": "Your prompt is too short (2 words). Please provide at least 4 words..."
}

# Test approved prompt
curl -X POST http://localhost:8000/api/v1/agents/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "prompt": "AI trends in healthcare 2026",
    "platform": "Web",
    "tone": "Casual"
  }'

# Expected: Pipeline runs successfully
```

## 📁 Files Created

- ✅ `backend/app/agents/supervisor/__init__.py` - Module init
- ✅ `backend/app/agents/supervisor/agent.py` - Supervisor agent logic (300+ lines)

## 📁 Files Modified

- ✅ `backend/app/agents/graph.py` - Added supervisor to pipeline
- ✅ `backend/app/core/logging_config.py` - Added supervisor color

## 🎯 Benefits

### For Users
- ✅ Clear, helpful error messages
- ✅ Guidance on how to fix issues
- ✅ Fast feedback (no wasted API calls)

### For Platform
- ✅ Content moderation compliance
- ✅ Reduced abuse and spam
- ✅ Better quality inputs → better outputs
- ✅ Cost savings (reject bad prompts early)

### For Developers
- ✅ Centralized validation logic
- ✅ Easy to extend with new rules
- ✅ Full logging and monitoring
- ✅ Testable validation functions

## 🔧 Customization

### Add New Keywords
```python
# In supervisor/agent.py

# Add to violence keywords
VIOLENCE_KEYWORDS.add("your_keyword")

# Add to sexual keywords
SEXUAL_KEYWORDS.add("your_keyword")

# Add to hate keywords
HATE_KEYWORDS.add("your_keyword")
```

### Add New Validation Rule
```python
def check_custom_rule(prompt: str) -> tuple[bool, str | None]:
    """Your custom validation logic."""
    if some_condition:
        return False, "Your error message"
    return True, None

# Add to validate_prompt()
def validate_prompt(prompt: str) -> tuple[bool, str | None]:
    # ... existing checks ...
    
    # Your new check
    is_valid, error = check_custom_rule(prompt)
    if not is_valid:
        return False, error
    
    return True, None
```

### Adjust Minimum Words
```python
# In supervisor/agent.py
def validate_length(prompt: str) -> tuple[bool, str | None]:
    words = prompt.strip().split()
    word_count = len(words)
    
    # Change from 4 to your desired minimum
    if word_count < 6:  # Now requires 6 words
        return False, f"Your prompt is too short ({word_count} words)..."
```

## 🚨 Error Handling

### Frontend Display
The error message is returned in the API response:

```typescript
// Frontend handling
try {
  const res = await agentsApi.generate({ prompt, ... });
  setRunId(res.run_id);
} catch (error) {
  // Display error.message to user
  setError(error.message);
}
```

### User Experience
```
┌─────────────────────────────────────────────────┐
│ ⚠️  Your prompt is too short (2 words).        │
│                                                  │
│ Please provide at least 4 words to help us     │
│ understand what you want to create.             │
│                                                  │
│ Example: 'AI trends in healthcare 2026'        │
└─────────────────────────────────────────────────┘
```

## 📊 Metrics to Monitor

Track these metrics in production:

- **Rejection Rate**: % of prompts rejected
- **Rejection Reasons**: Distribution by validation type
- **Average Prompt Length**: Words per prompt
- **False Positives**: Valid prompts incorrectly rejected
- **False Negatives**: Invalid prompts that passed

## 🎉 Summary

The Supervisor Agent provides:

1. ✅ **Input Validation** - Minimum 4 words
2. ✅ **Content Moderation** - Violence, sexual, hate speech
3. ✅ **Spam Detection** - Promotional content, excessive caps/punctuation
4. ✅ **Clear Error Messages** - Helpful guidance for users
5. ✅ **Conditional Routing** - Stop pipeline early if rejected
6. ✅ **Full Logging** - Complete audit trail
7. ✅ **Easy to Extend** - Add new rules easily

Your Cupid system now has enterprise-grade input validation! 🚀
