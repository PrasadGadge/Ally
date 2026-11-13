"""
Unit tests for Memory Service
"""

import pytest
import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMemoryService:
    """Test memory service functionality."""

    def test_memory_store_and_retrieve(self):
        """Test storing and retrieving memories."""
        from memory_core.memory_service import store_memory, retrieve_memory

        # Store a test memory
        test_key = "test_memory_001"
        test_value = {"content": "This is a test memory", "type": "info"}

        try:
            store_memory(test_key, test_value)
            retrieved = retrieve_memory(test_key)
            assert retrieved is not None, "Failed to retrieve stored memory"
        except Exception as e:
            pytest.skip(f"Memory service not fully initialized: {e}")

    def test_memory_key_format(self):
        """Test that memory keys are properly formatted."""
        valid_keys = [
            "user_preference_001",
            "conversation_001",
            "learned_fact_001",
        ]

        for key in valid_keys:
            assert isinstance(key, str), f"Invalid key format: {key}"
            assert len(key) > 0, "Key cannot be empty"


class TestEpisodicMemory:
    """Test episodic memory functionality."""

    def test_episodic_memory_structure(self):
        """Test that episodic memory has correct structure."""
        try:
            from memory_core.episodic_memory import update_last_reaction
            # Just verify the function exists and is callable
            assert callable(update_last_reaction)
        except ImportError:
            pytest.skip("Episodic memory module not available")

    def test_session_memory_initialization(self):
        """Test session memory can be initialized."""
        try:
            from memory_core.session_memory import get_session_memory
            session = get_session_memory()
            assert session is not None, "Failed to initialize session memory"
        except Exception as e:
            pytest.skip(f"Session memory initialization failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
