# ==================================================
# log_config.py
# Suppress noisy third-party loggers
# Import this at the TOP of Vivie.py before anything else:
#   from log_config import suppress_noise
#   suppress_noise()
# ==================================================

import logging
import sys
import warnings


def _configure_stdio():
    """Keep console logging alive on Windows code pages that cannot print Unicode."""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def suppress_noise():
    """Silence noisy third-party library logs."""
    _configure_stdio()

    noisy_loggers = [
        "httpx",
        "httpcore",
        "sentence_transformers",
        "chromadb",
        "chromadb.telemetry",
        "opentelemetry",
        "websockets",
        "websockets.server",
        "comtypes",
        "comtypes.client",
        "comtypes.client._code_cache",
        "urllib3",
        # FIX: asyncio was ERROR — hides real TTS/Edge-TTS fetch failures.
        # WARNING keeps it visible enough to debug without flooding the console.
        "asyncio",
    ]

    for name in noisy_loggers:
        level = logging.WARNING if name == "asyncio" else logging.ERROR
        logging.getLogger(name).setLevel(level)

    # Suppress DeprecationWarnings from third-party packages
    warnings.filterwarnings("ignore", category=DeprecationWarning)

    # Keep Vivie's own logs clean but visible
    logging.basicConfig(
        level  = logging.WARNING,
        format = "[%(name)s] %(message)s"
    )

    try:
        from vivie_core.log_util import configure
        configure()
    except ImportError:
        pass

    print("Noisy loggers silenced.")
