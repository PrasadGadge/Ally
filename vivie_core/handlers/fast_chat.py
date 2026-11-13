"""Fast path for simple high-confidence chat."""

from Brain.cl_brain import Main_Brain
from Brain.prompt_core import FAST_CHAT_USER_WRAP
from Core_structure.response_formatter import format_response
from vivie_core.ui import update_ui


def handle_fast_chat(ctx) -> str | None:
    if ctx.primary_intent != "chat" or ctx.confidence < 0.9:
        return None
    if len(ctx.text.split()) >= 6:
        return None

    prompt = FAST_CHAT_USER_WRAP.format(text=ctx.text)
    response = Main_Brain(prompt, history_text=ctx.text)
    if not response:
        return None

    response = format_response(response)
    update_ui("sig_vivie_message", response)
    return response
