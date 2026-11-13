"""
Production ToolManifest definitions — auto-registered at startup.
Add new tools here instead of editing main_brain / registry by hand.
"""

from Core_structure.tool_manifest import ToolManifest
from Features.check_internet_speed import get_internet_speed
from Features.create_file import create_file
from Features.image_generator import GenerateImages
from Features.weather_system import speak_forecast, speak_weather
from Features.whatsapp_bot import send_msg
"""
Production ToolManifest definitions — auto-registered at startup.
Add new tools here instead of editing main_brain / registry by hand.
"""

from Core_structure.tool_manifest import ToolManifest
from Features.check_internet_speed import get_internet_speed
from Features.create_file import create_file
from Features.image_generator import GenerateImages
from Features.weather_system import speak_forecast, speak_weather
from Features.whatsapp_bot import send_msg


class CreateFileTool(ToolManifest):
    name = "create_file"
    description = "Create a new file on disk"
    keywords = ["create file", "make a file", "new file"]
    action_type = "create_file"
    category = "files"
    parameters = {
        "type": "object",
        "properties": {
            "filename": {"type": "string", "description": "The exact name of the file to create, including extension"}
        },
        "required": ["filename"]
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        filename = kwargs.get("filename")
        if not filename:
            import re as _re
            text = details.strip()
            m = _re.search(r'(?:called|named)\s+["\']?([^\s"\']+)["\']?', text, _re.I)
            if m:
                filename = m.group(1)
            else:
                tokens = text.split()
                candidates = [t for t in tokens if '.' in t or (
                    t.lower() not in {
                        "create","make","new","a","an","the","file",
                        "me","please","my","for","and","with","in","on"
                    }
                )]
                filename = candidates[-1] if candidates else ""

        if not filename:
            return "Boss, what should I name the file?"
            
        import re as _re
        filename = _re.sub(r'[\\/:*?"<>|]', '', filename).strip(". ")
        created = create_file(filename)
        return f"Boss, '{created}' has been created."


class InternetSpeedTool(ToolManifest):
    name = "internet_speed"
    description = "Measure network speed"
    keywords = ["internet speed", "network speed", "speed test"]
    action_type = "check_internet_speed"
    category = "system"

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        speed = get_internet_speed()
        return str(speed) if speed is not None else "Unable to determine internet speed."


class WhatsAppTool(ToolManifest):
    name = "whatsapp"
    description = "Send a WhatsApp message"
    keywords = ["whatsapp", "send message on whatsapp"]
    action_type = "send_whatsapp"
    category = "communication"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "contact": {"type": "string", "description": "The name of the person to send the message to"},
            "message": {"type": "string", "description": "The content of the message"}
        }
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        # FIX: send_msg() is a void function (returns None always).
        # Checking its return value always gave "Failed to send WhatsApp message."
        # It handles the full voice dialog internally — just call it.
        try:
            send_msg(details)
            return "WhatsApp message flow started."
        except Exception as e:
            return f"Failed to start WhatsApp: {e}"


class WeatherTool(ToolManifest):
    name = "weather"
    description = "Current weather"
    keywords = ["weather", "temperature", "rain today"]
    action_type = "get_weather"
    category = "weather"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "The city to get the weather for"}
        }
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        city = kwargs.get("city")
        speak_weather(city)
        return "Weather updated."


class ForecastTool(ToolManifest):
    name = "forecast"
    description = "3-day weather forecast"
    keywords = ["forecast", "weather forecast"]
    action_type = "get_forecast"
    category = "weather"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "The city to get the forecast for"}
        }
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        speak_forecast(kwargs.get("city"))
        return "Forecast ready."


class ImageGenTool(ToolManifest):
    name = "image_gen"
    description = "Generate an image from a prompt"
    keywords = ["generate image", "draw", "create image", "make a picture"]
    action_type = "generate_image"
    category = "creative"
    requires_online = True
    parameters = {
        "type": "object",
        "properties": {
            "prompt": {"type": "string", "description": "The detailed visual description of the image to generate"}
        },
        "required": ["prompt"]
    }

    @staticmethod
    def handler(details: str, **kwargs) -> str:
        prompt = kwargs.get("prompt") or details
        result = GenerateImages(prompt)
        return result or "Image generation failed."
