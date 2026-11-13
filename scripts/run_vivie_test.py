#!/usr/bin/env python3
"""
Headless Vivie test harness — start Vivie runtime (patched) and simulate six phrases.
"""
import os
import sys
import time
import queue
import threading
import traceback

print("[TEST] Starting headless Vivie test harness")

# Load .env where available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Ensure working directory is project root
try:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root)
except Exception:
    pass
# Ensure project root is on sys.path (when running script from scripts/)
try:
    if root not in sys.path:
        sys.path.insert(0, root)
except Exception:
    pass

# Shared test control and capture
stop_event = threading.Event()
ui_signals = []
tts_outputs = []

# Patch vivie_core.ui.update_ui to capture UI signals
try:
    import vivie_core.ui as ui_mod
    orig_update_ui = ui_mod.update_ui

    def patched_update_ui(signal_name, *args, **kwargs):
        try:
            print(f"[UI] {signal_name} {args}")
        except Exception:
            pass
        try:
            ui_signals.append((signal_name, args))
        except Exception:
            pass
        try:
            return orig_update_ui(signal_name, *args, **kwargs)
        except Exception as e:
            print(f"[TEST] update_ui error: {e}")

    ui_mod.update_ui = patched_update_ui
    print("[TEST] Patched vivie_core.ui.update_ui to capture UI signals")
except Exception as e:
    print("[TEST] Could not patch update_ui:", e)
    traceback.print_exc()

# Patch listen_loop + tts_loop to avoid audio and capture outputs
try:
    import vivie_core.loops as loops_mod

    def dummy_listen_loop():
        print("[TEST] dummy listen_loop started (no mic)")
        while not stop_event.is_set():
            time.sleep(0.2)
        print("[TEST] dummy listen_loop exiting")

    def patched_tts_loop():
        import time as _t
        try:
            from vivie_core import state
            print("[TEST] patched tts_loop started (printing responses)")
            while not stop_event.is_set():
                try:
                    item = state.output_queue.get(timeout=0.2)
                except Exception:
                    _t.sleep(0.05)
                    continue
                if isinstance(item, tuple):
                    response, intent = item
                else:
                    response, intent = item, "chat"
                if response:
                    print(f"[TTS] {response}  (intent={intent})")
                    try:
                        tts_outputs.append((response, intent))
                    except Exception:
                        pass
            # Drain remaining
            try:
                while True:
                    item = state.output_queue.get_nowait()
                    if isinstance(item, tuple):
                        response, intent = item
                    else:
                        response, intent = item, "chat"
                    if response:
                        print(f"[TTS] {response}  (intent={intent})")
                        tts_outputs.append((response, intent))
            except Exception:
                pass
        except Exception as e:
            print("[TEST] patched_tts_loop error:", e)
        print("[TEST] patched tts_loop exiting")

    loops_mod.listen_loop = dummy_listen_loop
    loops_mod.tts_loop = patched_tts_loop
    print("[TEST] Patched listen_loop and tts_loop to avoid audio")
except Exception as e:
    print("[TEST] Could not patch loops:", e)
    traceback.print_exc()

# Patch TTS speak functions to avoid sounddevice usage
try:
    import TextToSpeech.Fast_DF_TTS as tts_mod

    def fake_speak_blocking(text, intent="chat"):
        try:
            print(f"[TTS-blocking] {text}")
            tts_outputs.append((text, intent))
        except Exception:
            pass
        return True

    def fake_speak(text, intent="chat"):
        try:
            print(f"[TTS] queued {text}")
            tts_outputs.append((text, intent))
        except Exception:
            pass
        return True

    tts_mod.speak_blocking = fake_speak_blocking
    tts_mod.speak = fake_speak
    print("[TEST] Patched Fast_DF_TTS.speak/speak_blocking")
except Exception as e:
    print("[TEST] Could not patch TTS speak:", e)
    traceback.print_exc()
else:
    # Also replace any already-imported module-level references to speak/speak_blocking
    try:
        for _name, _mod in list(sys.modules.items()):
            try:
                if hasattr(_mod, "speak_blocking"):
                    setattr(_mod, "speak_blocking", fake_speak_blocking)
                if hasattr(_mod, "speak"):
                    setattr(_mod, "speak", fake_speak)
            except Exception:
                continue
        print("[TEST] Replaced existing module references to speak/speak_blocking")
    except Exception as e:
        print("[TEST] Could not replace existing module references:", e)
        traceback.print_exc()

# Import runtime (after patches)
try:
    import vivie_core.runtime as runtime
    import vivie_core.state as state
    print("[TEST] vivie_core.runtime imported")
except Exception as e:
    print("[TEST] Import runtime failed:", e)
    traceback.print_exc()
    sys.exit(1)

# Start runtime in background thread
def run_runtime():
    try:
        runtime.start_vivie()
    except Exception:
        print("[TEST] start_vivie raised exception")
        traceback.print_exc()

rt = threading.Thread(target=run_runtime, daemon=True, name="test-runtime")
rt.start()

print("[TEST] Waiting 10 seconds for Vivie to initialize...")
# Wait for startup logs and UI emits
time.sleep(10)

# Define tests
tests = [
    ("hey vivie", "Expect: 'Hey Boss, I am listening.'"),
    ("what is 25 plus 75", "Expect: math answer"),
    ("research history", "Expect: Lists past research"),
    ("knowledge map", "Expect: Shows knowledge graph/connections"),
    ("what is machine learning", "Expect: Normal LLM answer"),
    ("who is elon musk", "Expect: Normal answer"),
]

results = []

for idx, (phrase, note) in enumerate(tests, start=1):
    print(f"[TEST] ({idx}) Sending: {phrase}  -> {note}")
    try:
        state.input_queue.put(phrase)
    except Exception as e:
        print("[TEST] Failed to enqueue input:", e)
    # Wait a short time to allow processing and TTS print
    time.sleep(6)
    print(f"[TEST] ({idx}) Done waiting for: {phrase}")
    results.append((phrase, "sent"))

print("[TEST] All tests sent. Waiting 3s for final logs...")
time.sleep(3)
print("[TEST] Test harness complete. Exiting.")
