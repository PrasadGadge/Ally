# voice_dialog.py
# Shared dialog queue used when Vivie needs multi-turn voice input
# (e.g. WhatsApp send flow). listen_loop routes to this queue when
# dialog_active is True instead of the main input_queue.

import queue as _queue

_dialog_queue: _queue.Queue = _queue.Queue()
dialog_active: bool = False


def activate():
    global dialog_active
    _dialog_queue.queue.clear()   # flush stale items
    dialog_active = True


def deactivate():
    global dialog_active
    dialog_active = False
    _dialog_queue.queue.clear()


def put(text: str):
    _dialog_queue.put(text)


def get(timeout: float = 20.0) -> str:
    """Block until user speaks. Raises queue.Empty on timeout."""
    return _dialog_queue.get(timeout=timeout)
