"""respond_text action — news, reminders, research, self-awareness, LLM path."""

import os

from Brain.cl_brain import Main_Brain
from Core_structure.proactive_engine import add_reminder
from Core_structure.research_engine import get_research_engine
from Core_structure.self_awareness_engine import (
    assess_confidence,
    describe_current_state,
    get_capability_status,
    get_growth_summary,
    record_growth_event,
    self_reflect,
)
from Features.web_search import search_web
from memory_core.memory_service import store_memory
from vivie_core import state
from vivie_core.config import REALTIME_KEYWORDS
from vivie_core import text as text_util
from vivie_core.engines import context_manager
from vivie_core.handlers.llm_decision import run_llm_decision
from vivie_core.handlers.post_process import finalize, finalize_with_memory
from vivie_core.ui import update_ui

# Lazy imports for heavy knowledge components
_extract_knowledge = None
_store_knowledge = None

def _get_extract_knowledge():
    global _extract_knowledge
    if _extract_knowledge is None:
        try:
            from knowledge_core.knowledge_extractor import extract_knowledge
            _extract_knowledge = extract_knowledge
        except Exception as e:
            from vivie_core.log_util import warn
            warn("knowledge_core.knowledge_extractor import", e)
    return _extract_knowledge

def _get_store_knowledge():
    global _store_knowledge
    if _store_knowledge is None:
        try:
            from knowledge_core.rag_store import store_knowledge
            _store_knowledge = store_knowledge
        except Exception as e:
            from vivie_core.log_util import warn
            warn("knowledge_core.rag_store import", e)
    return _store_knowledge


def handle_respond_text(ctx, details: str) -> str | None:
    lower = details.lower()

    if any(w in lower for w in [
        "how have you evolved", "your personality", "how are you different",
        "what have you become", "describe yourself", "your traits",
    ]):
        from Core_structure.personality_engine import get_personality_status
        status = get_personality_status()
        record_growth_event("personality_evolved", str(status))
        update_ui("sig_vivie_message", status)
        return status

    if any(k in lower for k in ["explain number", "open number", "tell me about number"]):
        return _handle_news_explain(ctx, details, lower)

    if any(k in lower for k in [
        "latest news", "tell latest news", "current news",
        "today news", "news today", "tell today news",
    ]):
        return _handle_latest_news()

    if any(t in lower for t in [
        "remind me to", "remind me at", "set reminder",
        "reminder for", "don't let me forget",
    ]):
        return _handle_reminder(details)

    if any(w in lower for w in [
        "what do you know about my habits", "what have you learned about me",
        "my patterns", "my routine", "my habits",
    ]):
        from Core_structure.behavior_engine import get_pattern_summary
        summary = get_pattern_summary()
        update_ui("sig_vivie_message", summary)
        return summary

    # Explicit memory command — "Vivie remember that..." / "remember this..."
    dl = details.lower()
    explicit_prefixes = (
        "remember that", "remember this", "remember ",
        "vivie remember that", "vivie remember this", "vivie remember ",
        "don't forget", "keep in mind",
    )
    if any(dl.startswith(p) for p in explicit_prefixes):
        try:
            from Brain.user_model import update_explicit
            update_explicit(details)
        except Exception:
            pass
        store_memory(details, "")
        response = "Stored, Boss. I will keep that in mind always."
        context_manager.update(ctx.intent, details, response)
        update_ui("sig_vivie_message", response)
        return response

    if text_util.is_personal_statement(details):
        store_memory(details, "")
        try:
            from Brain.user_model import update_explicit
            update_explicit(details)
        except Exception:
            pass
        response = "Noted. I will remember that, Boss."
        context_manager.update(ctx.intent, details, response)
        update_ui("sig_vivie_message", response)
        return response

    if any(word in lower for word in REALTIME_KEYWORDS):
        return _handle_realtime(ctx, details)

    if any(w in lower for w in [
        "knowledge map", "what have you researched",
        "show knowledge graph",
        "what do you know about connections",
    ]):
        return _research_map(lower)

    if any(w in lower for w in [
        "research history", "what have you researched before",
        "previous research", "past research",
    ]):
        engine = get_research_engine()
        record_growth_event("learned_topic", f"Researched: {details[:50]}")
        result = engine.get_research_history()
        update_ui("sig_vivie_message", result)
        return result

    if any(w in lower for w in [
        "what have you done", "autonomous actions", "digital life status",
        "dlc status", "what did you do", "show activity log",
    ]):
        from Core_structure.digital_life_controller import get_dlc
        result = get_dlc().get_status()
        update_ui("sig_vivie_message", result)
        return result[:300]

    if any(w in lower for w in ["watch folder", "monitor folder", "add folder"]):
        return _handle_watch_folder(details)

    if any(w in lower for w in ["my routines", "show routines", "what routines", "active routines"]):
        from Core_structure.digital_life_controller import get_dlc
        result = get_dlc().routine_manager.get_routine_status()
        update_ui("sig_vivie_message", result)
        return result[:300]

    result = _self_awareness(lower)
    if result is not None:
        return result

    return run_llm_decision(ctx, details)


