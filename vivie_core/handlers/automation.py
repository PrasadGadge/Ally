"""Desktop / browser automation shortcut."""

from Automation.Automation_brain import Auto_main_brain


def handle_automation(ctx) -> str | None:
    if ctx.primary_intent == "automation" and ctx.confidence >= 0.75:
        if Auto_main_brain(ctx.text):
            return "Done"
    return None
