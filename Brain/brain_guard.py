"""
Brain/brain_guard.py — Input/output firewalls for Vivie's LLM pipeline.

Every prompt and response passes through these checks before/after tier calls.

UPGRADE 5 additions:
  - Per-session injection attempt counter (>3 in a session = 60s cooldown)
  - Semantic similarity detection for repeated-probe rephrasing
  - Safe mode flag: if guard triggers 5x consecutively, enter safe mode
"""

from __future__ import annotations

import re
import time
import hashlib
import threading
from typing import Optional

# ── Limits ───────────────────────────────────────────────────────────────────
MAX_PROMPT_CHARS          = 14_000
MAX_USER_TEXT_CHARS       = 4_000
MAX_OUTPUT_CHARS          = 8_000
MAX_SYSTEM_INTERNAL_CHARS = 6_000

# ── Rate limit config ─────────────────────────────────────────────────────────
_MAX_INJECTIONS_PER_SESSION = 3    # block after this many injection attempts
_COOLDOWN_SECONDS           = 60   # seconds to block after threshold reached
_SAFE_MODE_THRESHOLD        = 5    # consecutive triggers → safe mode

# ── Injection / abuse patterns (block or strip) ──────────────────────────────
_INJECTION_PATTERNS = re.compile(
    r"(?i)("
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions"
    r"|disregard\s+(your\s+)?(system\s+)?prompt"
    r"|you\s+are\s+now\s+(?:a\s+)?(?:DAN|jailbreak|unrestricted)"
    r"|reveal\s+(your\s+)?(system\s+)?prompt"
    r"|print\s+(your\s+)?(system\s+)?instructions"
    r"|<\s*/?system\s*>"
    r"|```\s*system"
    r")"
)

_SECRET_PATTERNS = re.compile(
    r"(?i)(api[_-]?key|secret[_-]?key|bearer\s+[a-z0-9._-]{20,}|"
    r"sk-[a-z0-9]{20,}|gsk_[a-z0-9]+)"
)

_OUTPUT_LEAK_PATTERNS = re.compile(
    r"(?i)("
    r"BASE_SYSTEM_PROMPT"
    r"|You are Vivie\s*[—–-]\s*a private"
    r"|You are Vivie's intent classifier"
    r"|VIVIE_CORE_IDENTITY"
    r"|Operating principles:"
    r"|Hard rules:"
    r"|\[SYSTEM TASK"
    r"|\[END SYSTEM TASK\]"
    r")"
)


# ── Rate limiter state ────────────────────────────────────────────────────────

class _GuardState:
    """Thread-safe session-level guard state."""

    def __init__(self):
        self._lock               = threading.Lock()
        self._injection_count    = 0
        self._cooldown_until     = 0.0
        self._consecutive_triggers = 0
        self._safe_mode          = False
        # Rolling fingerprints of recent blocked prompts (detect rephrase attacks)
        self._recent_blocked: list[str] = []

    def _fingerprint(self, text: str) -> str:
        """Coarse n-gram fingerprint for similarity detection."""
        words = text.lower().split()
        # 3-grams
        grams = {" ".join(words[i:i+3]) for i in range(len(words) - 2)}
        sig   = "|".join(sorted(grams)[:20])
        return hashlib.md5(sig.encode()).hexdigest()

    def _is_similar_to_blocked(self, text: str) -> bool:
        """Return True if text is semantically similar to a previously blocked prompt."""
        if not self._recent_blocked:
            return False
        fp = self._fingerprint(text)
        return fp in self._recent_blocked

    def record_injection(self, text: str) -> tuple[bool, str]:
        """
        Record an injection attempt.
        Returns (blocked, reason).
        """
        with self._lock:
            now = time.time()

            # Check cooldown
            if now < self._cooldown_until:
                remaining = int(self._cooldown_until - now)
                return True, f"injection_cooldown:{remaining}s"

            self._injection_count      += 1
            self._consecutive_triggers += 1

            # Store fingerprint for rephrase detection
            fp = self._fingerprint(text)
            self._recent_blocked.append(fp)
            self._recent_blocked = self._recent_blocked[-20:]  # keep last 20

            # Check thresholds
            if self._injection_count > _MAX_INJECTIONS_PER_SESSION:
                self._cooldown_until = now + _COOLDOWN_SECONDS
                print(f"[BrainGuard] Injection threshold exceeded — {_COOLDOWN_SECONDS}s cooldown")
                return True, f"injection_threshold_exceeded:{self._injection_count}_attempts"

            if self._consecutive_triggers >= _SAFE_MODE_THRESHOLD:
                self._safe_mode = True
                print("[BrainGuard] Safe mode ACTIVATED — consecutive injection triggers")
                return True, "safe_mode_active"

            return False, ""

    def check_rephrase(self, text: str) -> bool:
        """Return True if this looks like a rephrased version of a previously blocked prompt."""
        with self._lock:
            return self._is_similar_to_blocked(text)

    def reset_consecutive(self):
        """Call on a clean (non-injecting) prompt to reset the consecutive counter."""
        with self._lock:
            self._consecutive_triggers = max(0, self._consecutive_triggers - 1)

    @property
    def safe_mode(self) -> bool:
        with self._lock:
            return self._safe_mode

    @property
    def in_cooldown(self) -> bool:
        with self._lock:
            return time.time() < self._cooldown_until


