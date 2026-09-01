"""Lists the model IDs actually available on providers like Groq and NVIDIA accounts
right now, straight from each provider's own /v1/models endpoint -- then
actually invokes your configured model with a real structured-output call,
because listing and invoking are not the same guarantee. NVIDIA's hosted
API in particular has a well-documented gap where /v1/models lists a model
correctly but /v1/chat/completions 404s with "Function ... not found for
account" -- a personal/new account missing the "Public API Endpoints"
permission, not a model problem. This script surfaces that distinction
immediately instead of making you debug it through the full pipeline.

Run this whenever you hit a "model does not exist" / NotFoundError, or
before setting GROQ_MODEL / NVIDIA_LLM_MODEL in .env at all -- both
providers' catalogs change and deprecate on their own schedule, so no
hardcoded name (including the defaults in config.py, or anything a search
engine or another AI tells you) should be trusted over this.

Usage: python check_providers.py
"""

from __future__ import annotations

import asyncio

from ..clients import _groq_client, _nvidia_client
from ..config import settings


async def _list(label: str, client, configured_key: str) -> None:
    print(f"\n--- {label}: /v1/models ---")
    if not configured_key:
        print("  no API key set in .env -- skipping")
        return
    try:
        response = await client.models.list()
        ids = sorted(m.id for m in response.data)
    except Exception as exc:
        print(f"  FAILED: {type(exc).__name__}: {exc}")
        return
    print(f"  {len(ids)} model(s) listed:")
    for model_id in ids:
        print(f"    {model_id}")


async def _smoke_test(label: str, client, model: str, configured_key: str) -> None:
    print(f"\n--- {label}: can it actually invoke '{model}'? ---")
    if not configured_key:
        print("  no API key set -- skipping")
        return
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK."}],
            timeout=20,
        )
        print(f"  OK -- responded: {response.choices[0].message.content!r}")
    except Exception as exc:
        print(f"  FAILED: {type(exc).__name__}: {exc}")
        if "not found for account" in str(exc).lower():
            print(
                "  This specific message is a known NVIDIA account-permission gap, not a bad "
                "model name -- /v1/models lists the model but this account's org is missing "
                "the 'Public API Endpoints' permission. Confirmed on NVIDIA's own developer "
                "forums (Access/Accounts category) across many accounts, including ones created "
                "recently. Fix: post there requesting it be enabled for your account/org -- "
                "this is not something changing the model name will resolve."
            )


async def main() -> None:
    await _list("Groq", _groq_client, settings.groq_api_key)
    await _list("NVIDIA NIM", _nvidia_client, settings.nvidia_api_key)

    print(
        "\nCurrently configured in .env:\n"
        f"  GROQ_MODEL       = {settings.groq_model}\n"
        f"  NVIDIA_LLM_MODEL = {settings.nvidia_llm_model}\n"
        "Cross-check these against the lists above -- fix .env if either is missing.\n"
        "Now actually invoking each configured model (listing =/= working):"
    )
    await _smoke_test("Groq", _groq_client, settings.groq_model, settings.groq_api_key)
    await _smoke_test(
        "NVIDIA NIM", _nvidia_client, settings.nvidia_llm_model, settings.nvidia_api_key
    )


if __name__ == "__main__":
    asyncio.run(main())
