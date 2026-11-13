"""
Regression tests for bugs fixed in audit session.
Tests that previously broken functionality now works correctly.
"""

import pytest
from Core_structure.llm_intent_router import route_with_llm
from Brain.tiered_brain import TIER_FAST, TIER_ADVANCED, TIERS


class TestTierLocalFix:
    """Test that TIER_LOCAL constant issue is fixed."""
    
    def test_tier_constants_exist(self):
        """TIER_FAST and TIER_ADVANCED should be defined."""
        assert TIER_FAST == 0
        assert TIER_ADVANCED == 1
    
    def test_tiers_dict_has_two_entries(self):
        """TIERS dict should have exactly 2 entries."""
        assert len(TIERS) == 2
        assert TIER_FAST in TIERS
        assert TIER_ADVANCED in TIERS
    
    def test_intent_router_imports_work(self):
        """Intent router should import without errors after TIER_LOCAL fix."""
        from Core_structure.llm_intent_router import route_with_llm
        assert callable(route_with_llm)


class TestIntentRouterFallback:
    """Test that intent router handles LLM fallback gracefully."""
    
    def test_intent_router_handles_plain_text_fallback(self):
        """
        When LLM returns plain text (fallback message),
        router should return null intent (chat) instead of crashing.
        """
        # This test verifies the fix in llm_intent_router.py
        # where we check for "unable to process" in response
        from Core_structure.llm_intent_router import route_with_llm
        
        # Test with simple query - should not crash even if LLM returns fallback
        # (We can't easily mock the LLM response here, but we verify import works)
        result = route_with_llm("test query", timeout_seconds=1.0)
        
        # Result should be either a dict with tool info or None
        # Should never raise an exception
        assert result is None or isinstance(result, dict)


class TestTieredBrainFallback:
    """Test that tiered brain uses intent-matched fallbacks."""
    
    def test_offline_fallbacks_exist(self):
        """OFFLINE_FALLBACKS should be defined in prompt_core."""
        from Brain.prompt_core import OFFLINE_FALLBACKS
        assert isinstance(OFFLINE_FALLBACKS, dict)
        assert len(OFFLINE_FALLBACKS) > 0
    
    def test_offline_fallbacks_has_general(self):
        """OFFLINE_FALLBACKS should have a 'general' fallback."""
        from Brain.prompt_core import OFFLINE_FALLBACKS
        assert "general" in OFFLINE_FALLBACKS
        assert isinstance(OFFLINE_FALLBACKS["general"], str)
        assert len(OFFLINE_FALLBACKS["general"]) > 0
    
    def test_offline_fallbacks_common_intents(self):
        """Common intents should have specific fallbacks."""
        from Brain.prompt_core import OFFLINE_FALLBACKS
        common_intents = ["chat", "code", "research", "deep"]
        for intent in common_intents:
            assert intent in OFFLINE_FALLBACKS, f"Missing fallback for intent: {intent}"


class TestSecurityImprovments:
    """Test security improvements in subprocess calls."""
    
    def test_open_app_whitelist_exists(self):
        """APP_MAP whitelist should exist and be non-empty."""
        from Automation.open_App import APP_MAP
        assert isinstance(APP_MAP, dict)
        assert len(APP_MAP) > 0
    
    def test_open_app_blocks_unknown(self):
        """Unknown app requests should be blocked."""
        from Automation.open_App import open_App
        result = open_App("malicious_app")
        assert result is False
    
    def test_open_app_only_allows_whitelisted(self):
        """Only whitelisted apps should be allowed."""
        from Automation.open_App import APP_MAP, open_App
        
        # Check that all keys in APP_MAP are safe, known applications
        safe_apps = {"chrome", "google", "youtube", "spotify", "notepad", 
                     "calculator", "cmd", "paint", "settings", "explorer"}
        
        for app in APP_MAP.keys():
            assert app in safe_apps, f"Unsafe app in whitelist: {app}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
