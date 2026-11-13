"""Decision engine + reasoning + Main_Brain LLM path."""

import traceback

from Brain.cl_brain import Main_Brain
from Core_structure.agent_router import route_to_agent
from Features.web_search import search_web
from Core_structure.self_awareness_engine import assess_confidence
from memory_core.memory_service import retrieve_memory
from vivie_core.config import REALTIME_KEYWORDS
from vivie_core.engines import (
    context_manager,
    decision_engine,
    reasoning_engine,
)
from vivie_core.handlers.post_process import finalize_with_memory
from vivie_core.log_util import error, warn
from vivie_core.ui import update_ui

# Lazy imports for heavy knowledge components
_retrieve_knowledge = None

def _get_retrieve_knowledge():
    global _retrieve_knowledge
    if _retrieve_knowledge is None:
        try:
            from knowledge_core.rag_retrieve import retrieve_knowledge
            _retrieve_knowledge = retrieve_knowledge
        except Exception as e:
            warn("knowledge_core.rag_retrieve import", e)
    return _retrieve_knowledge


def run_llm_decision(ctx, details: str) -> str | None:
    mem_block = ctx.memory_block
    knowledge = ctx.knowledge_context
    lower = details.lower()

    if not mem_block:
        try:
            mem_ctx = retrieve_memory(details)
            msgs = mem_ctx.get() if mem_ctx else []
            mem_block = "".join(m.get("content", "") + "\n" for m in msgs)
        except Exception as exc:
            warn("retrieve_memory (decision)", exc)

    if not knowledge:
        try:
            retrieve_fn = _get_retrieve_knowledge()
            if retrieve_fn:
                knowledge = retrieve_fn(details) or ""
        except Exception as exc:
            warn("retrieve_knowledge (decision)", exc)

    contextual_input = context_manager.build_context_prompt(details)
    reasoning_steps = reasoning_engine.think(details, ctx.intent, mem_block, knowledge)
    update_ui("sig_reasoning", reasoning_steps)

    decision = decision_engine.decide(
        user_input=details,
        intent=ctx.intent,
        memory_block=mem_block,
        knowledge=knowledge,
        context=contextual_input,
        reasoning=reasoning_steps,
    )
    update_ui("sig_confidence", round(decision.get("confidence", 0.8) * 100, 1))

    if decision.get("use_web_search"):
        web_data = search_web(details)
        if web_data:
            decision["top_knowledge"] = (
                (decision.get("top_knowledge") or "")
                + f"\nReal-time:\n{str(web_data)[:1000]}"
            )

    final_input = decision_engine.build_smart_prompt(
        user_input=details,
        decision=decision,
        context=contextual_input,
        reasoning=reasoning_steps,
    )

    try:
        confidence_data = assess_confidence(details, knowledge or "", mem_block)
    except Exception as exc:
        warn("assess_confidence", exc)
        confidence_data = {
            "should_refuse": False,
            "be_honest": False,
            "should_search": False,
            "caveat": "",
        }

    if confidence_data.get("should_refuse"):
        response = f"Boss, {confidence_data.get('caveat', '')}"
        update_ui("sig_vivie_message", response)
        return response

    if confidence_data.get("be_honest"):
        final_input = (
            f"Important: answer with appropriate uncertainty. "
            f"{confidence_data.get('caveat', '')}\n\n"
        ) + final_input

    if confidence_data.get("should_search") and not any(
        w in lower for w in REALTIME_KEYWORDS
    ):
        web_data = search_web(details)
        if web_data:
            final_input = f"Real-time data:\n{web_data}\n\n" + final_input

    try:
        response = Main_Brain(final_input)
    except Exception as exc:
        error("LLM call failed", exc, exc_info=True)
        print("\n" + "=" * 50)
        print("CRITICAL LLM ERROR")
        traceback.print_exc()
        print("=" * 50 + "\n")
        if "429" in str(exc):
            return "Boss, I've hit my API limit (Quota Exceeded). I need a moment to cool down or a new key."
        if "timeout" in str(exc).lower():
            return "My connection timed out, Boss. I'll try to reconnect."
        return "I encountered a neural glitch. Check the console for the error log."

    if not response:
        return None

    return finalize_with_memory(ctx, details, response)
