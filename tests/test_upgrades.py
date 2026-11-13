"""
Unit tests for the new Vivie Brain Upgrades:
- Smart History Compression
- Adaptive Context Builder
- Semantic Episodic Retrieval
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_context_builder_priorities_and_truncation():
    """Verify that ContextBuilder prioritizes and truncates correctly under budget."""
    from Brain import context_builder

    # Very large strings to trigger budget truncation
    huge_user = "U" * 1500
    huge_cot = "C" * 2000
    huge_mem = "M" * 4000
    huge_hist = "H" * 4000
    huge_kn = "K" * 4000

    # Total chars = 15500, which exceeds MAX_CHAR_BUDGET (12000)
    result = context_builder.build_context(
        user_model_context=huge_user,
        cot_context=huge_cot,
        episodic_memory=huge_mem,
        session_history=huge_hist,
        knowledge_context=huge_kn,
        max_chars=12000
    )

    assert "[USER PROFILE]" in result
    assert "[REASONING ENGINE]" in result
    assert "[PAST EXPERIENCES]" in result
    assert "[CONVERSATION HISTORY]" in result
    
    # RAG knowledge has lowest priority, so it should be truncated out or severely limited
    # Total characters of higher priorities:
    # User profile (1500) + Reasoning (2000) + Past experiences (3000) + History (3000) = 9500.
    # Remaining for RAG: 12000 - 9500 = 2500.
    assert len(result) <= 13000  # including labels


def test_history_manager_add_and_format():
    """Verify that HistoryManager adds turns correctly and formats them."""
    from Brain import history_manager
    history_manager._recent_turns.clear()
    
    history_manager.add_turn("User", "Hello Vivie")
    history_manager.add_turn("Vivie", "Hi Boss!")
    
    block = history_manager.get_history_block()
    assert "[RECENT TURNS]" in block
    assert "User: Hello Vivie" in block
    assert "Vivie: Hi Boss!" in block


def test_semantic_episodic_memory_fallback():
    """Verify episodic memory retrieval functions without crashing."""
    from memory_core import episodic_memory
    
    # Storing and retrieving a test episode
    episodic_memory.store_episode(
        user_input="test query for semantic memory",
        vivie_response="This is a test response",
        intent="general"
    )
    
    results = episodic_memory.retrieve_episodes("test query", top_k=1)
    assert len(results) > 0
    assert results[0]["user_input"] == "test query for semantic memory"
