# ==========================================
# plan.py — Phase 4/5 Upgrade
# LLM-first planning with multi-tool support
# Keyword branches kept as safe fallback only
# ==========================================


class Planner:

    def __init__(self):
        self._tool_registry = {}  # auto-populated by tool manifest

    # ─────────────────────────────────────────────────────────────
    # Phase 5: Build action list from multi-tool LLM response
    # Called when llm_intent_router returns a tools list
    # ─────────────────────────────────────────────────────────────
    @staticmethod
    def from_llm_tools(tools_list: list, user_text: str) -> list:
        """
        Convert a list of LLM tool-call dicts into an action list.
        Each entry:  {"tool": "action_type", "arguments": {...}}
        """
        actions = []
        for tool_call in tools_list:
            act_type = tool_call.get("tool") or tool_call.get("action_type")
            if not act_type or act_type == "null":
                continue
            actions.append({
                "type":   act_type,
                "details": user_text,
                "kwargs":  tool_call.get("arguments", {}),
            })
        if not actions:
            actions.append({"type": "respond_text", "details": user_text, "kwargs": {}})
        return actions

    # ─────────────────────────────────────────────────────────────
    # Primary plan generator
    # ─────────────────────────────────────────────────────────────
    def generate_plan(self, intent: dict, context: dict) -> list:
        actions    = []
        primary    = intent.get("primary",    "unknown")
        confidence = intent.get("confidence", 0.0)
        user_text  = context.get("last_input", "")
        parameters = intent.get("parameters", {})   # LLM-extracted args
        extra_tools = intent.get("extra_tools", [])  # Phase 5: multi-tool

        # ── Phase 5: multi-tool compound query ────────────────────────
        # If the LLM returned multiple tool steps, build the full chain
        if extra_tools:
            # primary tool first, then extras
            all_tools = [{"tool": primary, "arguments": parameters}] + extra_tools
            return self.from_llm_tools(all_tools, user_text)

        # ── Phase 4: single LLM-routed tool ───────────────────────────
        # If primary came from LLM (has parameters key set by router),
        # just emit it directly — no keyword guessing needed.
        if parameters or intent.get("extra_tools") is not None:
            if primary and primary not in ("unknown", "chat", "respond_text"):
                actions.append({
                    "type":    primary,
                    "details": user_text,
                    "kwargs":  parameters,
                })
                return actions

        # ── Fallback: keyword engine paths ─────────────────────────────
        # Only reached when LLM routing failed / returned chat/null.

        # Automation
        if primary == "automation" and confidence >= 0.75:
            actions.append({"type": "automation", "details": user_text})
        elif primary == "automation":
            actions.append({"type": "respond_text", "details": f"Did you mean: {user_text}?"})

        # Weather
        elif primary == "weather":
            t = "get_forecast" if "forecast" in user_text else "get_weather"
            actions.append({"type": t, "details": user_text})

        # Tool registry lookup (manifest-registered tools)
        elif primary in self._tool_registry:
            action_type = self._tool_registry[primary]
            actions.append({"type": action_type, "details": user_text})

        # Legacy hardcoded fallbacks (kept as last resort safety net)
        elif primary == "file_creation":
            actions.append({"type": "create_file",          "details": user_text})
        elif primary in ("internet", "internet_speed"):
            actions.append({"type": "check_internet_speed", "details": user_text})
        elif primary == "vision":
            actions.append({"type": "vision_analysis",      "details": user_text})
        elif primary == "whatsapp":
            actions.append({"type": "send_whatsapp",        "details": user_text})
        elif primary == "image_generation":
            actions.append({"type": "generate_image",       "details": user_text})

        # Ultimate fallback — pass to Brain as chat
        if not actions:
            actions.append({"type": "respond_text", "details": user_text})

        # Inject parameters as kwargs for every action (backward compat)
        for action in actions:
            if "kwargs" not in action:
                action["kwargs"] = parameters

        return actions
