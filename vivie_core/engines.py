"""Singleton cognitive engines — one instance for the whole runtime."""

from Core_structure.context import ContextManager
from Core_structure.decision_engine import DecisionEngine
from Core_structure.intent_engine import IntentEngine
from Core_structure.plan import Planner
from Core_structure.reasoning_engine import ReasoningEngine
from Core_structure.self_reflection import SelfReflection
from Core_structure.tool_router import ToolRouter

intent_engine = IntentEngine()
context_manager = ContextManager()
planner = Planner()
tool_router = ToolRouter()
reasoning_engine = ReasoningEngine()
self_reflection = SelfReflection()
decision_engine = DecisionEngine()
