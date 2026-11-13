# ==========================================
# Core_structure/llm_intent_router.py
# Phase 4/5: Primary LLM Router
# Supports single-tool and multi-tool responses
# ==========================================

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from Core_structure.tool_schema import build_function_schemas
from Brain.tiered_brain import api_generate_response, TIER_FAST

logger = logging.getLogger("LLMRouter")

# ─────────────────────────────────────────────────────────────────────────
# ROUTER PROMPT
# Phase 5 upgrade: supports returning multiple tools for compound queries.
# ─────────────────────────────────────────────────────────────────────────

ROUTER_PROMPT = """You are Vivie's semantic router — a precision intent classifier.

Your ONLY job is to map the user's request to the correct tool(s) from the tool registry.
Do NOT answer the question. Do NOT generate explanations. Return ONLY raw JSON.

Available Tools:
{tool_schemas}

User Request: "{user_text}"

RULES:
1. If the request maps to ONE tool, return:
{{
    "tool": "<action_type from the tool list>",
    "arguments": {{"<param_name>": "<param_value>"}},
    "confidence": 0.95
}}

2. If the request needs MULTIPLE tools (compound query), return:
{{
    "tool": "<primary action_type>",
    "arguments": {{"<param_name>": "<param_value>"}},
    "confidence": 0.95,
    "extra_tools": [
        {{"tool": "<second action_type>", "arguments": {{...}}}},
        {{"tool": "<third action_type>", "arguments": {{...}}}}
    ]
}}

3. If it is casual chat, a greeting, or a general question that no tool can satisfy, return:
{{
    "tool": null,
    "arguments": {{}},
    "confidence": 1.0
}}

CRITICAL: Return ONLY the raw JSON object. No markdown. No ```json. No explanations.
"""


def _call_llm(user_text: str) -> str:
    schemas     = build_function_schemas()
    schema_json = json.dumps(schemas, indent=2)
    prompt      = ROUTER_PROMPT.format(tool_schemas=schema_json, user_text=user_text)
    # Force Tier 0 (Fast) — minimize latency
    return api_generate_response(prompt, forced_tier=TIER_FAST)


def route_with_llm(user_text: str, timeout_seconds: float = 2.5) -> dict | None:
    """
    Route user text to one or more tools using the LLM.

    Returns:
        dict with keys: tool, arguments, confidence, extra_tools (optional)
        None if the LLM failed, timed out, or returned invalid JSON.
    
    ENHANCEMENT: Low-confidence classifications (< 0.70) trigger fallback
    to keyword-based intent engine for clarification.
    """
    response_text = ""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future        = executor.submit(_call_llm, user_text)
            response_text = future.result(timeout=timeout_seconds)

            if not response_text:
                return None

            # Strip markdown wrappers the model might add despite instructions
            clean = response_text.strip()
            for wrapper in ("```json", "```"):
                if clean.startswith(wrapper):
                    clean = clean[len(wrapper):]
            if clean.endswith("```"):
                clean = clean[:-3]

            parsed = json.loads(clean.strip())

            # Validate minimum required keys
            if "tool" not in parsed:
                logger.warning("[LLMRouter] Response missing 'tool' key: %s", clean[:80])
                return None

            # Normalise arguments key
            if "arguments" not in parsed:
                parsed["arguments"] = {}

            # Normalise extra_tools key (Phase 5)
            if "extra_tools" not in parsed:
                parsed["extra_tools"] = []

            # ENHANCEMENT: Low-confidence fallback
            # If confidence is below threshold, trigger fallback to keyword engine
            confidence = parsed.get("confidence", 0.0)
            if confidence < 0.70:
                logger.warning(
                    "[LLMRouter] Low confidence (%.2f) for: '%s' — triggering fallback",
                    confidence, user_text[:40]
                )
                # Return None to trigger keyword engine fallback
                return None

            return parsed

    except TimeoutError:
        logger.warning(
            "[LLMRouter] Timeout (%.1fs) for: '%s'", timeout_seconds, user_text[:40]
        )
        return None
    except json.JSONDecodeError as e:
        # Check if response is the generic fallback (LLM tiers failed)
        if "unable to process" in response_text.lower() or "offline" in response_text.lower():
            logger.warning("[LLMRouter] LLM tiers unavailable — routing to null (chat)")
            return {"tool": None, "arguments": {}, "confidence": 1.0}
        logger.error("[LLMRouter] JSON parse error: %s. Raw: %s", e, response_text[:100])
        return None
    except Exception as e:
        logger.error("[LLMRouter] Unexpected error: %s", e)
        return None
