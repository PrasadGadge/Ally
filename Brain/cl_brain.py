# ==========================================
# Brain/cl_brain.py — Streaming Brain
# Streams sentences to TTS as they arrive
# Cuts perceived latency from ~3s to ~0.5s
# ==========================================

import os
import re
import threading
import datetime
import time
from collections import deque

# FIX: removed stray `from transformers.testing_utils import USER` import.
# It was unused, forced the heavy `transformers` package to load on every
# cl_brain import (~2-3s startup hit), and could crash if transformers
# was missing or version-mismatched.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    load_dotenv = None

from Brain.prompt_core import (
    INTENT_RESPONSE_MODES,
    VIVIE_CORE_IDENTITY,
    VIVIE_COGNITIVE_STANDARDS,
)
from Brain import context_builder, history_manager

# Initialize history manager and migrate legacy history if needed
# Lazy migration to avoid blocking import
_history_migrated = False
_history_migration_lock = threading.Lock()

def _ensure_history_migrated():
    global _history_migrated
    if _history_migrated:
        return
    with _history_migration_lock:
        if not _history_migrated:
            try:
                history_manager.load_and_migrate()
                _history_migrated = True
            except Exception as _e:
                print(f"[Brain] History migration error: {_e}")

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_FILE = os.path.join(BASE_DIR, "vivie_history.txt")
MAX_HISTORY_WORDS = 2000

# FIX: simple-chat path runs outside processing_lock, so Main_Brain can be
# called concurrently from two threads. Both read+write the same history file.
# This lock serialises all file access to prevent corruption.
_history_lock = threading.Lock()


# ─────────────────────────────────────────────────
# SYSTEM PROMPT — see Brain/prompt_core.py
# ─────────────────────────────────────────────────

BASE_SYSTEM_PROMPT = VIVIE_CORE_IDENTITY


# ─────────────────────────────────────────────────
# INTENT DETECTION
# ─────────────────────────────────────────────────

def detect_intent(text: str) -> str:
    """
    Detect intent for system-prompt selection.
    Stage 1: fast keyword rules (no API call).
    Stage 2: LLM classifier using INTENT_CLASSIFIER_PROMPT for ambiguous queries.
    FIX: INTENT_CLASSIFIER_PROMPT was defined in prompt_core.py but never called.
    """
    t = text.lower()

    # ── Stage 1: keyword rules (fast, zero latency) ──────────────────────
    if any(w in t for w in [
        "write code", "write a function", "write a python", "write python",
        "implement", "create a function",
        "debug", "fix this code", "refactor", "syntax error",
    ]):
        return "code"
    if any(w in t for w in ["how old", "age", "when was", "how many", "what year"]):
        return "numeric"
    if any(w in t for w in ["who is", "tell me about", "biography"]):
        return "bio"
    if any(w in t for w in ["explain", "why", "how does", "how do"]):
        return "deep"
    if any(w in t for w in ["current", "live", "real time", "latest"]):
        return "realtime"
    if len(t.split()) <= 3:
        return "short"

    # ── Stage 2: LLM classifier for ambiguous multi-word queries ─────────
    # Only invoked when keywords don't match and query is complex enough.
    if len(t.split()) >= 6:
        try:
            from Brain.prompt_core import INTENT_CLASSIFIER_PROMPT
            from Brain.system_llm import system_llm
            import json as _json
            prompt   = INTENT_CLASSIFIER_PROMPT.format(text=text)
            response = system_llm(prompt)
            if response:
                # Strip markdown fences if present
                clean = response.strip().strip("```json").strip("```").strip()
                data  = _json.loads(clean)
                subtype    = data.get("subtype", "general")
                confidence = float(data.get("confidence", 0.0))
                # Only use LLM result if confident enough
                if confidence >= 0.75 and subtype in (
                    "numeric", "short", "bio", "deep", "realtime", "code", "general"
                ):
                    return subtype
        except Exception:
            pass  # silently fall through to default

    return "general"


# ─────────────────────────────────────────────────
# DYNAMIC PROMPT BUILDER
# ─────────────────────────────────────────────────

def build_system_prompt(intent: str, user_model_context: str = "") -> str:
    try:
        from Core_structure.personality_engine import get_personality_prompt
        personality_prompt = get_personality_prompt()
    except Exception:
        personality_prompt = ""

    prompt = BASE_SYSTEM_PROMPT + "\n\n" + VIVIE_COGNITIVE_STANDARDS
    if personality_prompt:
        prompt += f"\n\n{personality_prompt}"

    # Inject Prasad world model — makes every response personally relevant
    if user_model_context and user_model_context.strip():
        prompt += f"\n\n[What you know about your user]\n{user_model_context}"

    prompt += INTENT_RESPONSE_MODES.get(intent, INTENT_RESPONSE_MODES["general"])
    return prompt


# ─────────────────────────────────────────────────
# HISTORY HANDLING
# ─────────────────────────────────────────────────

def load_history() -> str:
    if not os.path.exists(HISTORY_FILE):
        return ""
    try:
        with _history_lock:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return f.read()
    except Exception:
        return ""


def save_history(history: str):
    try:
        with _history_lock:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write(history)
    except Exception as e:
        print(f"[Brain] History save error: {e}")


def trim_history(history: str) -> str:
    token_starts = deque(maxlen=MAX_HISTORY_WORDS)
    overflow = False
    for match in re.finditer(r"\S+", history):
        if len(token_starts) == MAX_HISTORY_WORDS:
            overflow = True
        token_starts.append(match.start())
    if overflow:
        return history[token_starts[0]:]
    return history