# ── Private helpers ────────────────────────────────────────────────────────────

def _handle_news_explain(ctx, details: str, lower: str) -> str:
    index = text_util.extract_number(lower)
    with state._news_results_lock:
        snap = list(state.last_news_results)
    if index is not None and 0 <= index < len(snap):
        article = snap[index]
        response = Main_Brain(
            f"Explain clearly:\ntitle:{article['title']}\n"
            f"Context:{article['content']}\nsource:{article['source']}"
        )
        if response:
            context_manager.update(ctx.intent, details, response)
            update_ui("sig_vivie_message", response)
            return response
    return "Please select a valid headline number."


def _handle_latest_news() -> str:
    news_results = search_web("latest world news today")
    if not news_results:
        return "I could not fetch the latest news right now."
    with state._news_results_lock:
        state.last_news_results = news_results
    headlines = "Here are the latest headlines:\n\n"
    for i, article in enumerate(news_results):
        title = article["title"].split(".")[0]
        headlines += f"{i + 1}.{title}\n"
    headlines += "\nWhich one would you like me to explain?"
    update_ui("sig_vivie_message", headlines)
    return headlines


def _handle_reminder(details: str) -> str:
    response = Main_Brain(
        f"Extract reminder time and task from: '{details}'\n"
        f"Reply in format: TIME|TASK\n"
        f"TIME: HH:MM or YYYY-MM-DD HH:MM\nExample: 14:30|Submit assignment\n"
        f"Only reply with TIME|TASK."
    )
    if response and "|" in response:
        parts = response.strip().split("|")
        r_time = parts[0].strip()
        r_task = parts[1].strip()
        add_reminder(r_task, r_time)
        msg = f"Got it Boss. I'll remind you to {r_task} at {r_time}."
        update_ui("sig_vivie_message", msg)
        return msg
    return "Boss, please tell me the time for the reminder."


def _handle_realtime(ctx, details: str) -> str | None:
    web_data = search_web(details)
    final_input = (
        f"Use real-time web data:\n{web_data}\n\n"
        f"Summarize clearly.\n\nUser: {details}"
    )
    response = Main_Brain(final_input)
    if response:
        context_manager.update(ctx.intent, details, response)
        update_ui("sig_vivie_message", response)
        return response
    return None


def _research_map(lower: str) -> str:
    engine = get_research_engine()
    topic = None
    for prep in ["about", "for", "on"]:
        if prep in lower:
            topic = lower[lower.index(prep) + len(prep):].strip()
            break
    result = engine.get_knowledge_map(topic)
    update_ui("sig_vivie_message", result)
    return result


def _handle_watch_folder(details: str) -> str:
    from Core_structure.digital_life_controller import get_dlc
    response = Main_Brain(f"Extract folder path from: '{details}'\nReturn ONLY the path.")
    if response and os.path.exists(response.strip()):
        get_dlc().add_watch_folder(response.strip())
        msg = f"Now monitoring {response.strip()}"
        update_ui("sig_vivie_message", msg)
        return msg
    return "Could not find that folder path, Boss."


def _self_awareness(lower: str) -> str | None:
    """Handle self-awareness and introspection queries."""
    triggers = {
        "what can you do":          lambda: get_capability_status(),
        "your capabilities":        lambda: get_capability_status(),
        "what are you capable of":  lambda: get_capability_status(),
        "how are you doing":        lambda: describe_current_state(),
        "your current state":       lambda: describe_current_state(),
        "system status":            lambda: describe_current_state(),
        "your growth":              lambda: get_growth_summary(),
        "how have you grown":       lambda: get_growth_summary(),
        "reflect on yourself":      lambda: self_reflect(),
        "honest reflection":        lambda: self_reflect(),
        "what are your limits":     lambda: get_capability_status(),
        "what can't you do":        lambda: get_capability_status(),
        "your vision capability":   lambda: get_capability_status("vision"),
        "your research capability": lambda: get_capability_status("research"),
        # Brain observability (UPGRADE 4)
        "brain stats":              lambda: _brain_stats(),
        "show brain stats":         lambda: _brain_stats(),
        "brain status":             lambda: _brain_stats(),
        "brain performance":        lambda: _brain_stats(),
        "brain metrics":            lambda: _brain_stats(),
    }
    for trigger, handler in triggers.items():
        if trigger in lower:
            result = handler()
            update_ui("sig_vivie_message", result)
            return result[:400]
    return None


def _brain_stats() -> str:
    """Return a formatted brain observability report."""
    try:
        from Brain.brain_metrics import brain_status_text
        return brain_status_text()
    except Exception as e:
        return f"Brain metrics unavailable: {e}"
