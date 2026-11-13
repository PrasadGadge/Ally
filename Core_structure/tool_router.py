# ==========================================
# Core_structure/tool_router.py
# Fixed: ValueError on unknown tool,
#        unhandled tool exceptions,
#        added list_tools() for debugging
# Enhanced: Structured tool result verification
# ==========================================

import time
from Core_structure.tool_result import ToolResult, wrap_tool_result, ToolStatus, SideEffect

class ToolRouter:

    def __init__(self):
        self.tools = {}

    def register(self, name: str, func) -> None:
        """Register a callable tool by name."""
        self.tools[name] = func
        print(f"[ToolRouter] Registered: {name}")

    def execute(self, name: str, *args, **kwargs) -> ToolResult:
        """
        Execute a registered tool with structured result verification.

        FIX 1: Unknown tool now returns a failure ToolResult instead of raising
        ValueError — prevents crashing the response pipeline when
        a planner suggests a tool that isn't registered yet.

        FIX 2: Tool exceptions are caught and logged — a broken
        tool no longer kills the entire request.

        ENHANCEMENT: Returns structured ToolResult with status, data, and metadata
        for better verification and UI integration.

        Returns a ToolResult object.
        """
        if name not in self.tools:
            # Log it so we can spot missing registrations — but don't crash
            print(f"[ToolRouter] Unknown tool: '{name}' — skipping")
            return ToolResult.failure(
                message=f"Tool '{name}' is not registered",
                tool_name=name,
            )

        start_time = time.perf_counter()
        
        try:
            result = self.tools[name](*args, **kwargs)
            execution_time = (time.perf_counter() - start_time) * 1000
            print(f"[ToolRouter] Executed: {name} ({execution_time:.0f}ms)")
            
            # Wrap result into structured format
            structured = wrap_tool_result(result, tool_name=name)
            structured.execution_time_ms = execution_time
            structured.verified = True  # Mark as verified since execution completed
            
            return structured
        except Exception as e:
            execution_time = (time.perf_counter() - start_time) * 1000
            print(f"[ToolRouter] Tool '{name}' raised: {e}")
            return ToolResult.failure(
                message=f"Tool '{name}' encountered an error",
                error=str(e),
                tool_name=name,
                execution_time_ms=execution_time,
            )

    def list_tools(self) -> list:
        """Return names of all registered tools (useful for debugging)."""
        return list(self.tools.keys())

    def is_registered(self, name: str) -> bool:
        """Check if a tool is registered without executing it."""
        return name in self.tools