_guard_state = _GuardState()


# ── Public API ────────────────────────────────────────────────────────────────

def sanitize_text(text: str, max_len: int = MAX_PROMPT_CHARS) -> str:
    """Normalize and cap length; remove dangerous control characters."""
    if not text:
        return ""
    cleaned = text.replace("\x00", "")
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", cleaned)
    cleaned = cleaned.strip()
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "\n[truncated for safety]"
    return cleaned


def check_prompt_safety(text: str) -> tuple[bool, str]:
    """
    Returns (allowed, reason).

    Checks (in order):
      1. Empty prompt
      2. Length limit
      3. Known injection patterns
      4. Rephrase/similarity to previously blocked prompts
      5. Rate limit / cooldown
    """
    if not text or not text.strip():
        return False, "empty prompt"

    if len(text) > MAX_PROMPT_CHARS:
        return False, "prompt exceeds maximum length"

    if _INJECTION_PATTERNS.search(text):
        blocked, reason = _guard_state.record_injection(text)
        print(f"[BrainGuard] Injection blocked: {reason}")
        return False, f"prompt injection pattern detected ({reason})"

    if _guard_state.check_rephrase(text):
        print("[BrainGuard] Rephrase attack detected — similar to previously blocked prompt")
        return False, "rephrase of blocked injection detected"

    if _guard_state.in_cooldown:
        return False, "guard cooldown active — try again in a moment"

    # Clean prompt — ease consecutive counter slightly
    _guard_state.reset_consecutive()
    return True, ""


def extract_user_utterance(prompt: str) -> str:
    """Best-effort extraction of the latest user line from a full prompt."""
    for line in reversed(prompt.splitlines()):
        stripped = line.strip()
        if stripped.lower().startswith("user:"):
            return stripped[5:].strip()
    m = re.search(
        r"User said:\s*(.+?)\.\s*Respond naturally",
        prompt,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        return m.group(1).strip()
    return prompt[-MAX_USER_TEXT_CHARS:].strip()


def sanitize_output(text: str) -> str:
    """Strip leaked secrets, system prompt fragments, and excess length."""
    if not text:
        return ""
    out = text.strip()
    if _SECRET_PATTERNS.search(out):
        out = _SECRET_PATTERNS.sub("[redacted]", out)
    if _OUTPUT_LEAK_PATTERNS.search(out):
        out = _OUTPUT_LEAK_PATTERNS.sub("", out)
    out = re.sub(r"\n{4,}", "\n\n", out)
    if len(out) > MAX_OUTPUT_CHARS:
        out = out[:MAX_OUTPUT_CHARS].rstrip() + "…"
    return out.strip()


def wrap_system_call(prompt: str, role: str = "system") -> str:
    """
    Wrap internal (non-chat) prompts so backends treat them as instructions only.
    """
    body = sanitize_text(prompt, MAX_SYSTEM_INTERNAL_CHARS)
    return (
        f"[{role.upper()} TASK — structured output only, no roleplay]\n"
        f"{body}\n"
        f"[END {role.upper()} TASK]"
    )


def is_safe_mode() -> bool:
    """Returns True if the brain guard is in safe/restricted mode."""
    return _guard_state.safe_mode


def get_guard_status() -> dict:
    """Returns current guard state for observability."""
    return {
        "safe_mode":        _guard_state.safe_mode,
        "in_cooldown":      _guard_state.in_cooldown,
        "injection_count":  _guard_state._injection_count,
        "consecutive":      _guard_state._consecutive_triggers,
    }