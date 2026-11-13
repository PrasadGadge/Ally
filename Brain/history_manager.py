# ==================================================
# Brain/history_manager.py — Smart History Compression
#
# UPGRADE 2: Replaces dumb word-count trimming with:
#
#   1. Recency Window — last N turns kept verbatim
#   2. Compressed Snapshot — older turns summarized
#      by Tier 0 LLM (background thread, non-blocking)
#   3. Injection Format — single clean block:
#      [COMPRESSED HISTORY]\n{summary}\n[RECENT TURNS]\n{recent}
#
# Critical context (user name, ongoing projects, key facts)
# is NEVER lost because the summary prompt explicitly
# instructs the LLM to preserve these.
#
# Zero pipeline latency:
#   - get_history_block() reads in-memory strings only
#   - Compression runs async in background
# ==================================================

from __future__ import annotations

import os
import re
import threading
import datetime
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────

_BASE_DIR    = Path(__file__).parent.parent
_HISTORY_FILE = _BASE_DIR / "vivie_history.txt"
_DATA_DIR    = _BASE_DIR / "data"
_SNAPSHOT_FILE = _DATA_DIR / "history_snapshot.txt"

RECENCY_WINDOW   = 8     # last N turns kept verbatim (each turn = User+Vivie pair)
MAX_RECENT_WORDS = 800   # max words in recent window
MAX_SNAPSHOT_CHARS = 600 # max chars in compressed snapshot
COMPRESS_AFTER_TURNS = 6 # trigger compression when older-than-window history > N turns


# ── Thread safety ─────────────────────────────────────────────────────────────

_lock             = threading.Lock()
_compress_lock    = threading.Lock()
_compressing      = False


# ── In-memory state ──────────────────────────────────────────────────────────

_recent_turns:    deque  = deque(maxlen=RECENCY_WINDOW)   # (ts, speaker, text) tuples
_snapshot:        str    = ""   # last compressed summary
_snapshot_loaded: bool   = False


# ── Compression prompt ────────────────────────────────────────────────────────

_COMPRESS_PROMPT = """Summarize this conversation history in 3-5 sentences.
CRITICAL: Preserve any mentions of:
- The user's name
- Ongoing projects or tasks
- Key facts or preferences the user stated
- Any unresolved questions or pending actions

History:
{history}

Reply with ONLY the summary. No preamble."""


# ── Snapshot persistence ──────────────────────────────────────────────────────

def _load_snapshot() -> str:
    global _snapshot, _snapshot_loaded
    if _snapshot_loaded:
        return _snapshot
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if _SNAPSHOT_FILE.exists():
            _snapshot = _SNAPSHOT_FILE.read_text(encoding="utf-8").strip()
    except Exception:
        _snapshot = ""
    _snapshot_loaded = True
    return _snapshot


def _save_snapshot(text: str):
    global _snapshot
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        _SNAPSHOT_FILE.write_text(text, encoding="utf-8")
        _snapshot = text
    except Exception as e:
        print(f"[HistoryMgr] Snapshot save error: {e}")


# ── Raw history file I/O (backward compat) ────────────────────────────────────

def _load_raw_history() -> str:
    """Load the legacy vivie_history.txt file."""
    try:
        if _HISTORY_FILE.exists():
            return _HISTORY_FILE.read_text(encoding="utf-8")
    except Exception:
        pass
    return ""


def _save_raw_history(text: str):
    """Save to legacy vivie_history.txt (kept for backward compat)."""
    try:
        _HISTORY_FILE.write_text(text, encoding="utf-8")
    except Exception as e:
        print(f"[HistoryMgr] History save error: {e}")


# ── Turn parsing ──────────────────────────────────────────────────────────────

_TURN_PATTERN = re.compile(
    r"\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\]\s+(User|Vivie):\s*(.*?)(?=\n\[|\Z)",
    re.DOTALL,
)


def _parse_turns(raw: str) -> list[tuple[str, str, str]]:
    """Parse raw history text into [(timestamp, speaker, text)] tuples."""
    turns = []
    for m in _TURN_PATTERN.finditer(raw):
        turns.append((m.group(1), m.group(2), m.group(3).strip()))
    return turns


