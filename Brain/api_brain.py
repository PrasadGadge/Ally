# ==========================================
# Brain/api_brain.py — Compatibility shim
# Forwards to the 2-tier router (NVIDIA fast + OpenRouter advanced).
# New code: import from Brain.tiered_brain directly.
# ==========================================

from Brain.tiered_brain import api_generate_response, stream_response

__all__ = ["stream_response", "api_generate_response"]
