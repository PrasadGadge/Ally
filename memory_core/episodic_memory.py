# ==================================================
# episodic_memory.py — Vivie's Experience Memory
# Stores what happened, when, and what worked.
# ==================================================

import json
import os
import threading
from datetime import datetime, date

BASE_DIR       = os.path.dirname(os.path.abspath(__file__))
EPISODES_FILE  = os.path.join(BASE_DIR, "episodes.json")
MAX_EPISODES   = 500
_episodes_lock = threading.Lock()   # FIX: no lock before — concurrent writes corrupted file


# ─────────────────────────────────────────────────
# LOAD
# ─────────────────────────────────────────────────

def _load_episodes() -> list:
    if not os.path.exists(EPISODES_FILE):
        return []
    try:
        with _episodes_lock:
            with open(EPISODES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        return []


# ─────────────────────────────────────────────────
# SAVE
# ─────────────────────────────────────────────────

def _save_episodes(episodes: list):
    try:
        if len(episodes) > MAX_EPISODES:
            episodes = episodes[-MAX_EPISODES:]
        with _episodes_lock:
            with open(EPISODES_FILE, "w", encoding="utf-8") as f:
                json.dump(episodes, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[EpisodicMemory] Save error: {e}")

# ─────────────────────────────────────────────────
# AUTO DETECT REACTION
# ─────────────────────────────────────────────────

def _auto_detect_reaction(user_input: str, vivie_response: str) -> str:
    """
    Automatically detect if response was good or bad
    based on conversation signals — no user input needed.
    """
    user = user_input.lower().strip()

    # ── Explicit positive signals ──────────────────
    positive_signals = [
        "good", "great", "perfect", "correct", "exactly",
        "yes", "right", "nice", "awesome", "thanks",
        "thank you", "well done", "good answer", "that's right",
        "that's correct", "makes sense", "i see", "got it",
        "understood", "helpful", "amazing", "brilliant"
    ]
    if any(w in user for w in positive_signals):
        return "positive"

    # ── Explicit negative signals ──────────────────
    negative_signals = [
        "wrong", "incorrect", "no that's wrong", "not right",
        "bad answer", "that's wrong", "you're wrong",
        "not helpful", "useless", "terrible", "awful",
        "stop", "that's not what i asked", "you misunderstood"
    ]
    if any(w in user for w in negative_signals):
        return "negative"

    # ── Response quality signals ───────────────────
    response = vivie_response.lower()

    # Good response indicators
    if len(vivie_response.split()) > 30:
        return "positive"   # detailed response = likely good

    # Short vague responses = likely neutral/negative
    vague_responses = [
        "i don't know", "i'm not sure", "i cannot",
        "i don't have", "unfortunately", "i apologize"
    ]
    if any(w in response for w in vague_responses):
        return "negative"

    return "neutral"


# ─────────────────────────────────────────────────
# STORE EPISODE
# ─────────────────────────────────────────────────

import hashlib

_episodes_collection = None
_collection_lock = threading.Lock()

def _get_episodes_collection():
    global _episodes_collection
    if _episodes_collection is not None:
        return _episodes_collection
    try:
        from knowledge_core.chroma_manager import get_chroma_manager, ChromaManager
        mgr = get_chroma_manager()
        if isinstance(mgr, ChromaManager) and mgr.client is not None:
            with _collection_lock:
                if _episodes_collection is None:
                    _episodes_collection = mgr.client.get_or_create_collection(
                        name="vivie_episodes",
                        embedding_function=mgr.embed_fn,
                        metadata={"hnsw:space": "cosine"}
                    )
    except Exception as e:
        print(f"[EpisodicMemory] Chroma collection init failed: {e}")
    return _episodes_collection


def _upsert_one_chroma(ep: dict, collection):
    try:
        doc_id = hashlib.md5(f"{ep.get('user_input', '')}||{ep.get('date', '')}||{ep.get('time', '')}".encode()).hexdigest()
        doc_text = f"{ep.get('user_input', '')} {ep.get('topic', '')} {ep.get('intent', '')}"
        meta = {
            "date": str(ep.get("date", "")),
            "time": str(ep.get("time", "")),
            "user_input": str(ep.get("user_input", "")),
            "vivie_response": str(ep.get("vivie_response", ""))[:300],
            "intent": str(ep.get("intent", "general")),
            "reaction": str(ep.get("reaction", "neutral")),
            "topic": str(ep.get("topic", "general")),
            "response_length": int(ep.get("response_length", 0))
        }
        collection.upsert(
            ids=[doc_id],
            documents=[doc_text],
            metadatas=[meta]
        )
    except Exception as e:
        print(f"[EpisodicMemory] Chroma upsert one error: {e}")


def _ensure_chroma_sync(episodes: list, collection) -> bool:
    try:
        count = collection.count()
        if count == len(episodes):
            return True
        
        ids = []
        documents = []
        metadatas = []
        for ep in episodes:
            doc_id = hashlib.md5(f"{ep.get('user_input', '')}||{ep.get('date', '')}||{ep.get('time', '')}".encode()).hexdigest()
            doc_text = f"{ep.get('user_input', '')} {ep.get('topic', '')} {ep.get('intent', '')}"
            ids.append(doc_id)
            documents.append(doc_text)
            
            meta = {
                "date": str(ep.get("date", "")),
                "time": str(ep.get("time", "")),
                "user_input": str(ep.get("user_input", "")),
                "vivie_response": str(ep.get("vivie_response", ""))[:300],
                "intent": str(ep.get("intent", "general")),
                "reaction": str(ep.get("reaction", "neutral")),
                "topic": str(ep.get("topic", "general")),
                "response_length": int(ep.get("response_length", 0))
            }
            metadatas.append(meta)
            
        if ids:
            for i in range(0, len(ids), 100):
                collection.upsert(
                    ids=ids[i:i+100],
                    documents=documents[i:i+100],
                    metadatas=metadatas[i:i+100]
                )
        return True
    except Exception as e:
        print(f"[EpisodicMemory] Chroma sync error: {e}")
        return False


# ─────────────────────────────────────────────────
# STORE EPISODE
# ─────────────────────────────────────────────────

def store_episode(
    user_input:     str,
    vivie_response: str,
    intent:         str = "general",
    reaction:       str = "neutral"
) -> bool:
    """
    Store a full experience episode.
    FIX: added deduplication — same topic + same day won't be stored again.
    Prevents 500 episodes of "what is machine learning" piling up.
    """
    try:
        episodes = _load_episodes()

        topic         = _extract_topic(user_input)
        today         = datetime.now().strftime("%Y-%m-%d")
        auto_reaction = _auto_detect_reaction(user_input, vivie_response)

        # ── Deduplication ──────────────────────────────────────────────────
        # If an episode with the same topic was already stored today,
        # just update its reaction rather than adding a duplicate.
        for ep in reversed(episodes[-20:]):   # check last 20 only — fast
            if ep.get("date") == today and ep.get("topic") == topic:
                ep["reaction"] = auto_reaction
                ep["vivie_response"] = vivie_response[:300]
                _save_episodes(episodes)
                
                # Update in Chroma if available
                collection = _get_episodes_collection()
                if collection is not None:
                    _upsert_one_chroma(ep, collection)
                return True   # updated, not duplicated

        episode = {
            "date":            today,
            "time":            datetime.now().strftime("%H:%M"),
            "user_input":      user_input,
            "vivie_response":  vivie_response[:300],
            "intent":          intent,
            "reaction":        auto_reaction,
            "topic":           topic,
            "response_length": len(vivie_response.split())
        }

        episodes.append(episode)
        _save_episodes(episodes)
        
        # Add to Chroma if available
        collection = _get_episodes_collection()
        if collection is not None:
            _upsert_one_chroma(episode, collection)
        return True

    except Exception as e:
        print(f"[EpisodicMemory] Store error: {e}")
        return False


# ─────────────────────────────────────────────────
# RETRIEVE RELEVANT EPISODES
# ─────────────────────────────────────────────────

def retrieve_episodes(query: str, top_k: int = 3) -> list:
    """
    Find past episodes relevant to current query.
    Queries ChromaDB for semantic similarity if available.
    Falls back to keyword overlap if Chroma unavailable.
    """
    try:
        episodes = _load_episodes()
        if not episodes:
            return []

        collection = _get_episodes_collection()
        if collection is not None:
            # Sync episodes list to Chroma collection
            _ensure_chroma_sync(episodes, collection)
            
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            retrieved = []
            if results and "metadatas" in results and results["metadatas"]:
                for meta in results["metadatas"][0]:
                    if meta:
                        retrieved.append(meta)
            return retrieved

    except Exception as e:
        print(f"[EpisodicMemory] Chroma retrieve error: {e} — falling back to keyword")

    # Keyword fallback
    try:
        query_words = set(query.lower().split())

        scored = []
        for ep in episodes:
            ep_text  = f"{ep['user_input']} {ep['topic']} {ep['intent']}".lower()
            ep_words = set(ep_text.split())
            overlap  = len(query_words & ep_words)
            if overlap > 0:
                scored.append((overlap, ep))

        # Sort by relevance, return top_k
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored[:top_k]]

    except Exception as e:
        print(f"[EpisodicMemory] Fallback retrieve error: {e}")
        return []


# ─────────────────────────────────────────────────
# FORMAT FOR PROMPT INJECTION
# ─────────────────────────────────────────────────

def get_episode_context(query: str, top_k: int = 2) -> str:
    """
    Returns formatted episode context ready to inject into LLM prompt.
    Only returns something if relevant episodes found.
    """
    try:
        episodes = retrieve_episodes(query, top_k=top_k)
        if not episodes:
            return ""

        lines = ["Past relevant experiences:"]
        for ep in episodes:
            lines.append(
                f"- On {ep['date']} user asked about '{ep['topic']}' "
                f"(intent: {ep['intent']}). "
                f"Response was {ep['reaction']}."
            )

        return "\n".join(lines)

    except Exception as e:
        print(f"[EpisodicMemory] Context error: {e}")
        return ""


# ─────────────────────────────────────────────────
# UPDATE REACTION (call when user says good/wrong)
# ─────────────────────────────────────────────────

def update_last_reaction(reaction: str):
    """
    Update the reaction of the most recent episode.
    Call this when user says 'good answer' or 'wrong' etc.

    reaction: 'positive' or 'negative'
    """
    try:
        episodes = _load_episodes()
        if not episodes:
            return

        episodes[-1]["reaction"] = reaction
        _save_episodes(episodes)
        print(f"[EpisodicMemory] Last episode marked: {reaction}")

    except Exception as e:
        print(f"[EpisodicMemory] Update reaction error: {e}")


# ─────────────────────────────────────────────────
# STATS (useful for debugging)
# ─────────────────────────────────────────────────

def get_memory_stats() -> dict:
    """Returns basic stats about episodic memory."""
    try:
        episodes = _load_episodes()
        if not episodes:
            return {"total": 0}

        topics    = [ep["topic"]    for ep in episodes]
        reactions = [ep["reaction"] for ep in episodes]

        return {
            "total":     len(episodes),
            "positive":  reactions.count("positive"),
            "negative":  reactions.count("negative"),
            "neutral":   reactions.count("neutral"),
            "top_topics": _top_items(topics, 3)
        }
    except Exception:
        return {"total": 0}


# ─────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────

def _extract_topic(text: str) -> str:
    """Extract short topic label from user input."""
    stop_words = {
        "what", "how", "why", "when", "where", "who",
        "is", "are", "the", "a", "an", "do", "does",
        "can", "could", "tell", "me", "about", "please",
        "vivie", "i", "my", "you", "your"
    }
    words = [
        w for w in text.lower().split()
        if w not in stop_words and len(w) > 2
    ]
    return " ".join(words[:4]) if words else "general"


def _top_items(items: list, n: int) -> list:
    """Return top n most frequent items."""
    from collections import Counter
    return [item for item, _ in Counter(items).most_common(n)]


# ─────────────────────────────────────────────────
# PUBLIC ACCESSORS — use these outside this module
# (avoids leaking the private _load_episodes symbol)
# ─────────────────────────────────────────────────

def load_episodes() -> list:
    """
    Public read of the full episodes list.
    Use this instead of the private _load_episodes().
    """
    return _load_episodes()


def get_episode_count() -> int:
    """
    Returns the total number of stored episodes.
    Cheaper than load_episodes() when you only need the count.
    """
    return get_memory_stats().get("total", 0)