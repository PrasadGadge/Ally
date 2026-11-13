# ==========================================
# Brain/system_llm.py — Isolated System LLM
#
# Used internally for intent JSON, planning hints, classification.
# No personality. No chat history.
#
# TIER_FAST (0) for cheap yes/no routing — free and fast.
# TIER_ADVANCED (1) for reliable structured output.
# ==========================================

from Brain.tiered_brain import TIER_FAST, TIER_ADVANCED, api_generate_response


def system_llm(prompt: str, tier: int = TIER_FAST) -> str:
    """
    Pure LLM call for internal system use.

    Args:
        prompt: Instruction prompt (not end-user chat).
        tier:   TIER_FAST (0) = NVIDIA/fast, cheap; TIER_ADVANCED (1) = OpenRouter, reliable.

    Returns:
        Stripped response text, or "" on failure.
    """
    if tier not in (TIER_FAST, TIER_ADVANCED):
        tier = TIER_FAST
    try:
        response = api_generate_response(
            prompt,
            forced_tier=tier,
            system_internal=True,
        )
        return response.strip() if response else ""
    except Exception as exc:
        print(f"[System LLM Error]: {exc}")
        return ""