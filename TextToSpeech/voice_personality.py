# ==================================================
# voice_personality.py — Vivie Voice Personality
#
# Fixes applied:
#  - Dead SSML path removed (edge-tts can't parse our SSML)
#  - rate / pitch / volume returned directly for edge-tts Communicate()
#  - Personality-engine read cached for 2s (was disk-I/O per sentence)
# ==================================================

import os
import re
import time
import datetime

VOICE          = "en-US-AriaNeural"
FALLBACK_VOICE = "en-US-JennyNeural"

# Per-mood prosody. All values are in edge-tts format.
VOICE_PROFILES = {
    "default":    {"rate": "+0%",  "pitch": "+0Hz",  "volume": "+0%"},
    "casual":     {"rate": "+8%",  "pitch": "+2Hz",  "volume": "+0%"},
    "technical":  {"rate": "-8%",  "pitch": "-1Hz",  "volume": "+5%"},
    "excited":    {"rate": "+12%", "pitch": "+5Hz",  "volume": "+8%"},
    "serious":    {"rate": "-12%", "pitch": "-3Hz",  "volume": "+10%"},
    "greeting":   {"rate": "+5%",  "pitch": "+3Hz",  "volume": "+5%"},
    "suggestion": {"rate": "+0%",  "pitch": "+1Hz",  "volume": "-5%"},
    "concerned":  {"rate": "-5%",  "pitch": "-2Hz",  "volume": "+5%"},
    "thinking":   {"rate": "-5%",  "pitch": "-1Hz",  "volume": "+0%"},
}

_MOOD_KEYWORDS = {
    "greeting":   ["good morning", "good evening", "good afternoon", "welcome back",
                   "hello boss", "hey boss", "good to see"],
    "excited":    ["amazing", "excellent", "perfect", "great news", "fantastic",
                   "wonderful", "incredible", "successfully", "done!", "completed",
                   "that works"],
    "serious":    ["warning", "alert", "critical", "error", "failed", "battery low",
                   "danger", "urgent", "important", "unable to"],
    "technical":  ["algorithm", "function", "code", "python", "neural", "database",
                   "api", "system", "framework", "implementation", "memory",
                   "token", "model", "latency"],
    "suggestion": ["you might", "perhaps", "suggestion", "consider", "you usually",
                   "based on your", "might want to", "i noticed"],
    "concerned":  ["trouble", "issue", "problem", "unfortunately", "unable",
                   "failed", "sorry", "couldn't"],
}


# ───────── mood detection ─────────
def detect_voice_mood(text: str, intent: str = "chat") -> str:
    t = text.lower()
    for mood, keywords in _MOOD_KEYWORDS.items():
        if any(kw in t for kw in keywords):
            return mood
    if intent in ("automation", "file_creation"):
        return "casual"
    if intent in ("research", "chat") and len(text.split()) > 50:
        return "technical"
    return "default"


# ───────── personality cache ─────────
_pers_cache = {"data": None, "ts": 0.0}
_PERS_TTL   = 2.0   # seconds

def _get_personality_adjustments() -> dict:
    now = time.time()
    if _pers_cache["data"] is not None and (now - _pers_cache["ts"]) < _PERS_TTL:
        return _pers_cache["data"]
    try:
        # Use the public accessor instead of the private _load() symbol.
        try:
            from Core_structure.personality_engine import get_personality
        except ImportError:
            from Core_structure.personality_engine import _load as get_personality  # legacy fallback
        p = get_personality()
        rate_adj, pitch_adj = 0, 0
        tone   = p.get("tone", 0.5)
        warmth = p.get("warmth", 0.5)
        depth  = p.get("technical_depth", 0.5)
        if tone   > 0.6: rate_adj  += 5
        elif tone < 0.3: rate_adj  -= 5
        if warmth > 0.6: pitch_adj += 1
        elif warmth < 0.3: pitch_adj -= 1
        if depth  > 0.6: rate_adj  -= 3
        result = {"rate_adj": rate_adj, "pitch_adj": pitch_adj}
    except Exception:
        result = {"rate_adj": 0, "pitch_adj": 0}
    _pers_cache["data"] = result
    _pers_cache["ts"]   = now
    return result


def _time_adjustment() -> dict:
    h = datetime.datetime.now().hour
    if 5  <= h < 9:  return {"rate_adj": -3, "volume_adj": -5}
    if 9  <= h < 17: return {"rate_adj":  0, "volume_adj":  0}
    if 17 <= h < 21: return {"rate_adj": -2, "volume_adj": -2}
    return {"rate_adj": -5, "volume_adj": -8}


# ───────── format helpers ─────────
def _parse_int(s: str) -> int:
    return int(s.replace("%", "").replace("Hz", "").replace("+", ""))

def _fmt_pct(v: int) -> str: return f"+{v}%"  if v >= 0 else f"{v}%"
def _fmt_hz(v: int)  -> str: return f"+{v}Hz" if v >= 0 else f"{v}Hz"


# ───────── public API ─────────
def get_voice_params(text: str, intent: str = "chat") -> dict:
    """
    Returns ready-to-use kwargs for edge_tts.Communicate(...).
    All deltas (mood + personality + time of day) are merged here.
    """
    mood    = detect_voice_mood(text, intent)
    profile = VOICE_PROFILES.get(mood, VOICE_PROFILES["default"])
    pers    = _get_personality_adjustments()
    tadj    = _time_adjustment()

    try:
        rate_val  = _parse_int(profile["rate"])   + pers["rate_adj"]  + tadj["rate_adj"]
        pitch_val = _parse_int(profile["pitch"])  + pers["pitch_adj"]
        vol_val   = _parse_int(profile["volume"]) + tadj["volume_adj"]
        return {
            "voice":  VOICE,
            "rate":   _fmt_pct(rate_val),
            "pitch":  _fmt_hz(pitch_val),
            "volume": _fmt_pct(vol_val),
            "mood":   mood,
        }
    except Exception:
        return {
            "voice":  VOICE,
            "rate":   profile["rate"],
            "pitch":  profile["pitch"],
            "volume": profile["volume"],
            "mood":   mood,
        }


def clean_for_speech(text: str) -> str:
    """Strip markdown / symbols / emojis before TTS."""
    text = re.sub(r'\*\*(.*?)\*\*',    r'\1', text)
    text = re.sub(r'\*(.*?)\*',        r'\1', text)
    text = re.sub(r'#{1,6}\s',         '',    text)
    text = re.sub(r'`(.*?)`',          r'\1', text)
    text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', text)
    replacements = {
        "→": " leads to ", "←": " from ", "✅": "", "❌": "",
        "•": "", "&": " and ", "\n": ". ",
        "↑": " increased ", "↓": " decreased ", "—": ", ",
    }
    for sym, word in replacements.items():
        text = text.replace(sym, word)
    text = re.sub(r'\s+', ' ', text).strip()
    return text