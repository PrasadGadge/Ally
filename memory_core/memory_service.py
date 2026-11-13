"""
Memory service — mem0 cloud + local episodic memory.
Production: timeouts, cache bounds, deduplicated stores, structured logging.
"""

import hashlib
import logging
import threading
import time
import atexit
from concurrent.futures import ThreadPoolExecutor

from memory_core.mem0_client import MemoryClient
from memory_core.Chatcontext import ChatContext
from memory_core.episodic_memory import store_episode, get_episode_context

try:
    from vivie_core.settings import (
        MEMORY_CACHE_MAX_ENTRIES,
        MEMORY_CACHE_TTL,
        MEMORY_RETRIEVAL_TIMEOUT,
        MEMORY_STORE_DEDUP_SECONDS,
        has_mem0,
    )
except ImportError:
    MEMORY_RETRIEVAL_TIMEOUT = 3.0
    MEMORY_CACHE_TTL = 8.0
    MEMORY_CACHE_MAX_ENTRIES = 64
    MEMORY_STORE_DEDUP_SECONDS = 30.0

    def has_mem0():
        return False

LOG = logging.getLogger("vivie.memory")

mem0 = MemoryClient()
USER_ID = "Boss"
_store_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="vivie-mem-store")
atexit.register(_store_executor.shutdown, wait=True)

_retrieval_cache: dict = {}
_retrieval_cache_lock = threading.Lock()
_recent_store_hashes: dict[str, float] = {}
_recent_store_lock = threading.Lock()

_LOW_VALUE_PREFIXES = (
    "hey", "hi", "hello", "open", "close", "play", "stop",
    "scroll", "pause", "resume", "set alarm", "tell me at",
    "new tab", "go back", "refresh", "mute", "unmute",
    "search in google", "volume",
)
_LOW_VALUE_EXACT = {
    "yes", "no", "ok", "okay", "sure", "thanks", "thank you",
    "got it", "alright", "bye", "good", "great", "nice", "fine",
    "cancel", "never mind", "stop",
}


def get_health() -> dict:
    return {
        "mem0_cloud": has_mem0(),
        "cache_entries": len(_retrieval_cache),
        "retrieval_timeout_s": MEMORY_RETRIEVAL_TIMEOUT,
    }


def _get_cached(query: str):
    with _retrieval_cache_lock:
        entry = _retrieval_cache.get(query)
        if entry and (time.time() - entry["ts"]) < MEMORY_CACHE_TTL:
            return entry["result"]
    return None


def _set_cached(query: str, result) -> None:
    with _retrieval_cache_lock:
        if len(_retrieval_cache) >= MEMORY_CACHE_MAX_ENTRIES:
            now = time.time()
            stale = [k for k, v in _retrieval_cache.items() if now - v["ts"] > MEMORY_CACHE_TTL]
            for k in stale:
                del _retrieval_cache[k]
            if len(_retrieval_cache) >= MEMORY_CACHE_MAX_ENTRIES:
                oldest = min(_retrieval_cache, key=lambda k: _retrieval_cache[k]["ts"])
                del _retrieval_cache[oldest]
        _retrieval_cache[query] = {"result": result, "ts": time.time()}


def _is_worth_storing(user_input: str) -> bool:
    t = user_input.strip().lower()
    if t in _LOW_VALUE_EXACT:
        return False
    if any(t.startswith(p) for p in _LOW_VALUE_PREFIXES):
        return False
    if len(t.split()) < 3:
        return False
    return True


def _is_duplicate_store(user_input: str, assistant_response: str) -> bool:
    key = hashlib.sha256(
        f"{user_input.strip().lower()}|{assistant_response.strip()[:200]}".encode()
    ).hexdigest()
    now = time.time()
    with _recent_store_lock:
        last = _recent_store_hashes.get(key)
        if last and (now - last) < MEMORY_STORE_DEDUP_SECONDS:
            return True
        _recent_store_hashes[key] = now
        if len(_recent_store_hashes) > 200:
            cutoff = now - MEMORY_STORE_DEDUP_SECONDS
            stale = [k for k, v in _recent_store_hashes.items() if v < cutoff]
            for k in stale:
                del _recent_store_hashes[k]
    return False


def retrieve_memory(query: str) -> ChatContext:
    cached = _get_cached(query)
    if cached is not None:
        return cached

    ctx = ChatContext()
    result_holder = [None]
    error_holder = [None]

    def fetch():
        try:
            result_holder[0] = mem0.search(
                query=query,
                filters={"user_id": USER_ID},
            )
        except Exception as exc:
            error_holder[0] = exc

    t = threading.Thread(target=fetch, daemon=True, name="vivie-mem-fetch")
    t.start()
    t.join(timeout=MEMORY_RETRIEVAL_TIMEOUT)

    if t.is_alive():
        LOG.warning("retrieve_memory timeout (%.1fs)", MEMORY_RETRIEVAL_TIMEOUT)
        return ctx

    if error_holder[0]:
        LOG.warning("retrieve_memory error: %s", error_holder[0])
        return ctx

    results = result_holder[0]
    try:
        if results and results.get("results"):
            memories = [r["memory"] for r in results["results"]]
            import json
            ctx.add("system", f"Relevant long-term memory about the user: {json.dumps(memories)}")

        episode_ctx = get_episode_context(query)
        if episode_ctx:
            ctx.add("system", episode_ctx)
    except Exception as exc:
        LOG.warning("retrieve_memory parse error: %s", exc)

    _set_cached(query, ctx)
    return ctx


def store_memory(user_input: str, assistant_response: str, intent: str = "general") -> None:
    if _is_duplicate_store(user_input, assistant_response):
        LOG.debug("skip duplicate store")
        return

    def _store():
        try:
            if _is_worth_storing(user_input) and has_mem0():
                mem0.add(
                    [
                        {"role": "user", "content": user_input},
                        {"role": "assistant", "content": assistant_response},
                    ],
                    user_id=USER_ID,
                )
            store_episode(
                user_input=user_input,
                vivie_response=assistant_response,
                intent=intent,
            )
        except Exception as exc:
            LOG.warning("store_memory error: %s", exc)

    _store_executor.submit(_store)
