import os
import re
from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
from langchain_core.messages import HumanMessage, SystemMessage

# ── config ────────────────────────────────────────────────────
os.environ["HUGGINGFACEHUB_API_TOKEN"] = "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"

hf_model = "Qwen/Qwen3-8B"

influencer_type = "tech and ai researcher"
platform        = "linkedin"
post_length     = "short"

# ── load research report ──────────────────────────────────────
with open("cupid_research_report.md", "r", encoding="utf-8") as f:
    research_report = f.read()

# ── build system prompt ───────────────────────────────────────
system_prompt = f"""You are a genz social media content creation agent.

You behave as an insightful, and engaging {influencer_type} influencer on {platform}.
Your writing style is platform-native, you use alot social media slang, optimized for {platform} engagement, tone, and write in simple text.
Your posts consistently earn high likes, comments, and shares because they are clear, active passage, natural, and human like.

Your task:
- Read the research report carefully provided below.
- Extract the most interesting, relevant piece of information from it.
- Write a {post_length} {platform} post based on that insight.
- Do NOT fabricate any facts. Only use information present in the report.
- Match the tone and format that performs best on {platform}.

--- RESEARCH REPORT START ---
{research_report}
--- RESEARCH REPORT END ---
"""

# ── build messages ────────────────────────────────────────────
messages = [SystemMessage(content=system_prompt)]

# ── run model ─────────────────────────────────────────────────
llm = HuggingFaceEndpoint(
    repo_id=hf_model,
    task="text-generation",
    max_new_tokens=3000,
    temperature=0.7,
)

chat_model = ChatHuggingFace(llm=llm)
response = chat_model.invoke(messages)
raw = response.content

# ── parse think vs final post ─────────────────────────────────
think_match = re.search(r"<think>(.*?)</think>", raw, re.DOTALL)
think_text  = think_match.group(1).strip() if think_match else "(no thinking block)"
main_response  = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

print("\n" + "=" * 60)
print("📝  FINAL POST")
print("=" * 60)
print(main_response)