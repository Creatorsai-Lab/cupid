"""
Supervisor Agent — Input validation and content moderation.

Validates user prompts before passing to the personalization agent:
1. Length validation (minimum 4 words)
2. Content moderation (violence, sexual content, hate speech)
3. Language detection (optional)
4. Spam detection (optional)

This is the first agent in the pipeline and acts as a gatekeeper.
"""
from __future__ import annotations

import re
from typing import Any

from app.agents.state import MemoryState
from app.core.logging_config import get_agent_logger

logger = get_agent_logger("supervisor")

# ═══════════════════════════════════════════════════════════════════════════════
# Content Moderation Rules
# ═══════════════════════════════════════════════════════════════════════════════

# Violent content keywords
VIOLENCE_KEYWORDS = {
    "kill", "murder", "assault", "attack", "weapon", "gun", "knife", "bomb",
    "terrorist", "violence", "violent", "shoot", "shooting", "stab", "stabbing",
    "torture", "abuse", "harm", "hurt", "injure", "death", "die", "suicide",
    "homicide", "massacre", "slaughter", "genocide", "war crime", "execution",
}

# Sexual content keywords
SEXUAL_KEYWORDS = {
    "sex", "sexual", "porn", "pornography", "nude", "naked", "explicit",
    "nsfw", "adult content", "erotic", "xxx", "intercourse", "prostitution",
    "escort", "hookup", "dating app", "onlyfans", "strip", "stripper",
}

# Hate speech keywords
HATE_KEYWORDS = {
    "hate", "racist", "racism", "nazi", "fascist", "supremacist", "bigot",
    "discrimination", "slur", "offensive", "derogatory", "prejudice",
}

# Spam indicators
SPAM_PATTERNS = [
    r"(?i)click here",
    r"(?i)buy now",
    r"(?i)limited time",
    r"(?i)act now",
    r"(?i)free money",
    r"(?i)get rich",
    r"(?i)work from home",
    r"(?i)make \$\d+",
    r"(?i)guaranteed",
    r"http[s]?://bit\.ly",  # Shortened URLs often spam
    r"http[s]?://tinyurl",
]

