"""
Feature tools — morning brief, vision, web search (ToolManifest).
"""

from Core_structure.tool_manifest import ToolManifest


class MorningBriefTool(ToolManifest):
    name = "morning_brief"
    description = "Daily briefing: weather, speed, top headline"
    keywords = ["morning brief", "daily brief", "good morning brief", "today briefing"]
    action_type = "morning_brief"
    category = "productivity"
    requires_online = True

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        from Features.morning_brief import morning_brief
        morning_brief()
        return "Here's your morning brief, Boss."


class VisionTool(ToolManifest):
    name = "vision"
    description = "Capture webcam and analyze the scene"
    keywords = [
        "what can you see", "take a look", "analyze", "analyse",
        "what do you see", "look at this", "vision",
    ]
    action_type = "vision_analysis"
    category = "vision"

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        from Vision.Vibrain import capture_image_and_save, vision_brain
        if capture_image_and_save("capture_image.jpg"):
            return vision_brain("capture_image.jpg") or "I could not analyze the image."
        return "Vision capture failed Boss."


class WebSearchTool(ToolManifest):
    name = "web_search"
    description = "Search the web and return top results"
    keywords = ["search the web", "google search", "look up online", "web search for"]
    action_type = "web_search"
    category = "search"
    requires_online = True

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        from Features.web_search import search_web
        results = search_web(details)
        if not results:
            return "I could not find results for that search."
        lines = []
        for i, r in enumerate(results[:5], 1):
            title = (r.get("title") or "Result").split(".")[0]
            lines.append(f"{i}. {title}")
        return "Here is what I found:\n" + "\n".join(lines)
