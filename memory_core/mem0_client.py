import json
import logging
import os

try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except Exception:
    load_dotenv = None
    _HAS_DOTENV = False

if _HAS_DOTENV:
    load_dotenv()

# Lazy imports for heavy mem0 SDK
_Mem0Client = None
_HAS_MEM0 = False

def _ensure_mem0():
    global _Mem0Client, _HAS_MEM0
    if _HAS_MEM0:
        return True
    try:
        from mem0 import MemoryClient as _Mem0Client
        _HAS_MEM0 = True
        print("[Mem0Client] mem0 SDK loaded.")
    except Exception as e:
        print(f"[Mem0Client] mem0 SDK unavailable: {e}")
        _HAS_MEM0 = False
    return _HAS_MEM0

LOG = logging.getLogger("vivie.mem0")


class MemoryClient:
    def __init__(self, *args, **kwargs):
        self._client = None
        self._args = args
        self._kwargs = kwargs

    def _ensure_client(self):
        if self._client is None and _ensure_mem0():
            self._client = _Mem0Client(*self._args, **self._kwargs)
        if self._client is None:
            LOG.info("mem0 SDK unavailable — cloud memory disabled")

    def add(self, *args, **kwargs):
        self._ensure_client()
        if self._client is None:
            return None
        try:
            return self._client.add(*args, **kwargs)
        except Exception as exc:
            LOG.warning("mem0 add failed: %s", exc)
            return None

    def search(self, *args, **kwargs):
        self._ensure_client()
        if self._client is None:
            return {"results": []}
        try:
            return self._client.search(*args, **kwargs)
        except Exception as exc:
            LOG.warning("mem0 search failed: %s", exc)
            return {"results": []}


mem0 = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))

user_name = "Boss"


def add_memory():
    messages_formatted = [
        {
            "role": "user",
            "content": "I really like coding."
        },
        {
            "role": "assistant",
            "content": "YAAH it's good."
        },
        {
            "role": "user",
            "content": "I think so too."
        },
        {
            "role": "assistant",
            "content": "What is your favorite song by them?"
        }
    ]

    mem0.add(messages_formatted, user_id="Boss")


def get_memory_by_query():

    query = f"What are {user_name}'s preferences?"
    results = mem0.search(
        query=query,
        filters={
            "user_id": user_name
        }
    )

    memories = [
        {
            "memory": r["memory"],
            "updated_at": r.get("updated_at")
        }
        for r in results["results"]
    ]

    memories_str = json.dumps(memories)
    print(f"Memories: {memories_str}")
    return memories_str

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    add_memory()
    get_memory_by_query()
