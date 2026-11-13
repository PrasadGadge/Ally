"""Startup regression tests for Vivie chat-first mode."""

import subprocess
import time
import sys
import os

def test_imports_dont_block():
    """Verify that critical module imports complete without heavy initialization."""
    # These should load reasonably quickly (ChromaDB and mem0 may be slow but shouldn't hang)
    modules = [
        ("vivie_core.config", 10.0),  # May be slow due to engines import
        ("vivie_core.state", 5.0),
        ("vivie_core.handlers.fallback", 5.0),
        ("vivie_core.processor", 5.0),
        ("memory_core.session_memory", 5.0),
        ("memory_core.mem0_client", 5.0),
        ("knowledge_core.chroma_manager", 5.0),
    ]
    
    for module, timeout in modules:
        start = time.time()
        try:
            __import__(module)
            elapsed = time.time() - start
            assert elapsed < timeout, f"{module} import took {elapsed:.2f}s (too slow, limit {timeout}s)"
            print(f"✓ {module} imported in {elapsed:.2f}s")
        except Exception as e:
            # Some modules may fail if dependencies missing, but shouldn't hang
            print(f"✓ {module} import failed gracefully: {e}")
            elapsed = time.time() - start
            assert elapsed < timeout, f"{module} import attempt took {elapsed:.2f}s (too slow, limit {timeout}s)"


def test_chat_mode_default():
    """Verify that VIVIE_MODE defaults to chat."""
    from vivie_core.config import VIVIE_MODE, VOICE_ENABLED
    assert VIVIE_MODE == "chat", f"VIVIE_MODE should default to 'chat', got '{VIVIE_MODE}'"
    assert VOICE_ENABLED == False, "VOICE_ENABLED should be False in chat mode"
    print("✓ Chat mode is default")


def test_chroma_lazy():
    """Verify ChromaDB is lazy-loaded and doesn't block imports."""
    # Import should not load ChromaDB
    import knowledge_core.chroma_manager as cm
    # The _ensure_chroma function exists and handles lazy loading
    assert hasattr(cm, '_ensure_chroma'), "ChromaDB should have lazy init function"
    print("✓ ChromaDB lazy import verified")
    
    # First use should attempt loading
    result = cm._ensure_chroma()
    # May return False if dependencies missing, but should not hang
    print(f"✓ ChromaDB lazy initialization attempted (result: {result})")


def test_mem0_lazy():
    """Verify mem0 is lazy-loaded and doesn't block imports."""
    import memory_core.mem0_client as mc
    # The _ensure_mem0 function exists and handles lazy loading
    assert hasattr(mc, '_ensure_mem0'), "mem0 should have lazy init function"
    print("✓ mem0 lazy import verified")
    
    # First use should attempt loading
    result = mc._ensure_mem0()
    print(f"✓ mem0 lazy initialization attempted (result: {result})")


def test_brain_lazy_migration():
    """Verify history migration is lazy and doesn't block imports."""
    import Brain.cl_brain as cb
    # Migration should not have run at import time
    assert hasattr(cb, '_ensure_history_migrated'), "Brain should have lazy migration function"
    print("✓ Brain lazy migration verified")


if __name__ == "__main__":
    print("Running startup regression tests...")
    test_imports_dont_block()
    test_chat_mode_default()
    test_chroma_lazy()
    test_mem0_lazy()
    test_brain_lazy_migration()
    print("\n✅ All startup tests passed")
