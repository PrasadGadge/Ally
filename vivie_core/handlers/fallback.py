"""Fallback when no planner action handled the request."""

from memory_core.memory_service import store_memory
from vivie_core.engines import context_manager
from vivie_core.log_util import warn
from vivie_core.pipeline_context import PipelineContext
from vivie_core.ui import emit_memory_counts, update_ui

# Lazy imports for heavy components
_MainBrain = None
_detect_signals = None
_evolve_personality = None
_store_conversation_knowledge = None

def _get_MainBrain():
    global _MainBrain
    if _MainBrain is None:
        try:
            from Brain.cl_brain import Main_Brain
            _MainBrain = Main_Brain
        except Exception as e:
            warn("Brain.cl_brain import", e)
    return _MainBrain

def _get_personality():
    global _detect_signals, _evolve_personality
    if _detect_signals is None:
        try:
            from Core_structure.personality_engine import detect_signals, evolve_personality
            _detect_signals = detect_signals
            _evolve_personality = evolve_personality
        except Exception as e:
            warn("personality_engine import", e)
    return _detect_signals, _evolve_personality

def _get_store_conversation_knowledge():
    global _store_conversation_knowledge
    if _store_conversation_knowledge is None:
        try:
            from knowledge_core.rag_store import store_conversation_knowledge
            _store_conversation_knowledge = store_conversation_knowledge
        except Exception as e:
            warn("knowledge_core.rag_store import", e)
    return _store_conversation_knowledge


def run_fallback(ctx: PipelineContext) -> str | None:
    details          = ctx.details or ctx.text
    contextual_input = context_manager.build_context_prompt(details)

    # Pass CoT + user model + episodic + knowledge context into Main_Brain for richer responses
    MainBrain_fn = _get_MainBrain()
    if not MainBrain_fn:
        return None
    response = MainBrain_fn(
        contextual_input,
        cot_context        = getattr(ctx, "cot_context", ""),
        user_model_context = getattr(ctx, "user_model_context", ""),
        episodic_memory    = getattr(ctx, "memory_block", ""),
        knowledge_context  = getattr(ctx, "knowledge_context", ""),
    )
    if not response:
        return None

    # Response quality gate — escalate to Tier 1 if quality is low
    try:
        from Brain.response_verifier import verify
        verdict = verify(ctx.text, response)
        if verdict.should_escalate:
            print(f"[Fallback] Escalating to Tier 1 (score {verdict.score}/10)")
            better = MainBrain_fn(
                contextual_input,
                cot_context        = getattr(ctx, "cot_context", ""),
                user_model_context = getattr(ctx, "user_model_context", ""),
                forced_tier        = 1,
                episodic_memory    = getattr(ctx, "memory_block", ""),
                knowledge_context  = getattr(ctx, "knowledge_context", ""),
            )
            if better and len(better) > len(response):
                response = better
    except Exception as exc:
        warn("response_verifier", exc)

    context_manager.update(ctx.intent, details, response)
    store_memory(details, response)
    store_fn = _get_store_conversation_knowledge()
    if store_fn:
        store_fn(details, response)
    emit_memory_counts()

    # Track conversation turn for reference resolution
    try:
        from Brain.reference_resolver import get_reference_resolver
        resolver = get_reference_resolver()
        resolver.add_turn(details, response)
    except Exception as exc:
        warn("reference_resolver_add_turn", exc)

    # Passive user model update — background thread, never blocks
    try:
        from Brain.user_model import update_async
        update_async(ctx.text, response)
    except Exception as exc:
        warn("user_model_update", exc)

    try:
        detect_fn, evolve_fn = _get_personality()
        if detect_fn and evolve_fn:
            signals = detect_fn(
                user_input=details,
                vivie_response=response,
                intent=str(ctx.intent.get("primary", "chat")),
                reaction="neutral",
            )
            evolve_fn(signals)
    except Exception as exc:
        warn("evolve_personality fallback", exc)

    update_ui("sig_vivie_message", response)
    _push_session_ui()
    return response


def _push_session_ui() -> None:
    try:
        from memory_core.episodic_memory import get_episode_count
        from memory_core.session_memory import get_session_memory

        stats = get_session_memory().get_session_stats()
        chroma_count = 0
        try:
            from knowledge_core.chroma_manager import get_chroma_manager
            chroma_count = get_chroma_manager().count()
        except Exception:
            pass  # ChromaDB unavailable, skip count

        update_ui(
            "sig_memory_update",
            get_episode_count(),
            chroma_count,
        )
        update_ui("sig_session_id", f"S{stats.get('total_sessions', 1):04d}")
    except Exception as exc:
        warn("fallback session UI", exc)
