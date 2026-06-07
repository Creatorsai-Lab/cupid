"""
Local Heuristic Query Generator.

Zero-LLM fallback. Performs a lightweight string cleanup to extract the core 
topic and dynamically wraps it in 5 distinct search angles.
Keeps the pipeline alive if all AI providers fail.
"""
from __future__ import annotations

import re
from datetime import datetime

def _extract_core_topic(prompt: str) -> str:
    """Strips common instructional fluff to isolate the core subject."""
    # Remove conversational AI instructions
    cleaned = re.sub(
        r"^(please\s+)?(write|create|make|generate|compose|give me|"
        r"i want|i need|help me (with|understand)|tell me about|explain)\s+"
        r"(a |an |the )?"
        r"(post|tweet|thread|article|content|piece|something)?\s*"
        r"(about|on|for|regarding)?\s*",
        "",
        prompt.strip(),
        flags=re.IGNORECASE,
    ).strip()
    
    # Grab the first 5-6 meaningful words to avoid creating a massive query
    words = cleaned.split()
    return " ".join(words[:6]) if words else "content creation"

def generate_queries(prompt: str) -> list[str]:
    """
    Generate 5 distinct search angles deterministically.
    """
    topic = _extract_core_topic(prompt)
    year = datetime.now().year
    
    return [
        f"{topic} key statistics and data points",                 # 1. FACTS
        f"{topic} latest developments trends {year}",              # 2. RECENCY
        f"what industry experts say about {topic}",                # 3. AUTHORITY
        f"how to implement {topic} step by step guide",            # 4. PRACTICAL
        f"{topic} common failures limitations and criticism"       # 5. CONTRARIAN
    ]