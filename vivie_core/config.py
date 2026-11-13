"""Central configuration constants for the Vivie pipeline."""

import os

from vivie_core.settings import POST_SPEAK_COOLDOWN  # noqa: F401 — re-export

# Interaction mode: "chat" (text-only) or "voice" (text + audio)
VIVIE_MODE = os.getenv("VIVIE_MODE", "chat").lower()
VOICE_ENABLED = VIVIE_MODE == "voice"

REALTIME_KEYWORDS = [
    "current", "latest", "today", "news",
    "live", "price", "stock", "weather now",
]

MEMORY_INTENTS = frozenset({
    "chat", "information", "question", "personal", "research", "advice",
})

# Time parsing helpers (schedule / alarm)
HOUR_NUMBERS = ["1:", "2:", "3:", "4:", "5:", "6:", "7:", "8:", "9:"]
SPLIT_HOUR_NUMBERS = ["11:", "12:"]

CODE_TRIGGERS = [
    "write a function", "write a python", "write code",
    "write a program", "implement", "create a function",
]

AUTOCORRECT_MAP = {
    # DO NOT add word substitutions that mangle technical terms
    # "network" was here → broke "neural network" every time. NEVER add back.
    "whats":   "what is",
    "wht":     "what",
    "recieve": "receive",
    "teh":     "the",
}

WAKE_VARIANTS = [
    "vivi", "vv", "baby", "bibi", "biwi", "vee vee", "abp", "v8", "bbp", "pv", "vb",
]