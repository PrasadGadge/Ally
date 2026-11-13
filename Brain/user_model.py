# ==================================================
# Brain/user_model.py  —  Vivie's User World Model
#
# UPGRADE 6: Confidence-scored, timestamped, decaying facts
#
# Facts now stored with:
#   - confidence (0.0-1.0)
#   - last_seen date
#   - times_mentioned count
#   - source ("explicit" | "extracted")
#
# Staleness decay: facts not mentioned in 30 days get
# lower weight in context string (still stored, but
# deprioritized in the prompt).
#
# Backward compatible: still reads old flat-list format
# and upgrades it automatically on first load.
# ==================================================

from __future__ import annotations

import json
import os
import threading
import datetime
from pathlib import Path


# ─────────────────────────────────────────────────
# STORAGE
# ─────────────────────────────────────────────────

_BASE_DIR   = Path(__file__).parent.parent
_MODEL_FILE = _BASE_DIR / "data" / "user_model.json"

_DEFAULT_MODEL: dict = {
    "name":               {"value": "Boss", "confidence": 0.5, "source": "default"},
    "role":               {"value": "", "confidence": 0.0, "source": "default"},
    "current_projects":   [],
    "current_goals":      [],
    "interests":          [],
    "recent_topics":      [],
    "known_facts":        [],      # list of {"fact": str, "confidence": float, "last_seen": str, "times_mentioned": int, "source": str}
    "communication_style": "direct, technical, informal",
    "working_pattern":    {},
    "last_updated":       "",
}

_STALE_DAYS = 30       # facts older than this get deprioritized
_PASSIVE_UPDATE_EVERY_N = 4


# ─────────────────────────────────────────────────
# MODULE STATE
# ─────────────────────────────────────────────────

_model:       dict           = {}
_model_lock:  threading.Lock = threading.Lock()
_update_lock: threading.Lock = threading.Lock()
_turn_counter: int           = 0
_loaded:      bool           = False


# ─────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────

def _today() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d")


def _days_since(date_str: str) -> int:
    """Days since a date string (YYYY-MM-DD). Returns 0 if invalid."""
    try:
        d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
        return (datetime.date.today() - d).days
    except Exception:
        return 0


def _upgrade_field(val, default_confidence: float = 0.5) -> dict:
    """Upgrade a plain string field to confidence dict if needed."""
    if isinstance(val, dict) and "value" in val:
        return val
    return {"value": str(val) if val else "", "confidence": default_confidence, "source": "legacy"}


def _upgrade_fact(fact) -> dict:
    """Upgrade a plain string fact to a scored fact dict."""
    if isinstance(fact, dict) and "fact" in fact:
        return fact
    return {
        "fact":            str(fact),
        "confidence":      0.7,
        "last_seen":       _today(),
        "times_mentioned": 1,
        "source":          "legacy",
    }


# ─────────────────────────────────────────────────
# LOAD / SAVE
# ─────────────────────────────────────────────────

