# ==================================================
# Brain/response_verifier.py  —  Response Quality Gate
#
# After Main_Brain() returns, runs a fast Tier 0 check:
#   • Did this actually answer the question?
#   • Any hallucination signals ("I think", "maybe")?
#   • Is Vivie admitting ignorance when she shouldn't?
#
# If quality < threshold → should_escalate = True
# ==================================================
# Brain/response_verifier.py  —  Response Quality Gate
#
# After Main_Brain() returns, runs a fast Tier 0 check:
#   • Did this actually answer the question?
#   • Any hallucination signals ("I think", "maybe")?
#   • Is Vivie admitting ignorance when she shouldn't?
#
# If quality < threshold → should_escalate = True
# Caller (fallback.py) retries with Tier 1.
#
# Cache: same (question, answer) pair is never re-checked.
# Only runs on fallback path — not tools, not automation.
# ==================================================

from __future__ import annotations

import hashlib
import time
import threading
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Dict, Tuple

from Brain.tiered_brain import api_generate_response

# Metrics — lazy import to avoid circular dependency
def _metrics():
    try:
        import Brain.brain_metrics as _m
        return _m
    except Exception:
        return None



# ─────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────

ESCALATE_THRESHOLD   = 5    # score < this → escalate to Tier 1
CACHE_MAX_SIZE       = 128  # max cached verification results
VERIFY_TIMEOUT_S     = 4.0  # max seconds for verification call


# ─────────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────────

@dataclass
class VerifyResult:
    score:            int   = 8      # 1-10
    should_escalate:  bool  = False
    reason:           str   = ""
    from_cache:       bool  = False
    latency_ms:       float = 0.0


# ─────────────────────────────────────────────────
# CACHE
# ─────────────────────────────────────────────────

_cache: Dict[str, VerifyResult] = {}


def _cache_key(question: str, answer: str) -> str:
    sig = f"{question[:150]}||{answer[:150]}"
    return hashlib.md5(sig.encode()).hexdigest()


def _get_cached(question: str, answer: str) -> VerifyResult | None:
    key = _cache_key(question, answer)
    return _cache.get(key)


def _set_cached(question: str, answer: str, result: VerifyResult):
    if len(_cache) >= CACHE_MAX_SIZE:
        # Evict oldest half
        keys = list(_cache.keys())
        for k in keys[: CACHE_MAX_SIZE // 2]:
            del _cache[k]
    key = _cache_key(question, answer)
    _cache[key] = result


# ─────────────────────────────────────────────────
# FAST CHECKS (no LLM needed)
# ─────────────────────────────────────────────────

_UNCERTAINTY_PHRASES = [
    "i'm not sure", "i am not sure", "i don't know",
    "i do not know", "i cannot", "i can't",
    "i have no information", "i'm unable", "i am unable",
    "not in my knowledge", "beyond my knowledge",
    "i don't have access", "no data available",
]

_DEFLECTION_PHRASES = [
    "you should consult", "please consult", "see a professional",
    "i recommend asking", "contact a specialist",
]


def _fast_check(question: str, answer: str) -> Tuple[int, str] | None:
    """
    Returns (score, reason) if fast rules apply, else None for LLM check.
    """
    a = answer.lower()

    # Very short answers for non-trivial questions
    if len(question.split()) > 4 and len(answer.split()) < 8:
        return 4, "Response too brief for a complex question"

    # Explicit uncertainty
    for phrase in _UNCERTAINTY_PHRASES:
        if phrase in a:
            return 3, f"Response expresses uncertainty: '{phrase}'"

    # Pure deflection
    for phrase in _DEFLECTION_PHRASES:
        if phrase in a:
            return 4, "Response deflects without answering"

    # Empty or near-empty
    if not answer.strip() or len(answer.strip()) < 10:
        return 1, "Empty or near-empty response"

    return None


# ─────────────────────────────────────────────────
# LLM VERIFIER PROMPT
# ─────────────────────────────────────────────────

_VERIFY_PROMPT = """Rate this AI response on a scale of 1 to 10.

Question: {question}
Response: {answer}

Scoring guide:
10 = Perfect, complete, accurate, directly addresses the question
7-9 = Good, mostly addresses question, minor gaps
5-6 = Partially answers, some gaps or vague areas
3-4 = Poor, mostly misses the question or very incomplete
1-2 = Wrong, empty, or completely off-topic

Reply with ONLY a single integer (1-10). Nothing else."""


# ─────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────

def _generate_score_with_timeout(prompt: str, timeout_s: float) -> str:
    result_q: Queue = Queue(maxsize=1)

    def worker():
        try:
            result_q.put((api_generate_response(prompt, forced_tier=0), None))
        except Exception as exc:
            result_q.put(("", exc))

    threading.Thread(target=worker, daemon=True, name="vivie-response-verifier").start()

    try:
        result, error = result_q.get(timeout=timeout_s)
    except Empty:
        print(f"[Verifier] LLM check timed out after {timeout_s:.1f}s")
        return ""

    if error:
        print(f"[Verifier] LLM check error: {error}")
        return ""
    return (result or "").strip()


def verify(question: str, answer: str) -> VerifyResult:
    """
    Verify response quality. Returns VerifyResult.
    Called from fallback.py after Main_Brain() returns.
    Never raises — returns a safe default on any error.
    """
    if not question or not answer:
        return VerifyResult(score=5, should_escalate=False)

    # Cache check
    cached = _get_cached(question, answer)
    if cached:
        m = _metrics()
        if m:
            m.record_verifier_cache(hit=True)
        return VerifyResult(
            score           = cached.score,
            should_escalate = cached.should_escalate,
            reason          = cached.reason,
            from_cache      = True,
        )

    m = _metrics()
    if m:
        m.record_verifier_cache(hit=False)


    t0 = time.perf_counter()

    # ── Stage 1: fast rule-based check ───────────
    fast = _fast_check(question, answer)
    if fast is not None:
        score, reason = fast
        result = VerifyResult(
            score           = score,
            should_escalate = score < ESCALATE_THRESHOLD,
            reason          = reason,
            latency_ms      = (time.perf_counter() - t0) * 1000,
        )
        _set_cached(question, answer, result)
        if result.should_escalate:
            print(f"[Verifier] Low quality ({score}/10): {reason}")
        return result

    # ── Stage 2: LLM scoring (Tier 0) ────────────
    score = 8   # default if LLM call fails
    reason = ""
    try:
        prompt = _VERIFY_PROMPT.format(
            question=question[:300],
            answer=answer[:400],
        )
        raw = _generate_score_with_timeout(prompt, VERIFY_TIMEOUT_S)
        if raw:
            # Extract first integer from response
            import re
            match = re.search(r'\b([1-9]|10)\b', raw.strip())
            if match:
                score = int(match.group(1))
                reason = f"LLM scored {score}/10"
    except Exception as e:
        print(f"[Verifier] LLM check error: {e}")

    latency = (time.perf_counter() - t0) * 1000
    result  = VerifyResult(
        score           = score,
        should_escalate = score < ESCALATE_THRESHOLD,
        reason          = reason,
        latency_ms      = latency,
    )
    _set_cached(question, answer, result)

    if result.should_escalate:
        print(f"[Verifier] Escalating ({score}/10, {latency:.0f}ms): {reason}")
    else:
        print(f"[Verifier] OK ({score}/10, {latency:.0f}ms)")

    # Record quality score in brain metrics
    m = _metrics()
    if m:
        m.record_quality_score(score)

    return result
