# ==================================================
# main_brain.py — compatibility shim (Vivie 2.0)
# Implementation: vivie_core/
# ==================================================

from vivie_core.config import POST_SPEAK_COOLDOWN
from vivie_core.loops import brain_loop, listen_loop, tts_loop
from vivie_core.processor import process_text
from vivie_core.runtime import start_vivie
from vivie_core.speech import controlled_speak
from vivie_core.state import input_queue, output_queue, processing_lock
from vivie_core.ui import update_ui

# Backward-compatible name used by Vivie.py and tests
Vivie = start_vivie

__all__ = [
    "Vivie",
    "start_vivie",
    "process_text",
    "input_queue",
    "output_queue",
    "processing_lock",
    "POST_SPEAK_COOLDOWN",
    "listen_loop",
    "brain_loop",
    "tts_loop",
    "controlled_speak",
    "update_ui",
]
