import json
import re

# Lazy imports to avoid import-chain hangs during module load
_intent_classifier_prompt = None
_system_llm_func = None

def _get_intent_classifier_prompt():
    """Lazy import of intent classifier prompt."""
    global _intent_classifier_prompt
    if _intent_classifier_prompt is None:
        try:
            from Brain.prompt_core import INTENT_CLASSIFIER_PROMPT
            _intent_classifier_prompt = INTENT_CLASSIFIER_PROMPT
        except Exception as e:
            print(f"[AIIntent] Failed to load intent classifier prompt: {e}")
            return None
    return _intent_classifier_prompt

def _get_system_llm():
    """Lazy import of system LLM function."""
    global _system_llm_func
    if _system_llm_func is None:
        try:
            from Brain.system_llm import system_llm
            _system_llm_func = system_llm
        except Exception as e:
            print(f"[AIIntent] Failed to load system LLM: {e}")
            return None
    return _system_llm_func

class AIIntentDetector:

    def extract_json(self, text):
        match = re.search(r"\{.*\}",text,re.DOTALL)
        if match:
            return match.group()
        return None

    def detect(self, text):
        prompt_template = _get_intent_classifier_prompt()
        llm_func = _get_system_llm()

        if not prompt_template or not llm_func:
            # Fallback if imports fail
            return {
                "primary": "chat",
                "subtype": "general",
                "confidence": 0.5
            }

        prompt = prompt_template.format(text=text)

        try:
            response = llm_func(prompt)
        except Exception as e:
            print(f"[AIIntent] System LLM call failed: {e}")
            return {
                "primary": "chat",
                "subtype": "general",
                "confidence": 0.5
            }

        try:
            json_text = self.extract_json(response)
            if not json_text:
                raise ValueError("NO JSON detected")

            intent = json.loads(json_text)
            if "primary" not in intent:
                raise ValueError("Missing primary intent")
            return intent

        except Exception as e:
            print("intent parse error:",e)
            return {
                "primary": "chat",
                "subtype": "general",
                "confidence": 0.6
            }