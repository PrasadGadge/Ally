"""Shared post-processing after a handler produces a response."""

from Core_structure.personality_engine import detect_signals, evolve_personality
from Core_structure.response_formatter import format_response
from memory_core.memory_service import store_memory
from vivie_core.engines import context_manager, self_reflection
from vivie_core.log_util import warn
from vivie_core.ui import emit_memory_counts, update_ui


def finalize(ctx, details: str, response: str, *, store: bool = True) -> str:
    response = format_response(response)
    response = self_reflection.evaluate(details, response)
    context_manager.update(ctx.intent, details, response)
    if store:
        store_memory(details, response)
    update_ui("sig_vivie_message", response)
    return response


def evolve_after_response(ctx, details: str, response: str) -> None:
    try:
        signals = detect_signals(
            user_input=details,
            vivie_response=response,
            intent=str(ctx.intent.get("primary", "chat")),
            reaction="neutral",
        )
        evolve_personality(signals)
    except Exception as exc:
        warn("evolve_personality", exc)


def finalize_with_memory(ctx, details: str, response: str) -> str:
    out = finalize(ctx, details, response)
    emit_memory_counts()
    evolve_after_response(ctx, details, out)
    return out
