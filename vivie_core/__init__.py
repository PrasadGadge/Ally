"""
Vivie 2.0 core — modular pipeline, unified registry, structured logging.

Public API (stable for imports):
  start_vivie, process_text, input_queue, output_queue
"""

from vivie_core.runtime import start_vivie
from vivie_core.processor import process_text
from vivie_core.state import input_queue, output_queue, processing_lock

__all__ = [
    "start_vivie",
    "process_text",
    "input_queue",
    "output_queue",
    "processing_lock",
]
