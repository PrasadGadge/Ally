"""TTS output — controlled speak and streaming."""

import vivie_core.state as state
from Brain.cl_brain import Main_Brain_Stream
from TextToSpeech.Fast_DF_TTS import speak_blocking
from vivie_core import text as text_util
from vivie_core.ui import update_ui
from voice_state import set_speaking


def controlled_speak(text: str, intent: str = "chat") -> None:
    if not state.VIVIE_ACTIVE:
        return

    update_ui("sig_agent_state", "Speaking...")
    update_ui("sig_speaking_state", True)
    set_speaking(True)

    try:
        clean = text_util.remove_emojis_for_speech(text)
        sentences = [s.strip() for s in clean.split(". ") if s.strip()]
        for sentence in sentences:
            if not state.VIVIE_ACTIVE:
                break
            speak_blocking(sentence, intent=intent)
    except Exception as exc:
        from vivie_core.log_util import error
        error("TTS execution", exc)
    finally:
        set_speaking(False)
        update_ui("sig_speaking_state", False)
        update_ui("sig_agent_state", "Standby")


def speak_stream(prompt: str, intent: str = "chat") -> None:
    if not state.VIVIE_ACTIVE:
        return

    update_ui("sig_agent_state", "Speaking...")
    update_ui("sig_speaking_state", True)
    set_speaking(True)

    def on_sentence(sentence: str) -> None:
        if not state.VIVIE_ACTIVE:
            return
        clean = text_util.remove_emojis_for_speech(sentence)
        if clean.strip():
            speak_blocking(clean, intent=intent)

    try:
        full_response = Main_Brain_Stream(prompt, on_sentence=on_sentence)
        if full_response:
            update_ui("sig_vivie_message", full_response)
    except Exception as exc:
        from vivie_core.log_util import error
        error("stream TTS", exc)
    finally:
        set_speaking(False)
        update_ui("sig_speaking_state", False)
        update_ui("sig_agent_state", "Standby")
