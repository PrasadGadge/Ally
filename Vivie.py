import warnings
warnings.filterwarnings("ignore")

# ── Load .env FIRST — must happen before any module reads os.getenv() ──
# vivie_stt.py reads GROQ_API_KEY at module level. If dotenv loads after
# the import, the key is always empty and Groq STT is silently disabled.
try:
    from dotenv import load_dotenv as _load_dotenv
    _load_dotenv()
except Exception:
    pass

import logging
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)

from log_config import suppress_noise
suppress_noise()

# ==================================================
# Vivie.py — Main Entry Point (UI Integrated)
# ==================================================

import threading
import sys
import random
import atexit
import os as _os
import time

from Automation.internet_check import is_Online
from Features.Alert import Alert
from DATA.DLG_Data import online_dlg, offline_dlg
from main_brain import Vivie
from TextToSpeech.Fast_DF_TTS import speak_blocking
from Automation.Battery import check_plug
from Time_operations.time_monitor import check_Alam
from Vivie_UI import launch_ui
from vivie_core.log_util import warn

_BASE = _os.path.dirname(_os.path.abspath(__file__))
Alarm_path = _os.path.join(_BASE, "alarm_data.txt")
file_path = _os.path.join(_BASE, "schedule.txt")

ran_online_dlg = random.choice(online_dlg)
ran_offline_dlg = random.choice(offline_dlg)


def _on_exit():
    try:
        from memory_core.session_memory import get_session_memory
        get_session_memory().end_session()
        print("[SessionMemory] Session saved on exit.")
    except Exception as exc:
        print(f"[SessionMemory] Exit save failed: {exc}")


atexit.register(_on_exit)


def _safe_call(label, fn, *args, fallback=None, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as exc:
        warn(label, exc)
        return fallback


def _safe_alert(message: str) -> None:
    _safe_call("startup alert", Alert, message)


def _safe_is_online() -> bool:
    return bool(_safe_call("internet check", is_Online, fallback=False))


def _ensure_file(path: str) -> None:
    if not _os.path.exists(path):
        with open(path, "a", encoding="utf-8"):
            pass


def _guarded_thread(label, target, *args):
    def runner():
        _safe_call(label, target, *args)
    return runner


def wish(message: str = ran_online_dlg):
    # Only speak if voice mode is enabled
    import os
    voice_mode = os.getenv("VIVIE_MODE", "chat").lower() == "voice"
    if voice_mode:
        _safe_call("startup greeting", speak_blocking, message)
    _safe_alert(message)


def start_brain_threads():
    # Schedule reminders: proactive_engine only (schedule.txt; see file header)
    threads = [
        threading.Thread(
            target=_guarded_thread("battery monitor", check_plug),
            daemon=True,
            name="vivie-battery",
        ),
        threading.Thread(
            target=_guarded_thread("vivie runtime", Vivie),
            daemon=True,
            name="vivie-runtime",
        ),
        threading.Thread(
            target=_guarded_thread("alarm monitor", check_Alam, Alarm_path),
            daemon=True,
            name="vivie-alarms",
        ),
    ]
    for thread in threads:
        thread.start()
    return threads


def _wait_forever() -> None:
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Vivie...")
        sys.exit(0)


def main(run_forever: bool = True):
    _ensure_file(Alarm_path)

    online = _safe_is_online()
    if online:
        wish(ran_online_dlg)
    else:
        print("[Startup] Internet unavailable; starting Vivie in degraded mode.")
        _safe_alert(ran_offline_dlg)

    start_brain_threads()
    _safe_call("launch ui", launch_ui)

    if run_forever:
        _wait_forever()


if __name__ == "__main__":
    main()