def _extract_clean_user_text(full_prompt: str) -> str:
    # FIX: early-exit path passes "User said: X. Respond naturally, warmly, and very briefly."
    # Extract just X so history shows the actual user words, not the instruction wrapper.
    m = re.match(r"User said:\s*(.+?)\.\s*Respond naturally", full_prompt, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:200]

    lines = full_prompt.strip().split('\n')
    for line in reversed(lines):
        if line.startswith('User:'):
            return line[5:].strip()[:200]
    return full_prompt[:200].strip()


# ─────────────────────────────────────────────────
# RESPONSE CLEANER
# ─────────────────────────────────────────────────

def _get_user_name() -> str:
    """
    Return the user's actual name from memory, or 'Boss' as default.
    Cached for 60s so we don't hit the file on every response.
    """
    now = time.time()
    if now - _name_cache["ts"] < 60.0:
        return _name_cache["name"]
    try:
        # Check episodic memory for stored name
        from memory_core.episodic_memory import load_episodes
        episodes = load_episodes()
        for ep in reversed(episodes[-50:]):
            ui = ep.get("user_input", "").lower()
            if "my name is" in ui:
                name = ui.split("my name is")[-1].strip().split()[0].capitalize()
                _name_cache["name"] = name
                _name_cache["ts"]   = now
                return name
    except Exception:
        pass
    _name_cache["name"] = "Boss"
    _name_cache["ts"]   = now
    return "Boss"


_name_cache = {"name": "Boss", "ts": 0.0}


def clean_response(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"(AI:|Assistant:)", "", text, flags=re.IGNORECASE)
    # FIX: LLM sometimes outputs literal {USER_NAME} when it has no name context.
    # Replace it with actual stored name (or "Boss" as fallback).
    if "{USER_NAME}" in text:
        text = text.replace("{USER_NAME}", _get_user_name())
    return text.strip()


# ─────────────────────────────────────────────────
# STREAMING MAIN BRAIN
# ─────────────────────────────────────────────────

def _build_full_prompt(text: str,
                       cot_context: str = "",
                       user_model_context: str = "",
                       history_text: str = "",
                       episodic_memory: str = "",
                       knowledge_context: str = "") -> tuple:
    ts         = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    intent     = detect_intent(text)
    sys_prompt = build_system_prompt(intent)

    clean_user = history_text.strip() if history_text else _extract_clean_user_text(text)
    # Upgrade 2: Smart History Compression
    history_manager.add_turn("User", clean_user)
    history_block = history_manager.get_history_block()

    context_block = context_builder.build_context(
        user_model_context=user_model_context,
        cot_context=cot_context,
        episodic_memory=episodic_memory,
        session_history=history_block,
        knowledge_context=knowledge_context,
    )

    full_prompt = sys_prompt
    if context_block:
        full_prompt += "\n\n" + context_block

    full_prompt += "\n\n" + text
    return full_prompt, clean_user, intent, history_block, ts


def Main_Brain(text: str,
               history_text: str = "",
               cot_context: str = "",
               user_model_context: str = "",
               forced_tier: int | None = None,
               episodic_memory: str = "",
               knowledge_context: str = "") -> str:
    """
    Blocking LLM call — returns complete response string.
    history_text:       stored in history instead of text (early-exit path)
    cot_context:        chain-of-thought block injected into prompt
    user_model_context: Prasad world model for system prompt
    episodic_memory:    retrieved memory context injected into the prompt
    knowledge_context:  RAG/knowledge context injected into the prompt
    forced_tier:        optional tier override for verified escalation
    """
    _ensure_history_migrated()
    try:
        from Brain.tiered_brain import api_generate_response
        full_prompt, clean_user, intent, history_block, ts = _build_full_prompt(
            text,
            cot_context=cot_context,
            user_model_context=user_model_context,
            history_text=history_text,
            episodic_memory=episodic_memory,
            knowledge_context=knowledge_context,
        )

        response = api_generate_response(full_prompt, forced_tier=forced_tier)
        response = clean_response(response)

        if not response:
            return "I couldn't generate a response. Please try again."

        # Upgrade 2: Smart History Compression
        history_manager.add_turn("Vivie", response)
        history_manager.save_history_to_file()

        return response

    except Exception as e:
        print(f"[Brain Error]: {e}")
        return "Processing interruption detected."


def Main_Brain_Stream(
    text: str,
    on_sentence=None,
    cot_context: str = "",
    user_model_context: str = "",
    episodic_memory: str = "",
    knowledge_context: str = "",
) -> str:
    """Streaming LLM call. Calls on_sentence(sentence_str) for each sentence."""
    try:
        from Brain.tiered_brain import stream_response
        full_prompt, clean_user, intent, history_block, ts = _build_full_prompt(
            text,
            cot_context=cot_context,
            user_model_context=user_model_context,
            episodic_memory=episodic_memory,
            knowledge_context=knowledge_context,
        )

        full_response = ""

        for sentence in stream_response(full_prompt):
            sentence = clean_response(sentence)
            if not sentence:
                continue

            full_response += sentence + " "

            if on_sentence:
                on_sentence(sentence.strip())

        full_response = full_response.strip()

        if not full_response:
            fallback = "I couldn't generate a response. Please try again."
            if on_sentence:
                on_sentence(fallback)
            return fallback

        # Upgrade 2: Smart History Compression
        history_manager.add_turn("Vivie", full_response)
        history_manager.save_history_to_file()

        return full_response

    except Exception as e:
        print(f"[Brain Stream Error]: {e}")
        fallback = "Processing interruption detected."
        if on_sentence:
            on_sentence(fallback)
        return fallback
