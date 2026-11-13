"""Pipeline handlers — each returns a response string or None to continue."""

from vivie_core.handlers.control import handle_control
from vivie_core.handlers.time_schedule import handle_time
from vivie_core.handlers.fast_chat import handle_fast_chat
from vivie_core.handlers.automation import handle_automation
from vivie_core.handlers.plan_executor import execute_plan

__all__ = [
    "handle_control",
    "handle_time",
    "handle_fast_chat",
    "handle_automation",
    "execute_plan",
]
