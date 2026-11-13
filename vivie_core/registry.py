"""
Unified tool registry — ToolManifest auto-discovery only (Tools/ + Features/).
"""

from vivie_core.engines import tool_router
from vivie_core.log_util import LOG


def bootstrap(intent_engine, planner) -> int:
    from Core_structure.tool_manifest import (
        discover_tools,
        inject_into_intent_engine,
        inject_into_planner,
        inject_into_tool_router,
    )

    count = discover_tools()
    inject_into_intent_engine(intent_engine)
    inject_into_planner(planner)
    inject_into_tool_router(tool_router)

    registered = tool_router.list_tools()
    LOG.info(
        "Tool registry ready: %s manifests, %s router entries: %s",
        count,
        len(registered),
        ", ".join(sorted(registered)[:12]) + ("..." if len(registered) > 12 else ""),
    )
    return count


def execute(action_type: str, details: str, **kwargs):
    from Core_structure.tool_manifest import execute_tool

    result = execute_tool(action_type, details, **kwargs)
    if result:
        return result
    return tool_router.execute(action_type, details, **kwargs)


def list_registered() -> list:
    from Core_structure.tool_manifest import get_all_tools
    return sorted(get_all_tools().keys())
