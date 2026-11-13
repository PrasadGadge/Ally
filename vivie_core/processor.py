"""
Vivie 2.0 pipeline processor — thin orchestrator.

Flow:
  preprocess → memory commands → control → intent/UI → memory → time → fast chat
  → [lock] automation → plan actions → fallback
"""

from Core_structure.behavior_engine import record_behavior
from vivie_core import state
from vivie_core import text as text_util
from vivie_core.handlers.automation import handle_automation
from vivie_core.handlers.control import handle_control
from vivie_core.handlers.fallback import run_fallback
from vivie_core.handlers.fast_chat import handle_fast_chat
from vivie_core.handlers.plan_executor import execute_plan
from vivie_core.handlers.time_schedule import handle_time
from vivie_core.pipeline_context import PipelineContext
from vivie_core.metrics import RequestTimer
from vivie_core.ui import update_ui
from vivie_core.log_util import warn


def process_text(text: str) -> str | None:
    with RequestTimer():
        return _process_text_inner(text)


def _process_text_inner(text: str) -> str | None:
    update_ui("sig_agent_state", "processing...")

    if any(x in text.lower() for x in ["[tts]", "speaking:"]):
        return None

    quick_text = text_util.fix_wake_word(
        text_util.autocorrect_input(text_util.normalize_input(text))
    )
    if quick_text in {"hey vivie", "hi vivie", "hello vivie", "vivie", "hey", "hi", "hello"}:
        state.VIVIE_ACTIVE = True
        update_ui("sig_user_message", quick_text)
        update_ui("sig_vivie_message", "Hey Boss, I am listening.")
        return "Hey Boss, I am listening."

    explicit_memory_prefixes = (
        "vivie remember", "remember ", "remember that", "remember this",
        "don't forget", "keep in mind",
    )
    if quick_text.startswith(explicit_memory_prefixes):
        try:
            from Brain.user_model import update_explicit
            update_explicit(quick_text)
        except Exception as exc:
            warn("explicit memory user model", exc)
        try:
            from memory_core.memory_service import store_memory
            store_memory(quick_text, "")
        except Exception as exc:
            warn("explicit memory store", exc)
        update_ui("sig_user_message", quick_text)
        update_ui("sig_vivie_message", "Stored, Boss. I will keep that in mind always.")
        return "Stored, Boss. I will keep that in mind always."

    # Handle memory management commands
    try:
        from Brain.memory_commands import get_memory_commands
        memory_cmd_handler = get_memory_commands()
        memory_response = memory_cmd_handler.handle_command(quick_text)
        if memory_response:
            update_ui("sig_user_message", quick_text)
            update_ui("sig_vivie_message", memory_response)
            return memory_response
    except Exception as exc:
        warn("memory commands", exc)

    ctx = PipelineContext.from_raw(text)

    print(f"User: {ctx.text}")
    print(f"Intent: {ctx.intent}")
    update_ui("sig_user_message", ctx.text)
    update_ui("sig_listening", False)

    result = handle_control(ctx)
    if result is not None:
        return result

    if not state.VIVIE_ACTIVE:
        return None

    record_behavior(
        action=ctx.intent.get("primary", "chat"),
        context=ctx.text[:80],
    )
    print("Actions:", ctx.actions)

    ctx.load_memory_if_needed()

    # Chain of thought — 2 fast Tier 0 calls (~300ms total)
    # Skipped for simple queries, automation, alarms, fast-chat path
    # Adds rich reasoning context to the main LLM prompt
    try:
        from Brain.chain_of_thought import build_cot
        ctx.cot_context = build_cot(ctx)
    except Exception as exc:
        warn("chain_of_thought", exc)

    result = handle_time(ctx)
    if result is not None:
        return result
    # FIX: handle_time() returns None for BOTH "handled, no speech" AND
    # "not a time command at all". The old guard:
    #   if ctx.text.startswith("tell me"): return None
    # silently dropped ALL "tell me about X" queries that aren't time commands.
    # Now handle_time() sets ctx.time_handled = True when it actually processes
    # a time command so we can distinguish the two cases.
    if getattr(ctx, "time_handled", False):
        return None

    result = handle_fast_chat(ctx)
    if result is not None:
        return result

    with state.processing_lock:
        result = handle_automation(ctx)
        if result is not None:
            return result

        result = execute_plan(ctx)
        if result is not None:
            return result

        return run_fallback(ctx)
