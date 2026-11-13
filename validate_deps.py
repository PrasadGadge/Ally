#!/usr/bin/env python3
"""
Dependency validator for Vivie.
Run before starting: python validate_deps.py
"""

import sys
import argparse
import importlib.metadata
import importlib.util
import logging
from typing import List, Tuple

# Windows console (cp1252) safe markers
OK = "[OK]"
FAIL = "[FAIL]"
WARN = "[WARN]"


def check_python_version() -> bool:
    if sys.version_info < (3, 8):
        print(f"{FAIL} Python 3.8+ required. You have {sys.version}")
        return False
    print(f"{OK} Python {sys.version_info.major}.{sys.version_info.minor}")
    return True


def _import_name(pip_name: str) -> str:
    _MAP = {
        "python-dotenv": "dotenv",
        "google-genai": "google.genai",
        "edge-tts": "edge_tts",
        "faster-whisper": "faster_whisper",
        "pygame-ce": "pygame",
        "sounddevice": "sounddevice",
        "PyQt6": "PyQt6",
        "opencv-python": "cv2",
        "google-generativeai": "google.generativeai",
        "pywhatkit": "pywhatkit",
        "mem0ai": "mem0",
        "tavily-python": "tavily",
        "PyAutoGUI": "pyautogui",
    }
    return _MAP.get(pip_name, pip_name.replace("-", "_"))


def _check(pkg: str) -> bool:
    import_name = _import_name(pkg)
    try:
        return importlib.util.find_spec(import_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError):
        return False


def _version(pkg: str) -> str:
    try:
        return importlib.metadata.version(pkg)
    except importlib.metadata.PackageNotFoundError:
        pass
    return "unknown"


def validate() -> Tuple[List[str], List[str]]:
    critical = [
        "python-dotenv",
        "requests",
        "groq",
        "sounddevice",
        "numpy",
        "edge-tts",
        "pygame-ce",
        "openai",
        "google-genai",
        "websockets",
        "chromadb",
        "pydantic",
    ]

    optional = [
        "faster-whisper",
        "sentence-transformers",
        "mem0ai",
        "tavily-python",
        "pywhatkit",
        "PyAutoGUI",
        "opencv-python",
        "torch",
    ]

    missing_critical = []
    missing_optional = []

    print("\nCritical packages:")
    for pkg in critical:
        if _check(pkg):
            print(f"   {OK} {pkg} ({_version(pkg)})")
        else:
            print(f"   {FAIL} {pkg}  MISSING")
            missing_critical.append(pkg)

    print("\nOptional packages:")
    for pkg in optional:
        if _check(pkg):
            print(f"   {OK} {pkg} ({_version(pkg)})")
        else:
            print(f"   {WARN} {pkg}  (some features disabled)")
            missing_optional.append(pkg)

    return missing_critical, missing_optional


def main():
    parser = argparse.ArgumentParser(description="Check Vivie dependencies")
    parser.add_argument(
        "--health",
        action="store_true",
        help="Also run runtime health checks; may touch audio, tools, and network services.",
    )
    args = parser.parse_args()

    print("Vivie Dependency Check\n")

    if not check_python_version():
        sys.exit(1)

    missing_critical, missing_optional = validate()

    if missing_critical:
        print(f"\n{FAIL} {len(missing_critical)} critical packages missing.")
        print("   Install: pip install " + " ".join(missing_critical))
        sys.exit(1)

    if missing_optional:
        print(f"\n{WARN} {len(missing_optional)} optional packages missing.")
    else:
        print(f"\n{OK} All dependencies satisfied. Run: python Vivie.py")

    if args.health:
        run_health()
    else:
        print(f"{OK} Dependency check complete. Run with --health for runtime checks.")


def run_health():
    _quiet_health_loggers()
    try:
        from vivie_core.health import format_report, run_full_check
        print("\n" + format_report(run_full_check()))
    except ImportError as e:
        print(f"\n{WARN} Health check skipped: {e}")


def _quiet_health_loggers() -> None:
    for name in (
        "httpx",
        "httpcore",
        "ToolManifest",
        "chromadb",
        "chromadb.telemetry",
        "sentence_transformers",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


if __name__ == "__main__":
    main()