def _load() -> dict:
    global _loaded
    if _loaded:
        return _model
    _MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        if _MODEL_FILE.exists():
            with open(_MODEL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            merged = _DEFAULT_MODEL.copy()
            merged.update(data)
            # Upgrade legacy flat fields
            merged["name"] = _upgrade_field(merged.get("name", "Boss"), 0.5)
            merged["role"] = _upgrade_field(merged.get("role", ""),   0.0)
            merged["known_facts"] = [_upgrade_fact(f) for f in merged.get("known_facts", [])]
            with _model_lock:
                _model.clear()
                _model.update(merged)
        else:
            with _model_lock:
                _model.update(_DEFAULT_MODEL.copy())
    except Exception as e:
        print(f"[UserModel] Load error: {e}")
        with _model_lock:
            _model.update(_DEFAULT_MODEL.copy())
    _loaded = True
    return _model


def _save():
    try:
        _MODEL_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(_MODEL_FILE) + ".tmp"
        with _model_lock:
            snapshot = dict(_model)
        snapshot["last_updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(_MODEL_FILE))
    except Exception as e:
        print(f"[UserModel] Save error: {e}")


# ─────────────────────────────────────────────────
# LLM EXTRACTOR  (Tier 0 — fast, cheap)
# ─────────────────────────────────────────────────

_EXTRACT_PROMPT = """You are a fact extractor. Read this conversation snippet and extract any personal facts about the user (Boss).

Conversation:
User: {user_input}
Vivie: {response}

Return ONLY valid JSON in this exact format (empty lists if nothing found):
{{
  "name":             "",
  "role":             "",
  "new_projects":     [],
  "new_goals":        [],
  "new_interests":    [],
  "new_facts":        [],
  "topic":            ""
}}

Rules:
- Only extract facts explicitly stated, never infer
- "name" only if user states their name
- "role" only if user states job/school/title
- "topic" = main subject of the conversation (1-4 words)
- Return empty strings/lists if nothing found
- No explanation, JSON only"""


def _extract_facts(user_input: str, response: str) -> dict | None:
    try:
        from Brain.tiered_brain import api_generate_response
        prompt = _EXTRACT_PROMPT.format(
            user_input=user_input[:400],
            response=response[:400],
        )
        raw = api_generate_response(prompt, forced_tier=0)
        if not raw:
            return None
        clean = raw.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except Exception as e:
        print(f"[UserModel] Extract error: {e}")
        return None


# ─────────────────────────────────────────────────
# MODEL MERGE  (applies extracted facts)
# ─────────────────────────────────────────────────

def _update_fact(facts_list: list, new_fact: str, confidence: float, source: str) -> list:
    """Add or update a fact in the scored facts list."""
    today = _today()
    for f in facts_list:
        if isinstance(f, dict) and f.get("fact", "").lower() == new_fact.lower():
            # Update existing fact
            f["times_mentioned"] = f.get("times_mentioned", 1) + 1
            f["last_seen"]       = today
            f["confidence"]      = min(1.0, f.get("confidence", confidence) + 0.05)
            return facts_list
    # New fact
    facts_list.append({
        "fact":            new_fact,
        "confidence":      confidence,
        "last_seen":       today,
        "times_mentioned": 1,
        "source":          source,
    })
    return facts_list


def _merge(facts: dict, source: str = "extracted"):
    with _model_lock:
        today = _today()

        if facts.get("name") and facts["name"].strip():
            current_name = _model.get("name", {})
            if isinstance(current_name, dict):
                if current_name.get("value", "Boss") in ("Boss", ""):
                    _model["name"] = {"value": facts["name"].strip().capitalize(),
                                      "confidence": 0.9, "source": source}
            else:
                _model["name"] = {"value": facts["name"].strip().capitalize(),
                                  "confidence": 0.9, "source": source}

        if facts.get("role") and facts["role"].strip():
            _model["role"] = {"value": facts["role"].strip(),
                              "confidence": 0.85, "source": source}

        for project in facts.get("new_projects", []):
            p = project.strip()
            if p and p not in _model["current_projects"]:
                _model["current_projects"].append(p)
                _model["current_projects"] = _model["current_projects"][-8:]

        for goal in facts.get("new_goals", []):
            g = goal.strip()
            if g and g not in _model["current_goals"]:
                _model["current_goals"].append(g)
                _model["current_goals"] = _model["current_goals"][-6:]

        for interest in facts.get("new_interests", []):
            i = interest.strip()
            if i and i not in _model["interests"]:
                _model["interests"].append(i)
                _model["interests"] = _model["interests"][-10:]

        for fact in facts.get("new_facts", []):
            f = fact.strip()
            if f:
                _model["known_facts"] = _update_fact(
                    _model.get("known_facts", []), f, 0.75, source
                )
                _model["known_facts"] = _model["known_facts"][-20:]

        if facts.get("topic") and facts["topic"].strip():
            topic = facts["topic"].strip()
            topics = _model.get("recent_topics", [])
            if topic not in topics:
                topics.append(topic)
            _model["recent_topics"] = topics[-12:]


# ─────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────

def get_context_string() -> str:
    """
    Returns a compact context block for injection into every system prompt.

    Confidence-weighted: high-confidence facts always included;
    stale facts (>30 days unseen) marked with [older] and deprioritized.
    Pure read — zero latency.
    """
    _load()
    with _model_lock:
        m = dict(_model)

    parts = []
    today = datetime.date.today()

    # Name and role
    name_data = m.get("name", {})
    if isinstance(name_data, dict):
        name = name_data.get("value", "Boss") or "Boss"
    else:
        name = str(name_data) or "Boss"

    role_data = m.get("role", {})
    if isinstance(role_data, dict):
        role = role_data.get("value", "")
    else:
        role = str(role_data) if role_data else ""

    parts.append(f"User: {name} ({role})" if role else f"User: {name}")

    if m.get("current_projects"):
        parts.append("Projects: " + ", ".join(m["current_projects"][-3:]))

    if m.get("current_goals"):
        parts.append("Goals: " + ", ".join(m["current_goals"][-2:]))

    if m.get("recent_topics"):
        parts.append("Recent topics: " + ", ".join(m["recent_topics"][-5:]))

    if m.get("interests"):
        parts.append("Interests: " + ", ".join(m["interests"][:4]))

    if m.get("communication_style"):
        parts.append(f"Style: {m['communication_style']}")

    # Confidence-weighted facts
    facts = m.get("known_facts", [])
    if facts:
        # Sort: high-confidence and recent first
        def _fact_score(f):
            if isinstance(f, dict):
                conf   = f.get("confidence", 0.5)
                days   = _days_since(f.get("last_seen", _today()))
                staleness = max(0, 1.0 - (days / _STALE_DAYS))
                return conf * 0.7 + staleness * 0.3
            return 0.3

        sorted_facts = sorted(facts, key=_fact_score, reverse=True)
        high_conf  = []
        lower_conf = []
        for f in sorted_facts[:6]:
            if isinstance(f, dict):
                text     = f.get("fact", "")
                days     = _days_since(f.get("last_seen", _today()))
                conf     = f.get("confidence", 0.5)
                is_stale = days > _STALE_DAYS
                if conf >= 0.7 and not is_stale:
                    high_conf.append(text)
                else:
                    label = "[older] " if is_stale else ""
                    lower_conf.append(f"{label}{text}")
            elif isinstance(f, str):
                high_conf.append(f)

        if high_conf:
            parts.append("Known (high confidence): " + "; ".join(high_conf[:3]))
        if lower_conf:
            parts.append("Known (lower confidence): " + "; ".join(lower_conf[:2]))

    return "\n".join(parts)


def update_async(user_input: str, response: str):
    """
    Passive background update — called after every conversation turn.
    Runs in a daemon thread, never blocks the pipeline.
    Skips every N turns to avoid hammering Tier 0.
    """
    global _turn_counter
    _turn_counter += 1
    if _turn_counter % _PASSIVE_UPDATE_EVERY_N != 0:
        return

    def _do():
        _load()
        with _update_lock:
            facts = _extract_facts(user_input, response)
            if facts:
                _merge(facts, source="extracted")
                _save()

    threading.Thread(target=_do, daemon=True).start()


def update_explicit(text: str):
    """
    Explicit update — triggered when user says 'Vivie, remember...'
    Stored with high confidence (0.95) immediately.
    """
    def _direct_fact(raw: str) -> str:
        return (
            raw.lower()
            .replace("vivie", "")
            .replace("remember", "")
            .replace("that", "")
            .replace("this", "")
            .replace("please", "")
            .strip()
        )

    def _do():
        _load()
        with _update_lock:
            clean = _direct_fact(text)
            if clean:
                with _model_lock:
                    _model["known_facts"] = _update_fact(
                        _model.get("known_facts", []),
                        clean,
                        confidence=0.95,
                        source="explicit",
                    )
                    _model["known_facts"] = _model["known_facts"][-20:]
            _save()
            print(f"[UserModel] Explicit update stored (conf=0.95): {text[:60]}")

    threading.Thread(target=_do, daemon=True).start()


def get_model_snapshot() -> dict:
    """Returns a copy of the current model for inspection."""
    _load()
    with _model_lock:
        return dict(_model)


def reset_model():
    """Reset to defaults — for testing only."""
    with _model_lock:
        _model.clear()
        _model.update(_DEFAULT_MODEL.copy())
    _save()