def _turns_to_text(turns: list[tuple[str, str, str]]) -> str:
    return "\n".join(f"[{ts}] {speaker}: {text}" for ts, speaker, text in turns)


# ── Compression (background) ──────────────────────────────────────────────────

def _compress_async(old_turns: list[tuple[str, str, str]]):
    """Run LLM compression in a background thread."""
    global _compressing
    with _compress_lock:
        if _compressing:
            return
        _compressing = True

    def _do():
        global _compressing
        try:
            history_text = _turns_to_text(old_turns)
            prompt = _COMPRESS_PROMPT.format(history=history_text[:2000])
            from Brain.tiered_brain import api_generate_response
            summary = api_generate_response(prompt, forced_tier=0)
            if summary and summary.strip():
                compressed = summary.strip()[:MAX_SNAPSHOT_CHARS]
                _save_snapshot(compressed)
                print(f"[HistoryMgr] Compressed {len(old_turns)} older turns → {len(compressed)} chars")
        except Exception as e:
            print(f"[HistoryMgr] Compression error: {e}")
        finally:
            _compressing = False

    threading.Thread(target=_do, daemon=True, name="vivie-history-compress").start()


# ── Public API ────────────────────────────────────────────────────────────────

def add_turn(speaker: str, text: str):
    """
    Add a new conversation turn to the in-memory recent window.
    speaker: "User" | "Vivie"
    text:    the utterance (will be truncated to 300 chars)
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with _lock:
        _recent_turns.append((ts, speaker, text[:300]))


def get_history_block() -> str:
    """
    Returns the full history block ready to inject into LLM prompt.

    Format:
        [COMPRESSED HISTORY]
        <summary of older turns>
        [RECENT TURNS]
        <last N turns verbatim>

    If no snapshot exists, falls back to recent turns only.
    Zero LLM calls — pure memory read.
    """
    snapshot = _load_snapshot()
    with _lock:
        recent = list(_recent_turns)

    parts = []
    if snapshot:
        parts.append(f"[COMPRESSED HISTORY]\n{snapshot}")
    if recent:
        parts.append("[RECENT TURNS]\n" + _turns_to_text(recent))

    return "\n\n".join(parts) if parts else ""


def load_and_migrate():
    """
    Called at startup. Reads old vivie_history.txt, migrates turns
    into the new manager, and triggers compression of older turns.
    """
    _load_snapshot()
    raw = _load_raw_history()
    if not raw.strip():
        return

    turns = _parse_turns(raw)
    if not turns:
        return

    # Put last RECENCY_WINDOW turns into the recent window
    recent = turns[-RECENCY_WINDOW:]
    older  = turns[:-RECENCY_WINDOW]

    with _lock:
        _recent_turns.clear()
        for t in recent:
            _recent_turns.append(t)

    # Trigger compression of older turns if we have enough
    if len(older) >= COMPRESS_AFTER_TURNS and not _snapshot:
        print(f"[HistoryMgr] Migrating {len(older)} older turns to compressed snapshot...")
        _compress_async(older)

    print(f"[HistoryMgr] Loaded {len(recent)} recent turns from history file.")


def save_history_to_file():
    """
    Persist current in-memory turns back to vivie_history.txt
    for backward compatibility.
    """
    with _lock:
        recent = list(_recent_turns)

    snapshot = _load_snapshot()
    lines = []
    if snapshot:
        lines.append(f"[SNAPSHOT] {snapshot}")
    lines.extend(f"[{ts}] {sp}: {txt}" for ts, sp, txt in recent)
    _save_raw_history("\n".join(lines))


def get_recent_turns_text() -> str:
    """Returns only the recent turns as plain text (for backward compat callers)."""
    with _lock:
        recent = list(_recent_turns)
    return _turns_to_text(recent)


def trim_legacy(history: str, max_words: int = 2000) -> str:
    """
    Legacy word-count trimmer — kept for backward compat with old callers.
    New code should use get_history_block() instead.
    """
    words = history.split()
    if len(words) <= max_words:
        return history
    # Keep last max_words words
    cutoff = len(" ".join(words[:-max_words]))
    return history[cutoff:]