# Allowed exceptions (context matters)
ALLOWED_CONTEXTS = {
    "violence": {
        "violence prevention", "anti-violence", "stop violence", "violence awareness",
        "domestic violence support", "violence statistics", "violence research",
    },
    "sexual": {
        "sexual health", "sexual education", "sexual harassment prevention",
        "sexual assault awareness", "sexual wellness", "sex education",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Validation Functions
# ═══════════════════════════════════════════════════════════════════════════════

def validate_length(prompt: str) -> tuple[bool, str | None]:
    """
    Validate prompt has minimum 4 words.
    
    Returns:
        (is_valid, error_message)
    """
    words = prompt.strip().split()
    word_count = len(words)
    
    if word_count < 4:
        return False, (
            f"Your prompt is too short ({word_count} word{'s' if word_count != 1 else ''}). "
            f"Please provide at least 4 words to help us understand what you want to create. "
            f"Example: 'AI trends in healthcare 2026'"
        )
    
    return True, None


def check_violence(prompt: str) -> tuple[bool, str | None]:
    """
    Check for violent content.
    
    Returns:
        (is_safe, error_message)
    """
    prompt_lower = prompt.lower()
    
    # Check for allowed contexts first
    for context in ALLOWED_CONTEXTS["violence"]:
        if context in prompt_lower:
            return True, None
    
    # Check for violence keywords
    found_keywords = []
    for keyword in VIOLENCE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", prompt_lower):
            found_keywords.append(keyword)
    
    if found_keywords:
        return False, (
            "Your prompt contains content related to violence which we cannot process. "
            "Please rephrase your request to focus on constructive, educational, or awareness topics. "
            "If you're discussing violence prevention or awareness, please make that context clear."
        )
    
    return True, None


def check_sexual_content(prompt: str) -> tuple[bool, str | None]:
    """
    Check for sexual content.
    
    Returns:
        (is_safe, error_message)
    """
    prompt_lower = prompt.lower()
    
    # Check for allowed contexts first
    for context in ALLOWED_CONTEXTS["sexual"]:
        if context in prompt_lower:
            return True, None
    
    # Check for sexual keywords
    found_keywords = []
    for keyword in SEXUAL_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", prompt_lower):
            found_keywords.append(keyword)
    
    if found_keywords:
        return False, (
            "Your prompt contains adult or sexual content which we cannot process. "
            "Please rephrase your request. If you're discussing health, education, or awareness topics, "
            "please make that context clear (e.g., 'sexual health education')."
        )
    
    return True, None


def check_hate_speech(prompt: str) -> tuple[bool, str | None]:
    """
    Check for hate speech.
    
    Returns:
        (is_safe, error_message)
    """
    prompt_lower = prompt.lower()
    
    # Check for hate speech keywords
    found_keywords = []
    for keyword in HATE_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", prompt_lower):
            found_keywords.append(keyword)
    
    if found_keywords:
        return False, (
            "Your prompt contains language that may be offensive or discriminatory. "
            "Please rephrase your request to be respectful and inclusive. "
            "We're here to help create positive, constructive content."
        )
    
    return True, None


def check_spam(prompt: str) -> tuple[bool, str | None]:
    """
    Check for spam patterns.
    
    Returns:
        (is_safe, error_message)
    """
    # Check for spam patterns
    for pattern in SPAM_PATTERNS:
        if re.search(pattern, prompt):
            return False, (
                "Your prompt appears to contain promotional or spam content. "
                "Please focus on creating genuine, valuable content for your audience."
            )
    
    # Check for excessive capitalization (>50% caps)
    if len(prompt) > 10:
        caps_ratio = sum(1 for c in prompt if c.isupper()) / len(prompt)
        if caps_ratio > 0.5:
            return False, (
                "Your prompt contains excessive capitalization. "
                "Please write in a normal, conversational style."
            )
    
    # Check for excessive punctuation
    punct_count = sum(1 for c in prompt if c in "!?")
    if punct_count > 5:
        return False, (
            "Your prompt contains excessive punctuation. "
            "Please write in a clear, professional style."
        )
    
    return True, None


def validate_prompt(prompt: str) -> tuple[bool, str | None]:
    """
    Run all validation checks on the prompt.
    
    Returns:
        (is_valid, error_message)
    """
    # 1. Length validation
    is_valid, error = validate_length(prompt)
    if not is_valid:
        return False, error
    
    # 2. Violence check
    is_safe, error = check_violence(prompt)
    if not is_safe:
        return False, error
    
    # 3. Sexual content check
    is_safe, error = check_sexual_content(prompt)
    if not is_safe:
        return False, error
    
    # 4. Hate speech check
    is_safe, error = check_hate_speech(prompt)
    if not is_safe:
        return False, error
    
    # 5. Spam check
    is_safe, error = check_spam(prompt)
    if not is_safe:
        return False, error
    
    return True, None


# ═══════════════════════════════════════════════════════════════════════════════
# LangGraph Node
# ═══════════════════════════════════════════════════════════════════════════════

async def supervisor_node(state: MemoryState) -> dict[str, Any]:
    """
    Validate user input before passing to personalization agent.
    
    Reads:  user_prompt
    Writes: error (if validation fails), agents_completed
    """
    run_id = state.get("run_id", "unknown")
    prompt = (state.get("user_prompt") or "").strip()
    completed = state.get("agents_completed", [])
    
    # Log agent start
    logger.agent_start(
        run_id,
        user_prompt=prompt[:100] + "..." if len(prompt) > 100 else prompt,
        prompt_length=f"{len(prompt)} chars, {len(prompt.split())} words",
    )
    
    # Validate prompt
    logger.log_step(run_id, "Validating prompt", "Running content moderation checks")
    is_valid, error_message = validate_prompt(prompt)
    
    if not is_valid:
        logger.warning(f"Validation failed: {error_message}", run_id)
        logger.agent_complete(
            run_id,
            status="rejected",
            reason=error_message[:100],
        )
        
        return {
            "error": error_message,
            "status": "failed",
            "current_agent": "supervisor",
            "agents_completed": [*completed, "supervisor"],
        }
    
    # Validation passed
    logger.info("✓ Length validation passed", run_id)
    logger.info("✓ Content moderation passed", run_id)
    logger.info("✓ Spam detection passed", run_id)
    
    logger.agent_complete(
        run_id,
        status="approved",
        prompt_words=len(prompt.split()),
    )
    
    return {
        "current_agent": "supervisor",
        "agents_completed": [*completed, "supervisor"],
    }
