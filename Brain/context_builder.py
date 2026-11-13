# ==================================================
# Brain/context_builder.py — Adaptive Context Builder
#
# UPGRADE 3: Token budget management for context injection.
# Max budget: 3000 tokens (~12,000 characters).
# Priority order:
#   1. User model (always preserved)
#   2. CoT reasoning
#   3. Episodic memory
#   4. Session history (recent turns)
#   5. RAG knowledge
# ==================================================

from __future__ import annotations

import re

MAX_CHAR_BUDGET = 12000  # ~3000 tokens (average 4 chars per token)


def build_context(
    user_model_context: str = "",
    cot_context:        str = "",
    episodic_memory:    str = "",
    session_history:    str = "",
    knowledge_context:   str = "",
    max_chars:          int = MAX_CHAR_BUDGET,
) -> str:
    """
    Builds a single clean, labeled [CONTEXT] block with priority allocation.
    Lower-priority sections get truncated first if budget is exceeded.
    """
    um   = (user_model_context or "").strip()
    cot  = (cot_context or "").strip()
    mem  = (episodic_memory or "").strip()
    hist = (session_history or "").strip()
    kn   = (knowledge_context or "").strip()

    remaining = max_chars
    sections = []

    # 1. User Model (highest priority)
    if um:
        um_alloc = min(2000, remaining)
        um_truncated = um[:um_alloc].strip()
        if um_truncated:
            sections.append(f"[USER PROFILE]\n{um_truncated}")
            remaining -= len(um_truncated)

    # 2. CoT Reasoning
    if cot and remaining > 0:
        cot_alloc = min(2500, remaining)
        cot_truncated = cot[:cot_alloc].strip()
        if cot_truncated:
            sections.append(f"[REASONING ENGINE]\n{cot_truncated}")
            remaining -= len(cot_truncated)

    # 3. Episodic Memory
    if mem and remaining > 0:
        mem_alloc = min(3000, remaining)
        mem_truncated = mem[:mem_alloc].strip()
        if mem_truncated:
            sections.append(f"[PAST EXPERIENCES]\n{mem_truncated}")
            remaining -= len(mem_truncated)

    # 4. Session History (Recent turns snapshot)
    if hist and remaining > 0:
        hist_alloc = min(3000, remaining)
        hist_truncated = hist[:hist_alloc].strip()
        if hist_truncated:
            sections.append(f"[CONVERSATION HISTORY]\n{hist_truncated}")
            remaining -= len(hist_truncated)

    # 5. RAG Knowledge (lowest priority)
    if kn and remaining > 0:
        kn_alloc = min(3000, remaining)
        kn_truncated = kn[:kn_alloc].strip()
        if kn_truncated:
            sections.append(f"[KNOWLEDGE RETRIEVAL]\n{kn_truncated}")
            remaining -= len(kn_truncated)

    if not sections:
        return ""

    return "[CONTEXT]\n" + "\n\n".join(sections)
