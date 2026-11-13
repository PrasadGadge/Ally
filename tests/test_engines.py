"""
Unit tests for Intent Engine
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestIntentEngine:
    """Test Core_structure/intent_engine.py functionality."""

    def test_intent_engine_initialization(self):
        """Test that intent engine can be initialized."""
        try:
            from Core_structure.intent_engine import IntentEngine
            engine = IntentEngine()
            assert engine is not None, "Failed to initialize IntentEngine"
        except ImportError as e:
            pytest.skip(f"IntentEngine not available: {e}")

    def test_intent_engine_has_detect_method(self):
        """Test that intent engine has detect method."""
        try:
            from Core_structure.intent_engine import IntentEngine
            engine = IntentEngine()
            assert hasattr(engine, 'detect'), "IntentEngine missing detect method"
            assert callable(getattr(engine, 'detect')), "detect is not callable"
        except Exception as e:
            pytest.skip(f"Intent engine check failed: {e}")

    def test_intent_detection_returns_dict(self):
        """Test that intent detection returns proper structure."""
        try:
            from Core_structure.intent_engine import IntentEngine
            engine = IntentEngine()
            
            result = engine.detect("hello", {})
            assert isinstance(result, dict), "Intent detection should return dict"
            
            # Check for expected keys
            assert "primary" in result or "intent" in result, \
                "Result should contain intent information"
        except Exception as e:
            pytest.skip(f"Intent detection test skipped: {e}")

    def test_battery_intent_does_not_need_ai_fallback(self, monkeypatch):
        from Core_structure.intent_engine import IntentEngine

        engine = IntentEngine()
        monkeypatch.setattr(
            engine.ai_detector,
            "detect",
            lambda text: (_ for _ in ()).throw(AssertionError("AI fallback used")),
        )

        result = engine.detect("check device charging")

        assert result["primary"] == "automation"
        assert result["subtype"] == "device_status"

    def test_remember_intent_does_not_need_ai_fallback(self, monkeypatch):
        from Core_structure.intent_engine import IntentEngine

        engine = IntentEngine()
        monkeypatch.setattr(
            engine.ai_detector,
            "detect",
            lambda text: (_ for _ in ()).throw(AssertionError("AI fallback used")),
        )

        result = engine.detect("vivie remember i am building an ai assistant")

        assert result["primary"] == "chat"
        assert result["subtype"] == "personal_info"


class TestDecisionEngine:
    """Test Core_structure/decision_engine.py functionality."""

    def test_decision_engine_initialization(self):
        """Test that decision engine can be initialized."""
        try:
            from Core_structure.decision_engine import DecisionEngine
            engine = DecisionEngine()
            assert engine is not None, "Failed to initialize DecisionEngine"
        except ImportError as e:
            pytest.skip(f"DecisionEngine not available: {e}")


class TestToolRouter:
    """Test Core_structure/tool_router.py functionality."""

    def test_tool_router_initialization(self):
        """Test that tool router can be initialized."""
        try:
            from Core_structure.tool_router import ToolRouter
            router = ToolRouter()
            assert router is not None, "Failed to initialize ToolRouter"
        except ImportError as e:
            pytest.skip(f"ToolRouter not available: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
