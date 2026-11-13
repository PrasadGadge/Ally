"""Planner action_type handlers (non-respond_text)."""

from Brain.cl_brain import Main_Brain
from Features.check_internet_speed import get_internet_speed
from Features.morning_brief import morning_brief
from Features.web_search import search_web
from Vision.Vibrain import capture_image_and_save, vision_brain
from memory_core.memory_service import store_memory
from vivie_core import text as text_util
from vivie_core.engines import tool_router
from vivie_core.handlers.post_process import finalize
from vivie_core.registry import execute as execute_tool
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


def handle_action(ctx, act_type: str, details: str, kwargs: dict = None) -> str | None:
    kwargs = kwargs or {}
    
    if act_type == "create_file":
        filename = kwargs.get("filename") or details.replace("create", "").replace("file", "").strip()
        if not filename:
            return "Boss, what should I name the file?"
        result = tool_router.execute("create_file", details, **kwargs)
        msg = result or "Boss, I could not create that file."
        return finalize(ctx, details, msg)

    if act_type == "check_internet_speed":
        speed = get_internet_speed()
        msg = str(speed) if speed is not None else "Unable to determine internet speed"
        return finalize(ctx, details, msg)

    if act_type == "vision_analysis":
        if capture_image_and_save("capture_image.jpg"):
            return finalize(ctx, details, vision_brain("capture_image.jpg"))
        return "Vision capture failed Boss."

    if act_type == "get_weather":
        city = kwargs.get("city") or text_util.extract_city(details, "weather")
        tool_router.execute("get_weather", details, **kwargs)
        return None

    if act_type == "get_forecast":
        city = kwargs.get("city") or text_util.extract_city(details, "forecast")
        city_label = city if city else "your area"
        update_ui("sig_vivie_message", f"Fetching 3-day forecast for {city_label}...")
        tool_router.execute("get_forecast", details, **kwargs)
        return None

    if act_type == "send_whatsapp":
        result = tool_router.execute("send_whatsapp", details, **kwargs)
        msg = (
            "Message sent successfully on WhatsApp."
            if result is not None
            else "Failed to send WhatsApp message."
        )
        update_ui("sig_vivie_message", msg)
        return msg

    if act_type == "morning_brief":
        morning_brief()
        return "Here's your morning brief, Boss."

    if act_type == "respond_text":
        from vivie_core.handlers.respond import handle_respond_text
        return handle_respond_text(ctx, details)

    return None


def handle_tool_or_agent(ctx, act_type: str, details: str, kwargs: dict = None) -> str | None:
    from Core_structure.agent_router import route_to_agent
    from vivie_core.handlers.post_process import finalize

    kwargs = kwargs or {}
    tool_result = execute_tool(act_type, details, **kwargs)
    if tool_result:
        response = finalize(ctx, details, tool_result)
        extract_fn = _get_extract_knowledge()
        store_fn = _get_store_knowledge()
        if extract_fn and store_fn:
            info = extract_fn(details, response, source="tool")
            if info:
                store_fn(info, {"source": "tool", "query": details[:100]})
        store_memory(details, response)
        return response

    agent_name, agent_response = route_to_agent(
        details, ctx.memory_block, ctx.knowledge_context
    )
    if agent_name != "none" and agent_response:
        response = finalize(ctx, details, agent_response)
        extract_fn = _get_extract_knowledge()
        store_fn = _get_store_knowledge()
        if extract_fn and store_fn:
            info = extract_fn(details, response, source="agent")
            if info:
                store_fn(
                    info, {"source": f"{agent_name}_agent", "query": details[:100]}
                )
        store_memory(details, response)
        return response

    return None
