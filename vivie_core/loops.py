"""Background loops: listen → brain → TTS."""

import time

from Automation.Automation_brain import REDIRECT_PREFIX
from Core_structure.proactive_engine import mark_user_active
from SpeechToText.vivie_stt import listen
from TextToSpeech.Fast_DF_TTS import (
    is_speaking as tts_is_speaking,
    stop_speaking,
    time_since_last_spoke,
)
from TextToSpeech.voice_personality import detect_voice_mood
from vivie_core import state
from vivie_core.settings import POST_SPEAK_COOLDOWN
from vivie_core.log_util import warn
from vivie_core.processor import process_text
from vivie_core.speech import controlled_speak
from vivie_core.ui import update_ui

DUPLICATE_INPUT_WINDOW_SEC = 1.0

# Extra safety cooldown — must be >= POST_SPEAK_COOLDOWN
# Guards against residual system audio right after TTS finishes.
LISTEN_LOOP_COOLDOWN_SEC = max(2.5, POST_SPEAK_COOLDOWN)


def _is_recent_duplicate(text: str, now: float | None = None) -> bool:
    """Suppress immediate STT echo/requeue duplicates without blocking retries."""
    now = time.time() if now is None else now
    return (
        text == state.last_processed
        and now - state.last_processed_at < DUPLICATE_INPUT_WINDOW_SEC
    )


def listen_loop() -> None:
    import voice_dialog

    while True:
        try:
            update_ui("sig_agent_state", "listening...")
            update_ui("sig_listening", True)
            text = listen()
            update_ui("sig_listening", False)

            if not text or not text.strip():
                continue

            mark_user_active()

            # Post-speak cooldown — reject STT input that arrived too
            # soon after TTS finished (prevents self-feedback loop)
            if time_since_last_spoke() < LISTEN_LOOP_COOLDOWN_SEC:
                print(f"[STT] Ignored (post-speak cooldown {LISTEN_LOOP_COOLDOWN_SEC}s): '{text}'")
                continue

            print(f"[QUEUE] Input: {text}")
            if tts_is_speaking():
                print("Interrupting Vivie...")
                stop_speaking()

            if voice_dialog.dialog_active:
                voice_dialog.put(text.strip())
            else:
                state.input_queue.put(text.strip())

        except Exception as exc:
            update_ui("sig_listening", False)
            warn("listen_loop", exc)
            time.sleep(0.2)


def brain_loop() -> None:
    while True:
        try:
            text = state.input_queue.get(timeout=0.2)
            if isinstance(text, str) and text.startswith(REDIRECT_PREFIX):
                text = text[len(REDIRECT_PREFIX):]

            now = time.time()
            if _is_recent_duplicate(text, now):
                continue
            state.last_processed = text
            state.last_processed_at = now

            response = process_text(text)
            if not response:
                continue

            mood = detect_voice_mood(response)
            state.output_queue.put((response, mood))

        except Exception as exc:
            if str(exc):
                warn("brain_loop", exc)


def tts_loop() -> None:
    while True:
        try:
            item = state.output_queue.get(timeout=0.2)
            if isinstance(item, tuple):
                response, intent = item
            else:
                response, intent = item, "chat"

            if not response:
                continue

            controlled_speak(response, intent=intent)

        except Exception as exc:
            if str(exc):
                warn("tts_loop", exc)

