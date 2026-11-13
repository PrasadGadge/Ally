# ==================================================
# Brain/chain_of_thought.py  —  Vivie CoT Engine
#
# Replaces keyword-based reasoning with actual LLM
# reasoning. Two fast Tier 0 calls before the main
# response. Total overhead: ~300ms on complex queries.
# Skipped entirely for simple/automation queries.
#
# Output is a structured context block injected into
# the main LLM prompt — gives dramatically richer
# answers because the LLM receives:
#   • What the user actually wants (decomposed intent)
#   • What Vivie knows + what gaps exist
#   • Recommended response strategy
# instead of just the raw user words.
# ==================================================

from __future__ import annotations

import time
import threading
from dataclasses import dataclass
from queue import Empty, Queue

from Brain.tiered_brain import api_generate_response

# Metrics — lazy import
def _metrics():
    try:
        import Brain.brain_metrics as _m
        return _m
    except Exception:
        return None

COT_HARD_TIMEOUT_S = 15.0  # Hard abort budget for both fast-tier CoT calls.


# ─────────────────────────────────────────────────
# SKIP CONDITIONS
# Words/intents that bypass CoT entirely
# ─────────────────────────────────────────────────

_SKIP_INTENTS = frozenset({
    "automation", "time", "alarm", "reminder",
    "weather", "music", "volume", "scroll",
    "open", "close", "search",
})

_SKIP_PREFIXES = (
    "open ", "close ", "play ", "stop ", "pause ",
    "scroll ", "search ", "set alarm", "remind me",
    "check battery", "what time",
)

_MIN_WORDS_FOR_COT = 7   # Simple queries rarely benefit from CoT.


# ─────────────────────────────────────────────────
# PROMPTS
# ─────────────────────────────────────────────────

_DECOMPOSE_PROMPT = """Analyze this user request in 2-3 sentences. Be brief.

User said: "{text}"

Answer these three things:
1. INTENT: What does the user actually want? (not just the surface question)
2. SUBTEXT: Any implicit need, emotion, or context behind the request?
3. GOAL: What would a perfect response achieve for them?

Keep each point to one sentence. No preamble."""


_ASSESS_PROMPT = """You are Vivie's reasoning engine.

User request: "{text}"
Context available:
  Memory: {memory_summary}
  Knowledge: {knowledge_summary}

Answer briefly:
1. KNOW: What relevant information do you have about this?
2. GAPS: What's missing that would improve the answer?
3. STRATEGY: What type of response works best here?
   (options: direct-answer, explain-then-answer,
    ask-clarifying-question, step-by-step, creative, empathetic)

One sentence per point. No preamble."""


# ─────────────────────────────────────────────────
# RESULT
# ─────────────────────────────────────────────────

@dataclass
class CoTResult:
    decomposed_intent: str = ""
    knowledge_assessment: str = ""
    strategy: str = "direct-answer"
    latency_ms: float = 0.0
    skipped: bool = False

    def to_prompt_block(self) -> str:
        """Returns the context block injected into the main LLM prompt."""
        if self.skipped or not self.decomposed_intent:
            return ""
        lines = ["[Reasoning context — use this to shape your response]"]
        if self.decomposed_intent:
            lines.append(f"Intent analysis: {self.decomposed_intent}")
        if self.knowledge_assessment:
            lines.append(f"Knowledge check: {self.knowledge_assessment}")
        if self.strategy and self.strategy != "direct-answer":
            lines.append(f"Response strategy: {self.strategy}")
        return "\n".join(lines)


# ─────────────────────────────────────────────────
# MAIN FUNCTION
# ─────────────────────────────────────────────────

def build_cot(ctx) -> str:
    """
    Entry point called from processor.py.
    ctx: PipelineContext

    Returns a context block string (empty string if skipped).
    Never raises — all errors return empty string gracefully.
    """
    try:
        result = _run_cot(ctx)
        # Record CoT metrics
        m = _metrics()
        if m:
            m.record_cot(skipped=result.skipped, latency_ms=result.latency_ms)
        return result.to_prompt_block()
    except Exception as e:
        print(f"[CoT] Error: {e}")
        return ""


