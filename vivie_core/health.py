"""
Production health checks — run at startup and on demand.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vivie_core.log_util import LOG, warn


@dataclass
class HealthReport:
    ok: bool = True
    components: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_warning(self, msg: str) -> None:
        self.warnings.append(msg)
        LOG.warning("Health: %s", msg)

    def add_error(self, msg: str) -> None:
        self.errors.append(msg)
        self.ok = False
        LOG.error("Health: %s", msg)


def check_stt() -> dict:
    try:
        from SpeechToText import vivie_stt
        if hasattr(vivie_stt, "get_health"):
            return vivie_stt.get_health()
        return {"audio": False}
    except Exception as exc:
        warn("STT health", exc)
        return {"error": str(exc)}


def check_tts() -> dict:
    try:
        from TextToSpeech import Fast_DF_TTS as tts
        if hasattr(tts, "get_health"):
            return tts.get_health()
        return {}
    except Exception as exc:
        warn("TTS health", exc)
        return {"error": str(exc)}


def check_memory() -> dict:
    try:
        from memory_core import memory_service
        if hasattr(memory_service, "get_health"):
            return memory_service.get_health()
        return {}
    except Exception as exc:
        warn("memory health", exc)
        return {"error": str(exc)}


def check_automation() -> dict:
    try:
        from Automation import Automation_brain as ab
        if hasattr(ab, "get_health"):
            return ab.get_health()
        return {}
    except Exception as exc:
        warn("automation health", exc)
        return {"error": str(exc)}


def run_full_check() -> HealthReport:
    from vivie_core.settings import has_groq, has_mem0

    report = HealthReport()

    report.components["stt"] = check_stt()
    stt = report.components["stt"]
    # Distinguish between missing dependencies and missing backends
    if not stt.get("audio"):
        report.add_error("Audio dependencies unavailable (sounddevice/numpy)")
    elif not stt.get("groq") and not stt.get("local_whisper"):
        report.add_error("No STT backend (set GROQ_API_KEY or install faster-whisper)")

    report.components["tts"] = check_tts()
    tts = report.components["tts"]
    if not tts.get("edge_tts"):
        report.add_warning("edge-tts missing — speech disabled")
    if not tts.get("streaming"):
        report.add_warning("TTS streaming off — install ffmpeg for lower latency")

    report.components["memory"] = check_memory()
    if not has_mem0():
        report.add_warning("MEM0_API_KEY not set — cloud long-term memory disabled")

    report.components["automation"] = check_automation()
    if not report.components["automation"].get("pyautogui"):
        report.add_warning("pyautogui missing — desktop automation limited")

    if not has_groq():
        report.add_warning("GROQ_API_KEY not set — using local Whisper only")

    try:
        from vivie_core.metrics import snapshot
        report.components["metrics"] = snapshot()
    except Exception as exc:
        warn("metrics snapshot", exc)

    try:
        from Core_structure.tool_manifest import discover_tools
        from vivie_core.registry import list_registered
        discover_tools()
        report.components["tools"] = list_registered()
    except Exception as exc:
        warn("tool list", exc)

    return report


def format_report(report: HealthReport) -> str:
    lines = ["=== Vivie Health ===", f"Status: {'OK' if report.ok else 'DEGRADED'}"]
    for name, data in report.components.items():
        lines.append(f"  {name}: {data}")
    for w in report.warnings:
        lines.append(f"  WARN: {w}")
    for e in report.errors:
        lines.append(f"  ERR:  {e}")
    return "\n".join(lines)
