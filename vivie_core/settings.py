"""
Central configuration — load once from environment.
Override via .env (see .env.example).
"""

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except ValueError:
        return default


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, default))
    except ValueError:
        return default


# ── Pipeline ─────────────────────────────────────────────────────────────
POST_SPEAK_COOLDOWN        = _float("VIVIE_POST_SPEAK_COOLDOWN",  1.5)
MEMORY_RETRIEVAL_TIMEOUT   = _float("VIVIE_MEMORY_TIMEOUT",       3.0)
MEMORY_CACHE_TTL           = _float("VIVIE_MEMORY_CACHE_TTL",     8.0)
MEMORY_CACHE_MAX_ENTRIES   = _int(  "VIVIE_MEMORY_CACHE_MAX",     64)
MEMORY_STORE_DEDUP_SECONDS = _float("VIVIE_MEMORY_DEDUP_SEC",     30.0)

# ── STT ──────────────────────────────────────────────────────────────────
STT_GROQ_MODEL       = os.getenv("VIVIE_STT_MODEL", "whisper-large-v3-turbo")
STT_SILENCE_DURATION = _float("VIVIE_STT_SILENCE_SEC",    1.2)
STT_MAX_RECORD_SEC   = _float("VIVIE_STT_MAX_RECORD_SEC", 12.0)
STT_GROQ_FAIL_LIMIT  = _int(  "VIVIE_STT_GROQ_FAIL_LIMIT", 3)

# ── TTS ──────────────────────────────────────────────────────────────────
TTS_FETCH_TIMEOUT = _float("VIVIE_TTS_FETCH_TIMEOUT", 5.0)
TTS_MAX_WORDS     = _int(  "VIVIE_TTS_MAX_WORDS",     150)
FFMPEG_PATH       = os.getenv("FFMPEG_PATH", "").strip()

# ── API key presence checks (never log values) ────────────────────────────
def has_groq() -> bool:
    """GROQ_API_KEY is used for Whisper STT only — not for LLM chat."""
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def has_nvidia() -> bool:
    """NVIDIA_API_KEY powers Tier 1 (fast) brain — NVIDIA Nemotron-Super."""
    return bool(os.getenv("NVIDIA_API_KEY", "").strip())


def has_openrouter() -> bool:
    """OPENROUTER_API_KEY powers Tier 2 (advanced) brain — Gemini 2.5 Pro etc."""
    return bool(os.getenv("OPENROUTER_API_KEY", "").strip())


def has_mem0() -> bool:
    return bool(os.getenv("MEM0_API_KEY", "").strip())