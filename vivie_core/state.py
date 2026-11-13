"""Shared runtime state — queues, locks, session flags."""

import threading
from queue import Queue

input_queue: Queue = Queue()
output_queue: Queue = Queue()

processing_lock = threading.Lock()
_news_results_lock = threading.Lock()

VIVIE_ACTIVE = True
last_processed = ""
last_processed_at = 0.0
last_news_results: list = []

# Track input source for debugging and prevention of self-listening
# Values: "text", "voice", "system"
INPUT_SOURCE_TEXT = "text"
INPUT_SOURCE_VOICE = "voice"
INPUT_SOURCE_SYSTEM = "system"
