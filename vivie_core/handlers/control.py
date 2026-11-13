"""Kill switch, wake, and feedback handlers."""

import vivie_core.state as state
from memory_core.episodic_memory import update_last_reaction
from vivie_core.log_util import warn


def handle_control(ctx) -> str | None:
    text_lower = ctx.text_lower

    greetings = {
        "hey vivie", "hi vivie", "hello vivie", "vivie",
        "hey", "hi", "hello",
    }
    if text_lower.strip() in greetings:
        state.VIVIE_ACTIVE = True
        return "Hey Boss, I am listening."

    stop_words = [
        "go to sleep", "vivie silence", "vivie stop", "vivie keep quiet",
        "vivie shut down", "stop vivie",
    ]
    if text_lower.strip() == "stop" or any(w in text_lower for w in stop_words):
        state.VIVIE_ACTIVE = False
        return "Okay, going silent Boss."

    wake_words = ["wake up", "vivie wake up", "vivie start", "vivie speak"]
    if text_lower.strip() == "start" or any(w in text_lower for w in wake_words):
        state.VIVIE_ACTIVE = True
        return "Hey Boss, I am back."

    if not state.VIVIE_ACTIVE:
        return None  # silent — not an error

    if any(w in ctx.text for w in ["good answer", "correct", "well done", "perfect answer"]):
        update_last_reaction("positive")
        try:
            from Core_structure.personality_engine import evolve_personality
            evolve_personality({"general_positive": True})
        except Exception as exc:
            warn("personality positive", exc)
        return "Glad that helped Boss."

    if any(w in ctx.text for w in [
        "wrong answer", "incorrect", "that was wrong", "bad answer", "improve more",
    ]):
        update_last_reaction("negative")
        try:
            from Core_structure.personality_engine import evolve_personality
            evolve_personality({"general_negative": True})
        except Exception as exc:
            warn("personality negative", exc)
        return "Noted. I will do better."

    return None
