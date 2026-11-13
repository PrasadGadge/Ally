# ==================================================
# Brain/tiered_brain.py — 2-Tier LLM Router
#
# Tier 1  FAST      NVIDIA Nemotron-3-Super   Normal chat, Q&A, voice replies
# Tier 2  ADVANCED  OpenRouter (Gemini 2.5 Pro) Code, research, deep reasoning
#
# Setup (.env):
#   NVIDIA_API_KEY        — https://build.nvidia.com  (free tier available)
#   NVIDIA_MODEL          — nemotron-3-ultra-550b-a55b  (default)
#   OPENROUTER_API_KEY    — https://openrouter.ai
#   OPENROUTER_MODEL      — google/gemini-2.5-pro  (default, swap freely)
#
# Routing: classify_tier() picks Tier 1 or 2 based on query complexity.
# On Tier 1 failure → auto-escalates to Tier 2.
# Groq key is STT-only — not used for chat here.
# ==================================================

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from typing import Iterator, Optional

from Brain.brain_guard import (
    check_prompt_safety,
    extract_user_utterance,
    sanitize_output,
    sanitize_text,
    wrap_system_call,
)

# OpenAI exceptions — needed to catch and escalate API errors properly
try:
    from openai import APIError, APIConnectionError, Timeout as OpenAITimeout, APITimeoutError
    _ALL_CATCHABLE_EXCEPTIONS = (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, 
                                  APIError, APIConnectionError, OpenAITimeout, APITimeoutError)
except ImportError:
    _ALL_CATCHABLE_EXCEPTIONS = (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError)

# Metrics — imported lazily to avoid circular imports at module load time
def _metrics():
    try:
        import Brain.brain_metrics as _m
        return _m
    except Exception:
        return None

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ── Tier constants ────────────────────────────────────────────────────────────

TIER_FAST     = 0
TIER_LOCAL    = 0
TIER_ADVANCED = 1

# ── NVIDIA NIM config ─────────────────────────────────────────────────────────

_NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
_NVIDIA_KEY      = os.getenv("NVIDIA_API_KEY", "").strip()
_HAS_NVIDIA      = bool(_NVIDIA_KEY)

# ── OpenRouter config ─────────────────────────────────────────────────────────

_OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
_OPENROUTER_KEY      = os.getenv("OPENROUTER_API_KEY", "").strip()
_HAS_OPENROUTER      = bool(_OPENROUTER_KEY)

# ── Tier definitions ──────────────────────────────────────────────────────────

