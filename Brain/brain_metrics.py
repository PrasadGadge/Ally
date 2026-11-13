# ==================================================
# Brain/brain_metrics.py — Vivie Brain Observability
#
# Tracks real-time performance of every brain component:
#   • Per-tier call counts, success rates, latencies
#   • CoT skip/run rates and latency
#   • Response quality score distribution
#   • Escalation rate (Tier 0 → Tier 1)
#   • Cache hit rates
#   • Rolling 100-call window for live stats
#
# Zero overhead on hot path — all updates are O(1).
# Thread-safe with a single lock.
#
# Query: brain_status() → dict
# Reset: reset_metrics()
# ==================================================

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict


# ── Config ────────────────────────────────────────────────────────────────────

_ROLLING_WINDOW = 100   # calls tracked in rolling window

_lock = threading.Lock()


# ── Per-tier stats ─────────────────────────────────────────────────────────

@dataclass
class TierStats:
    name:          str
    calls:         int   = 0
    successes:     int   = 0
    failures:      int   = 0
    total_ms:      float = 0.0
    first_token_ms: Deque[float] = field(default_factory=lambda: deque(maxlen=_ROLLING_WINDOW))

    @property
    def success_rate(self) -> float:
        return (self.successes / self.calls * 100) if self.calls else 0.0

    @property
    def avg_latency_ms(self) -> float:
        if not self.first_token_ms:
            return 0.0
        return sum(self.first_token_ms) / len(self.first_token_ms)

    def to_dict(self) -> dict:
        return {
            "calls":        self.calls,
            "successes":    self.successes,
            "failures":     self.failures,
            "success_rate": f"{self.success_rate:.1f}%",
            "avg_latency":  f"{self.avg_latency_ms:.0f}ms",
        }


# ── Global state ──────────────────────────────────────────────────────────────

_tier_stats: Dict[int, TierStats] = {
    0: TierStats(name="Fast (NVIDIA)"),
    1: TierStats(name="Advanced (OpenRouter)"),
}

# CoT metrics
_cot_runs:    int   = 0
_cot_skips:   int   = 0
_cot_total_ms: float = 0.0
_cot_latencies: Deque[float] = deque(maxlen=_ROLLING_WINDOW)

# Quality scores from response verifier
_quality_scores: Deque[int] = deque(maxlen=_ROLLING_WINDOW)
_escalations:    int         = 0   # Tier 0 → 1 escalations

# Cache hits
_verifier_cache_hits:   int = 0
_verifier_cache_misses: int = 0

# Session start time
_start_time: float = time.time()


# ── Recording API (called from brain components) ──────────────────────────────

def record_tier_call(tier: int, success: bool, first_token_ms: float = 0.0) -> None:
    """Record a tier LLM call result."""
    with _lock:
        stats = _tier_stats.get(tier)
        if stats is None:
            return
        stats.calls += 1
        if success:
            stats.successes += 1
            if first_token_ms > 0:
                stats.first_token_ms.append(first_token_ms)
                stats.total_ms += first_token_ms
        else:
            stats.failures += 1


def record_escalation() -> None:
    """Record a Tier 0 → Tier 1 escalation due to quality."""
    global _escalations
    with _lock:
        _escalations += 1


def record_cot(skipped: bool, latency_ms: float = 0.0) -> None:
    """Record a CoT run or skip."""
    global _cot_runs, _cot_skips, _cot_total_ms
    with _lock:
        if skipped:
            _cot_skips += 1
        else:
            _cot_runs += 1
            _cot_total_ms += latency_ms
            _cot_latencies.append(latency_ms)


def record_quality_score(score: int) -> None:
    """Record a response quality score from the verifier."""
    with _lock:
        _quality_scores.append(score)


def record_verifier_cache(hit: bool) -> None:
    """Record a verifier cache hit or miss."""
    global _verifier_cache_hits, _verifier_cache_misses
    with _lock:
        if hit:
            _verifier_cache_hits += 1
        else:
            _verifier_cache_misses += 1


# ── Query API ─────────────────────────────────────────────────────────────────

def brain_status() -> dict:
    """
    Returns a comprehensive brain health snapshot.
    Called by "Vivie show brain stats" command.
    """
    with _lock:
        uptime_s = int(time.time() - _start_time)
        uptime   = f"{uptime_s // 3600}h {(uptime_s % 3600) // 60}m {uptime_s % 60}s"

        # Quality stats
        scores = list(_quality_scores)
        avg_q  = (sum(scores) / len(scores)) if scores else 0.0
        low_q  = sum(1 for s in scores if s < 5)

        # CoT stats
        cot_total = _cot_runs + _cot_skips
        cot_run_rate = ((_cot_runs / cot_total * 100) if cot_total else 0)
        cot_avg_ms   = (
            (sum(_cot_latencies) / len(_cot_latencies))
            if _cot_latencies else 0.0
        )

        # Cache stats
        vc_total = _verifier_cache_hits + _verifier_cache_misses
        vc_rate  = ((_verifier_cache_hits / vc_total * 100) if vc_total else 0)

        return {
            "uptime":          uptime,
            "tiers":           {t: s.to_dict() for t, s in _tier_stats.items()},
            "escalations":     _escalations,
            "cot": {
                "runs":        _cot_runs,
                "skips":       _cot_skips,
                "run_rate":    f"{cot_run_rate:.1f}%",
                "avg_latency": f"{cot_avg_ms:.0f}ms",
            },
            "quality": {
                "samples":     len(scores),
                "avg_score":   f"{avg_q:.1f}/10",
                "low_quality": low_q,
            },
            "verifier_cache": {
                "hits":     _verifier_cache_hits,
                "misses":   _verifier_cache_misses,
                "hit_rate": f"{vc_rate:.1f}%",
            },
        }


def brain_status_text() -> str:
    """Returns a human-readable brain status summary for Vivie to speak."""
    s = brain_status()
    t0 = s["tiers"].get(0, {})
    t1 = s["tiers"].get(1, {})
    lines = [
        f"Brain Status — up {s['uptime']}",
        f"Fast tier: {t0.get('calls', 0)} calls, {t0.get('success_rate', '0%')} success, {t0.get('avg_latency', '0ms')} avg",
        f"Advanced tier: {t1.get('calls', 0)} calls, {t1.get('success_rate', '0%')} success, {t1.get('avg_latency', '0ms')} avg",
        f"Escalations: {s['escalations']}",
        f"CoT: {s['cot']['runs']} runs, {s['cot']['skips']} skips ({s['cot']['run_rate']} run rate), {s['cot']['avg_latency']} avg",
        f"Response quality avg: {s['quality']['avg_score']} ({s['quality']['low_quality']} low-quality triggers)",
        f"Verifier cache: {s['verifier_cache']['hit_rate']} hit rate",
    ]
    return "\n".join(lines)


def reset_metrics() -> None:
    """Reset all metrics — for testing only."""
    global _cot_runs, _cot_skips, _cot_total_ms, _escalations
    global _verifier_cache_hits, _verifier_cache_misses, _start_time
    with _lock:
        for stats in _tier_stats.values():
            stats.calls = 0
            stats.successes = 0
            stats.failures = 0
            stats.total_ms = 0.0
            stats.first_token_ms.clear()
        _cot_runs = _cot_skips = _escalations = 0
        _cot_total_ms = _verifier_cache_hits = _verifier_cache_misses = 0
        _quality_scores.clear()
        _cot_latencies.clear()
        _start_time = time.time()