def _should_skip(ctx) -> bool:
    text    = ctx.text.lower().strip()
    primary = ctx.primary_intent.lower()

    if len(ctx.text.split()) < _MIN_WORDS_FOR_COT:
        return True

    if primary in _SKIP_INTENTS:
        return True

    if any(text.startswith(p) for p in _SKIP_PREFIXES):
        return True

    # Also skip for fast-chat path (handled by handle_fast_chat)
    if primary == "chat" and ctx.confidence >= 0.9:
        return True

    return False


def _summarise(text: str, max_chars: int = 120) -> str:
    if not text:
        return "none"
    return text.strip()[:max_chars].replace("\n", " ")


def _remaining(deadline: float) -> float:
    return max(0.0, deadline - time.perf_counter())


def _generate_with_timeout(prompt: str, timeout_s: float, label: str) -> str:
    if timeout_s <= 0:
        print(f"[CoT] {label} skipped; timeout exhausted")
        return ""

    result_q: Queue = Queue(maxsize=1)

    def worker():
        try:
            result_q.put((api_generate_response(prompt, forced_tier=0), None))
        except Exception as exc:
            result_q.put(("", exc))

    threading.Thread(target=worker, daemon=True, name=f"vivie-cot-{label}").start()

    try:
        result, error = result_q.get(timeout=timeout_s)
    except Empty:
        print(f"[CoT] {label} timed out after {timeout_s:.1f}s")
        return ""

    if error:
        print(f"[CoT] {label} error: {error}")
        return ""
    return (result or "").strip()


def _run_cot(ctx) -> CoTResult:
    if _should_skip(ctx):
        return CoTResult(skipped=True)

    t0       = time.perf_counter()
    deadline = t0 + COT_HARD_TIMEOUT_S
    text     = ctx.text

    # ── Step 1: Decompose intent (Tier 0, ~150ms) ──────────────────────
    decomposed = ""
    try:
        prompt_1 = _DECOMPOSE_PROMPT.format(text=text)
        raw      = _generate_with_timeout(
            prompt_1,
            min(7.0, _remaining(deadline)),
            "decompose",
        )
        decomposed = (raw or "").strip()[:400]
    except Exception as e:
        print(f"[CoT] Step 1 error: {e}")

    if _remaining(deadline) <= 0:
        return CoTResult(
            decomposed_intent=decomposed,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )

    # ── Step 2: Assess knowledge + strategy (Tier 0, ~150ms) ────────────
    assessment = ""
    strategy   = "direct-answer"
    try:
        memory_summary    = _summarise(getattr(ctx, "memory_block", ""))
        knowledge_summary = _summarise(getattr(ctx, "knowledge_context", ""))

        prompt_2 = _ASSESS_PROMPT.format(
            text=text,
            memory_summary=memory_summary,
            knowledge_summary=knowledge_summary,
        )
        raw = _generate_with_timeout(prompt_2, _remaining(deadline), "assess")
        assessment = (raw or "").strip()[:400]

        # Extract strategy keyword from assessment
        for s in ["direct-answer", "explain-then-answer",
                  "ask-clarifying-question", "step-by-step",
                  "creative", "empathetic"]:
            if s in assessment.lower():
                strategy = s
                break

    except Exception as e:
        print(f"[CoT] Step 2 error: {e}")

    latency = (time.perf_counter() - t0) * 1000
    print(f"[CoT] Completed in {latency:.0f}ms | strategy: {strategy}")

    return CoTResult(
        decomposed_intent    = decomposed,
        knowledge_assessment = assessment,
        strategy             = strategy,
        latency_ms           = latency,
        skipped              = False,
    )