TIERS: dict[int, dict] = {
    TIER_FAST: {
        "name":      "Fast (NVIDIA Nemotron-Super)",
        "provider":  "nvidia",
        "key_env":   "NVIDIA_API_KEY",
        "base_url":  _NVIDIA_BASE_URL,
        "model":     os.getenv("NVIDIA_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
        "max_tok":   int(os.getenv("NVIDIA_MAX_TOKENS",   "700")),
        "temp":      float(os.getenv("NVIDIA_TEMPERATURE", "0.35")),
        "timeout":   float(os.getenv("NVIDIA_TIMEOUT_SEC", "25")),
    },
    TIER_ADVANCED: {
        "name":      "Advanced (OpenRouter / Gemini 2.5 Pro)",
        "provider":  "openrouter",
        "key_env":   "OPENROUTER_API_KEY",
        "base_url":  _OPENROUTER_BASE_URL,
        "model":     os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-pro"),
        "max_tok":   int(os.getenv("OPENROUTER_MAX_TOKENS",   "2000")),
        "temp":      float(os.getenv("OPENROUTER_TEMPERATURE", "0.45")),
        "timeout":   float(os.getenv("OPENROUTER_TIMEOUT_SEC", "90")),
    },
}

# ── Advanced-task signals (route to Tier 2) ───────────────────────────────────

_ADVANCED_KEYWORDS = [
    "write code", "write a function", "write a python", "write python",
    "python function", "implement", "debug", "refactor",
    "syntax error", "algorithm", "python script", "javascript", "typescript",
    "explain in detail", "step by step", "comprehensive", "deep dive",
    "research", "compare", "difference between", "pros and cons",
    "analyse", "analyze", "architecture", "optimise", "optimize",
    "multi-step", "detailed analysis", "create a plan", "roadmap",
    "strategy for", "break down", "how should i achieve",
]

_CODE_BLOCK_HINT = re.compile(r"```|\bdef\s+\w+\(|class\s+\w+")
_SENTENCE_SPLIT  = re.compile(r"(?<=[.!?])\s+")


def classify_tier(text: str) -> int:
    """
    Route to Tier 1 (fast) or Tier 2 (advanced).
    Default: fast. Escalate only when the query needs deep reasoning.
    """
    t  = text.strip()
    tl = t.lower()

    if _CODE_BLOCK_HINT.search(t):
        return TIER_ADVANCED
    if any(kw in tl for kw in _ADVANCED_KEYWORDS):
        return TIER_ADVANCED
    if len(t.split()) >= 40:
        return TIER_ADVANCED

    return TIER_FAST


def _routing_reason(user_text: str, tier: int, forced_tier: Optional[int]) -> str:
    if forced_tier is not None:
        return f"forced_tier_{forced_tier}"
    if tier == TIER_ADVANCED:
        tl = user_text.lower()
        if _CODE_BLOCK_HINT.search(user_text):
            return "code_block"
        for kw in _ADVANCED_KEYWORDS:
            if kw in tl:
                return f"keyword:{kw}"
        if len(user_text.split()) >= 40:
            return "long_message"
        return "classified_advanced"
    return "default_fast_chat"


def routing_preview(text: str) -> dict:
    """Debug helper: which tier would run and why — no API calls made."""
    tier = classify_tier(text)
    return {
        "tier":       tier,
        "tier_name":  TIERS[tier]["name"],
        "model":      TIERS[tier]["model"],
        "reason":     _routing_reason(text, tier, None),
        "escalation": "Fast (NVIDIA) → Advanced (OpenRouter) on failure",
    }


# ── Availability checks ───────────────────────────────────────────────────────

def _fast_tier_available() -> bool:
    return bool(os.getenv("NVIDIA_API_KEY", "").strip())


def _advanced_tier_available() -> bool:
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


# ── Shared sentence streamer ──────────────────────────────────────────────────

def _yield_sentences(token_iter: Iterator[str]) -> Iterator[str]:
    """Buffer raw tokens and emit complete sentence-sized chunks."""
    buffer = ""
    for tok in token_iter:
        buffer += tok
        while True:
            m = _SENTENCE_SPLIT.search(buffer)
            if not m:
                break
            yield buffer[: m.start() + 1].strip()
            buffer = buffer[m.end():]
    if buffer.strip():
        yield buffer.strip()


# ── Shared OpenAI-compatible backend ─────────────────────────────────────────

def _call_openai_compatible(
    prompt: str,
    *,
    key_env:      str,
    base_url:     str,
    model:        str,
    timeout:      float,
    temperature:  float,
    max_tokens:   int,
    provider_name: str,
    extra_headers: dict | None = None,
) -> Iterator[str]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError("pip install openai  # required for LLM calls") from exc

    key = os.getenv(key_env, "").strip()
    if not key:
        raise RuntimeError(f"{key_env} not set — add it to .env")

    kwargs: dict = {}
    if extra_headers:
        kwargs["default_headers"] = extra_headers

    client = OpenAI(api_key=key, base_url=base_url, timeout=timeout, **kwargs)
    stream = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )

    def _tokens() -> Iterator[str]:
        for chunk in stream:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    yield from _yield_sentences(_tokens())


# ── Tier-specific callers ─────────────────────────────────────────────────────

