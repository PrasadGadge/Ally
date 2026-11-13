# ==========================================
# Core_structure/intent_engine.py
# Phase 6: Lightweight fallback-only engine
#
# The LLM router in llm_intent_router.py is
# now the primary classifier. This engine only
# runs when the LLM is unavailable or returns
# null (chat). Hardcoded keyword dicts removed.
# ==========================================

import re
from Core_structure.ai_intent import AIIntentDetector


class IntentEngine:
    """
    Lightweight fallback intent engine for Vivie.
    Handles cases the LLM router can't or won't (chat, memory commands,
    edge-case knowledge queries). Falls back to AI intent detector if
    even these minimal rules don't match.
    """

    def __init__(self):
        self.ai_detector = AIIntentDetector()

    def detect(self, text: str, context: dict = None) -> dict:
        # ── Normalize ────────────────────────────────────────────────
        text_lower = re.sub(r'\s+', ' ', text.lower()).strip()

        # ── 1. Knowledge / memory map queries ────────────────────────
        _knowledge_phrases = (
            "knowledge graph", "knowledge map", "show knowledge",
            "research history", "what have you learned", "what do you know",
            "your memory", "past research", "what you researched",
        )
        if any(p in text_lower for p in _knowledge_phrases):
            return {"primary": "research", "subtype": "knowledge_map", "confidence": 0.95}

        # ── 2. Explicit memory/note commands ─────────────────────────
        _memory_starters = (
            "vivie remember", "remember ", "remember that",
            "remember this", "don't forget", "keep in mind",
        )
        if text_lower.startswith(_memory_starters):
            return {"primary": "chat", "subtype": "personal_info", "confidence": 0.95}

        # ── 3. Battery / device status ────────────────────────────────
        _battery_phrases = (
            "check device charging", "device charging", "charging status",
            "check charging", "check battery", "battery percentage",
            "battery status", "battery level", "how much battery",
        )
        if any(p in text_lower for p in _battery_phrases):
            return {"primary": "automation", "subtype": "device_status", "confidence": 0.95}

        # ── 4. Context continuation ───────────────────────────────────
        # If the user follows up with a short reference like "tomorrow?"
        # after a weather query, carry the context forward.
        if context:
            last_intent = context.get("last_intent")
            follow_words = ("tomorrow", "today", "next", "and", "then",
                            "what about", "how about")
            if any(w in text_lower for w in follow_words):
                if last_intent == "weather":
                    return {"primary": "weather", "subtype": "forecast", "confidence": 0.90}

        # ── 5. AI fallback ────────────────────────────────────────────
        print("[IntentEngine] LLM router unavailable — using AI fallback.")
        return self.ai_detector.detect(text)
