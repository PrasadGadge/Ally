"""Schedule and alarm commands."""

from Time_operations.time_manager import input_manage, input_manage_Alam
from vivie_core import text as text_util


def handle_time(ctx) -> str | None:
    text = ctx.text

    # "tell me at 3pm" — only handle if there's a digit (time) in the text
    # "tell me about machine learning" has no digit — NOT a time command
    if text.startswith("tell me"):
        if any(char.isdigit() for char in text):
            input_manage(text_util.pad_time_text(text))
            ctx.time_handled = True   # FIX: signal processor this was handled
            return None
        return None   # no digit → not a time command → fall through normally

    if text.startswith("set alarm"):
        input_manage_Alam(text_util.pad_time_text(text))
        ctx.time_handled = True       # FIX: signal processor this was handled
        return None

    return None
