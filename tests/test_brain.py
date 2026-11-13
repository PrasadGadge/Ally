"""
Unit tests for Brain modules - cl_brain.py and api_brain.py
"""

import pytest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# FIX: was importing production module at top level — fails with ImportError
# when run without full prod setup (no .env, no chromadb, no API keys).
# Now skips gracefully with a clear message.
cl_brain = pytest.importorskip(
    "Brain.cl_brain",
    reason="cl_brain not importable — check .env and dependencies"
)
detect_intent = cl_brain.detect_intent


class TestIntentDetection:
    """Test intent detection functionality."""

    def test_numeric_intent(self):
        """Test detection of numeric queries."""
        queries = [
            "How old is the earth?",
            "What is the age of the universe?",
            "When was Python created?",
            "How many stars are there?",
        ]
        for query in queries:
            intent = detect_intent(query)
            assert intent == "numeric", f"Failed for: {query}"

    def test_bio_intent(self):
        """Test detection of biographical queries."""
        queries = [
            "Who is Albert Einstein?",
            "Tell me about Elon Musk",
            "Biography of Marie Curie",
        ]
        for query in queries:
            intent = detect_intent(query)
            assert intent == "bio", f"Failed for: {query}"

    def test_deep_intent(self):
        """Test detection of deep/explanatory queries."""
        queries = [
            "Explain quantum computing",
            "Why is the sky blue?",
            "How does photosynthesis work?",
            "How do neural networks function?",
        ]
        for query in queries:
            intent = detect_intent(query)
            assert intent == "deep", f"Failed for: {query}"

    def test_code_intent(self):
        queries = [
            "Write a python function to sort a list",
            "Debug this code for me",
            "Implement binary search",
        ]
        for query in queries:
            assert detect_intent(query) == "code", f"Failed for: {query}"

    def test_realtime_intent(self):
        """Test detection of real-time queries."""
        queries = [
            "What is the current weather?",
            "Show me live stock prices",
            "Real time traffic updates",
            "Latest news today",
        ]
        for query in queries:
            intent = detect_intent(query)
            assert intent == "realtime", f"Failed for: {query}"


class TestSystemPrompt:
    """Test system prompt configuration."""

    def test_base_system_prompt_exists(self):
        """Verify base system prompt is configured."""
        from Brain.cl_brain import BASE_SYSTEM_PROMPT
        assert BASE_SYSTEM_PROMPT is not None
        assert "Vivie" in BASE_SYSTEM_PROMPT
        assert len(BASE_SYSTEM_PROMPT) > 100

    def test_base_system_prompt_contains_rules(self):
        """Verify system prompt contains key rules."""
        from Brain.cl_brain import BASE_SYSTEM_PROMPT
        required_rules = ["Never say", "personal AI", "Hard rules"]
        for rule in required_rules:
            assert rule in BASE_SYSTEM_PROMPT, f"Missing rule: {rule}"


class TestBrainHardening:
    def test_cot_generation_timeout_returns_empty(self, monkeypatch):
        import time
        from Brain import chain_of_thought as cot

        def slow_generate(*args, **kwargs):
            time.sleep(0.2)
            return "late"

        monkeypatch.setattr(cot, "api_generate_response", slow_generate)

        assert cot._generate_with_timeout("prompt", 0.01, "unit") == ""

    def test_response_verifier_timeout_returns_empty(self, monkeypatch):
        import time
        from Brain import response_verifier as verifier

        def slow_generate(*args, **kwargs):
            time.sleep(0.2)
            return "9"

        monkeypatch.setattr(verifier, "api_generate_response", slow_generate)

        assert verifier._generate_score_with_timeout("prompt", 0.01) == ""

    def test_explicit_user_model_update_does_not_call_llm(self, monkeypatch, tmp_path):
        from Brain import user_model

        monkeypatch.setattr(user_model, "_MODEL_FILE", tmp_path / "user_model.json")
        user_model._loaded = False
        user_model._model.clear()
        monkeypatch.setattr(
            user_model,
            "_extract_facts",
            lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("LLM extractor used")),
        )

        user_model.update_explicit("vivie remember i am building an ai assistant")
        import time
        time.sleep(0.2)

        snapshot = user_model.get_model_snapshot()
        facts = [f["fact"] if isinstance(f, dict) else f for f in snapshot["known_facts"]]
        assert "i am building an ai assistant" in facts

    def test_main_brain_accepts_and_injects_all_context(self, monkeypatch):
        from Brain import cl_brain, history_manager, tiered_brain

        captured = {}

        monkeypatch.setattr(cl_brain, "detect_intent", lambda text: "general")
        monkeypatch.setattr(history_manager, "add_turn", lambda *args, **kwargs: None)
        monkeypatch.setattr(history_manager, "get_history_block", lambda: "recent session turn")
        monkeypatch.setattr(history_manager, "save_history_to_file", lambda: None)

        def fake_generate(prompt, *args, **kwargs):
            captured["prompt"] = prompt
            captured["kwargs"] = kwargs
            return "All context wired."

        monkeypatch.setattr(tiered_brain, "api_generate_response", fake_generate)

        out = cl_brain.Main_Brain(
            "User: explain my project",
            cot_context="reasoning context",
            user_model_context="user profile context",
            episodic_memory="episodic memory context",
            knowledge_context="knowledge graph context",
            forced_tier=1,
        )

        assert out == "All context wired."
        assert captured["kwargs"]["forced_tier"] == 1
        prompt = captured["prompt"]
        assert "[USER PROFILE]" in prompt
        assert "user profile context" in prompt
        assert "[REASONING ENGINE]" in prompt
        assert "reasoning context" in prompt
        assert "[PAST EXPERIENCES]" in prompt
        assert "episodic memory context" in prompt
        assert "[CONVERSATION HISTORY]" in prompt
        assert "recent session turn" in prompt
        assert "[KNOWLEDGE RETRIEVAL]" in prompt
        assert "knowledge graph context" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
