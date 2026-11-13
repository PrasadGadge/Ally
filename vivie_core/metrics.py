"""
Lightweight runtime metrics — request timing and counters (no external deps).
"""

import threading
import time
from collections import deque

_lock = threading.Lock()
_request_times: deque = deque(maxlen=100)
_counts = {"processed": 0, "errors": 0, "stt_empty": 0}


def record_request(duration_sec: float, *, error: bool = False) -> None:
    with _lock:
        _request_times.append(duration_sec)
        _counts["processed"] += 1
        if error:
            _counts["errors"] += 1


def record_stt_empty() -> None:
    with _lock:
        _counts["stt_empty"] += 1


def snapshot() -> dict:
    with _lock:
        times = list(_request_times)
        avg = sum(times) / len(times) if times else 0.0
        return {
            "processed": _counts["processed"],
            "errors": _counts["errors"],
            "stt_empty": _counts["stt_empty"],
            "avg_request_sec": round(avg, 3),
            "samples": len(times),
        }


class RequestTimer:
    """Context manager: with RequestTimer(): ..."""

    def __init__(self):
        self._start = 0.0
        self._error = False

    def __enter__(self):
        self._start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        duration = time.perf_counter() - self._start
        if exc_type is not None:
            self._error = True
        record_request(duration, error=self._error)
        return False