def _call_nvidia(prompt: str) -> Iterator[str]:
    cfg = TIERS[TIER_FAST]
    yield from _call_openai_compatible(
        prompt,
        key_env=cfg["key_env"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        timeout=cfg["timeout"],
        temperature=cfg["temp"],
        max_tokens=cfg["max_tok"],
        provider_name="NVIDIA NIM",
    )


def _call_openrouter(prompt: str) -> Iterator[str]:
    cfg = TIERS[TIER_ADVANCED]
    yield from _call_openai_compatible(
        prompt,
        key_env=cfg["key_env"],
        base_url=cfg["base_url"],
        model=cfg["model"],
        timeout=cfg["timeout"],
        temperature=cfg["temp"],
        max_tokens=cfg["max_tok"],
        provider_name="OpenRouter",
        # OpenRouter recommends these headers for attribution / rate-limit routing
        extra_headers={
            "HTTP-Referer": "https://vivie.local",
            "X-Title":      "Vivie",
        },
    )


def _stream_tier(tier: int, prompt: str) -> Iterator[str]:
    if tier == TIER_FAST:
        yield from _call_nvidia(prompt)
    elif tier == TIER_ADVANCED:
        yield from _call_openrouter(prompt)
    else:
        raise ValueError(f"Unknown tier {tier}")


# ── Prompt preparation ────────────────────────────────────────────────────────

def _prepare_prompt(prompt: str, *, system_internal: bool) -> str:
    safe      = sanitize_text(prompt)
    user_part = extract_user_utterance(safe)
    allowed, reason = check_prompt_safety(user_part or safe)
    if not allowed:
        raise ValueError(f"Blocked by brain firewall: {reason}")
    return wrap_system_call(safe) if system_internal else safe


# ── Public API ────────────────────────────────────────────────────────────────

def stream_response(
    prompt: str,
    forced_tier: Optional[int] = None,
    *,
    system_internal: bool = False,
) -> Iterator[str]:
    """
    Stream sentence-sized chunks from the appropriate tier.

    forced_tier: 0 = NVIDIA fast, 1 = OpenRouter advanced.
    system_internal: wraps prompt for classification/JSON tasks (stricter guard).

    Routing:
      - classify_tier() picks the tier based on query complexity.
      - Tier 1 failure → auto-escalates to Tier 2.
      - forced_tier bypasses routing and disables escalation.
    """
    if forced_tier is not None and forced_tier not in TIERS:
        raise ValueError(f"forced_tier must be 0 or 1, got {forced_tier}")

    try:
        prepared = _prepare_prompt(prompt, system_internal=system_internal)
    except ValueError as exc:
        yield str(exc)
        return

    user_text  = extract_user_utterance(prepared)
    start_tier = forced_tier if forced_tier is not None else classify_tier(user_text)
    reason     = _routing_reason(user_text, start_tier, forced_tier)

    # Guard: warn if a required key is missing and we can't serve the tier
    if start_tier == TIER_FAST and forced_tier is None and not _fast_tier_available():
        if _advanced_tier_available():
            print("[Brain] NVIDIA key missing — routing directly to Advanced tier.")
            start_tier = TIER_ADVANCED
            reason     = "nvidia_key_missing_fallback"
        else:
            yield "Boss, neither NVIDIA_API_KEY nor OPENROUTER_API_KEY is set. Add them to .env."
            return

    if start_tier == TIER_ADVANCED and not _advanced_tier_available():
        if forced_tier == TIER_ADVANCED:
            yield "Boss, OpenRouter is not configured (OPENROUTER_API_KEY is not set). Add it to .env."
            return
        if _fast_tier_available():
            print("[Brain] OpenRouter key missing — staying on Fast tier.")
            start_tier = TIER_FAST
            reason     = "openrouter_key_missing_fallback"
        else:
            yield "Boss, I need at least one API key (NVIDIA or OpenRouter) configured to respond."
            return

    print(f"[Brain] Route: {TIERS[start_tier]['name']} | reason={reason}")

    # Determine tiers to attempt (escalate on failure unless forced)
    tiers_to_try = (
        [start_tier]
        if forced_tier is not None
        else list(range(start_tier, len(TIERS)))
    )

    tried: list[str] = []
    for tier in tiers_to_try:
        cfg = TIERS[tier]
        tried.append(cfg["name"])

        # Skip tier if its key isn't configured
        if tier == TIER_FAST     and not _fast_tier_available():
            continue
        if tier == TIER_ADVANCED and not _advanced_tier_available():
            continue

        try:
            t0      = time.perf_counter()
            got_any = False
            for sentence in _stream_tier(tier, prepared):
                clean = sanitize_output(sentence)
                if not clean:
                    continue
                if not got_any:
                    ms = int((time.perf_counter() - t0) * 1000)
                    print(f"[Brain] {cfg['name']} — first token {ms}ms")
                    m = _metrics()
                    if m:
                        m.record_tier_call(tier, success=True, first_token_ms=ms)
                    got_any = True
                yield clean
            if got_any:
                return
        except _ALL_CATCHABLE_EXCEPTIONS as exc:
            print(f"[Brain] {cfg['name']} failed (network): {exc}")
            m = _metrics()
            if m:
                m.record_tier_call(tier, success=False)
            if forced_tier is None and tier < len(TIERS) - 1:
                print(f"[Brain] Escalating → {TIERS[tier + 1]['name']}")
                m2 = _metrics()
                if m2:
                    m2.record_escalation()
            continue
        except Exception as exc:
            print(f"[Brain] {cfg['name']} error: {exc}")
            m = _metrics()
            if m:
                m.record_tier_call(tier, success=False)
            if forced_tier is None and tier < len(TIERS) - 1:
                print(f"[Brain] Escalating → {TIERS[tier + 1]['name']}")
                m2 = _metrics()
                if m2:
                    m2.record_escalation()
            continue

    print(f"[Brain] All tiers failed. Tried: {tried}")
    # Use warm, intent-matched offline message instead of cold error
    try:
        from Brain.prompt_core import OFFLINE_FALLBACKS
        intent = "general"
        try:
            from Brain.cl_brain import detect_intent
            intent = detect_intent(extract_user_utterance(prepared) or prepared)
        except Exception:
            pass
        yield OFFLINE_FALLBACKS.get(intent, OFFLINE_FALLBACKS["general"])
    except Exception:
        yield OFFLINE_FALLBACKS.get("general", "Boss, I need a moment — my reasoning systems are briefly offline. Try again shortly.")



def api_generate_response(
    prompt: str,
    forced_tier: Optional[int] = None,
    *,
    system_internal: bool = False,
) -> str:
    """Blocking (non-streaming) wrapper around stream_response."""
    try:
        parts = list(
            stream_response(prompt, forced_tier=forced_tier, system_internal=system_internal)
        )
        return sanitize_output(" ".join(parts).strip())
    except Exception as exc:
        print(f"[Brain] Blocking call error: {exc}")
        return "I am unable to process that right now."


# Backward-compatible alias kept for any callers using the old name
classify_complexity = classify_tier