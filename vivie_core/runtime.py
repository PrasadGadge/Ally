"""Vivie runtime startup — engines, background services, worker threads."""

import datetime
import os
import threading
import time

# Lazy imports to avoid blocking initialization
from Vivie_UI import start_websocket_server
from vivie_core.engines import intent_engine, planner
from vivie_core.loops import brain_loop, listen_loop, tts_loop
from vivie_core.log_util import LOG, configure, warn
from vivie_core.health import format_report, run_full_check
from vivie_core.registry import bootstrap
from vivie_core.ui import emit_memory_counts, update_ui

# Optional components - lazy loaded
_auto_learning_engine = None
_behavior_engine = None
_digital_life_controller = None
_proactive_engine = None
_self_awareness_engine = None
_weather_system = None
_tts_module = None

def _get_auto_learning():
    global _auto_learning_engine
    if _auto_learning_engine is None:
        try:
            from Core_structure.auto_learning_engine import start_auto_learning
            _auto_learning_engine = start_auto_learning
        except Exception as e:
            warn("auto_learning import", e)
    return _auto_learning_engine

def _get_behavior_engine():
    global _behavior_engine
    if _behavior_engine is None:
        try:
            from Core_structure.behavior_engine import get_suggestions, start_behavior_engine
            _behavior_engine = {"get_suggestions": get_suggestions, "start": start_behavior_engine}
        except Exception as e:
            warn("behavior_engine import", e)
    return _behavior_engine

def _get_digital_life_controller():
    global _digital_life_controller
    if _digital_life_controller is None:
        try:
            from Core_structure.digital_life_controller import start_digital_life_controller
            _digital_life_controller = start_digital_life_controller
        except Exception as e:
            warn("digital_life_controller import", e)
    return _digital_life_controller

def _get_proactive_engine():
    global _proactive_engine
    if _proactive_engine is None:
        try:
            from Core_structure.proactive_engine import start_proactive_engine
            _proactive_engine = start_proactive_engine
        except Exception as e:
            warn("proactive_engine import", e)
    return _proactive_engine

def _get_self_awareness_engine():
    global _self_awareness_engine
    if _self_awareness_engine is None:
        try:
            from Core_structure.self_awareness_engine import record_growth_event
            _self_awareness_engine = record_growth_event
        except Exception as e:
            warn("self_awareness_engine import", e)
    return _self_awareness_engine

def _get_weather_system():
    global _weather_system
    if _weather_system is None:
        try:
            from Features.weather_system import start_weather_system
            _weather_system = start_weather_system
        except Exception as e:
            warn("weather_system import", e)
    return _weather_system

def _get_tts():
    global _tts_module
    if _tts_module is None:
        try:
            from TextToSpeech.Fast_DF_TTS import speak_blocking
            _tts_module = speak_blocking
        except Exception as e:
            warn("TTS import", e)
    return _tts_module


def _push_behavior_suggestions() -> None:
    behavior = _get_behavior_engine()
    if not behavior:
        return
    time.sleep(90)
    while True:
        try:
            suggestions = behavior["get_suggestions"](top_k=3)
            if suggestions:
                for sug in suggestions:
                    now = datetime.datetime.now().strftime("%H:%M:%S")
                    update_ui("sig_log", f"[{now}] {sug['message']}")
        except Exception as exc:
            warn("behavior_suggestions", exc)
        time.sleep(1800)


def _push_startup_data() -> None:
    def worker():
        time.sleep(3)
        try:
            from memory_core.session_memory import get_session_memory
            stats = get_session_memory().get_session_stats()
            update_ui("sig_session_id", f"S{stats.get('total_sessions', 1):04d}")
        except Exception as exc:
            warn("startup session id", exc)

        emit_memory_counts()

        try:
            from Core_structure.personality_engine import get_personality
            p = get_personality()
            pos   = p.get("positive_reactions", 0)
            neg   = p.get("negative_reactions", 0)
            total = pos + neg
            conf  = round((pos / total * 30) + 70, 1) if total > 0 else 97.0
            update_ui("sig_confidence", conf)
        except Exception as exc:
            warn("startup confidence", exc)

        update_ui("sig_log", "System initialized — all engines online")

    threading.Thread(target=worker, daemon=True).start()


def start_vivie() -> None:
    """Main Vivie runtime (formerly main_brain.Vivie)."""
    from vivie_core.config import VOICE_ENABLED

    configure()
    LOG.info("Vivie 2.0 starting...")

    health = run_full_check()
    print(format_report(health))
    if not health.ok:
        update_ui("sig_log", "Degraded mode — check console health report")
    else:
        update_ui("sig_log", "Health check passed")

    bootstrap(intent_engine, planner)

    # Lazy initialization of optional components
    weather = _get_weather_system()
    if weather:
        weather()

    proactive = _get_proactive_engine()
    if proactive:
        proactive()

    auto_learning = _get_auto_learning()
    if auto_learning:
        auto_learning()

    self_awareness = _get_self_awareness_engine()
    if self_awareness:
        self_awareness("learned_topic", "Initial setup complete")

    behavior = _get_behavior_engine()
    if behavior:
        behavior["start"]()

    digital_life = _get_digital_life_controller()
    if digital_life:
        digital_life()

    start_websocket_server()
    _push_startup_data()

    time.sleep(1.2)
    try:
        from memory_core.session_memory import get_session_memory
        stats = get_session_memory().get_session_stats()
        update_ui("sig_session_id", str(stats.get("total_sessions", 1)))
    except Exception as exc:
        warn("session stats", exc)

    # NOTE: emit_memory_counts() is called inside _push_startup_data() worker thread.
    # Do NOT call it again here — doing so fires two overlapping UI updates at startup.

    # Only speak greeting if voice mode is enabled
    if VOICE_ENABLED:
        tts = _get_tts()
        try:
            from memory_core.session_memory import get_session_memory
            greeting = get_session_memory().get_session_greeting()
            if greeting and tts:
                tts(greeting)
        except Exception as exc:
            warn("session greeting", exc)
    else:
        LOG.info("Voice mode disabled — greeting displayed as text only")

    # Start background threads based on mode
    threads = [
        threading.Thread(target=brain_loop, daemon=True),
        threading.Thread(target=_push_behavior_suggestions, daemon=True),
    ]

    # Only start audio loops if voice mode is enabled
    if VOICE_ENABLED:
        threads.extend([
            threading.Thread(target=listen_loop, daemon=True),
            threading.Thread(target=tts_loop, daemon=True),
        ])
        LOG.info("Voice mode enabled — starting audio loops")
    else:
        LOG.info("Chat mode — audio loops disabled")

    for t in threads:
        t.start()
    for t in threads:
        t.join()