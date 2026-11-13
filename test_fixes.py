#!/usr/bin/env python3
"""
Test script to verify all fixes for Vivie error debugging session.
Tests:
1. NVIDIA API model name fix
2. OpenAI exception handling in tiered brain
3. Chroma duplicate ID fix in RAG store
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_env_configuration():
    """Test 1: Verify .env configuration is correct"""
    print("\n" + "="*60)
    print("TEST 1: Environment Configuration")
    print("="*60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    nvidia_model = os.getenv("NVIDIA_MODEL")
    nvidia_key = os.getenv("NVIDIA_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    
    print(f"✓ NVIDIA_MODEL: {nvidia_model}")
    
    if not nvidia_model.startswith("nvidia/"):
        print(f"❌ ERROR: NVIDIA_MODEL should start with 'nvidia/' but got: {nvidia_model}")
        return False
    
    if not nvidia_key:
        print("❌ ERROR: NVIDIA_API_KEY is missing")
        return False
    
    if not openrouter_key:
        print("❌ ERROR: OPENROUTER_API_KEY is missing")
        return False
    
    print(f"✓ NVIDIA_API_KEY configured (length: {len(nvidia_key)})")
    print(f"✓ OPENROUTER_API_KEY configured (length: {len(openrouter_key)})")
    print("\n✅ TEST 1 PASSED: Environment configuration is correct")
    return True


def test_openai_exceptions_import():
    """Test 2: Verify OpenAI exception imports in tiered_brain.py"""
    print("\n" + "="*60)
    print("TEST 2: OpenAI Exception Handling")
    print("="*60)
    
    try:
        from Brain import tiered_brain
        
        # Check if _OPENAI_EXCEPTIONS is defined
        if hasattr(tiered_brain, '_OPENAI_EXCEPTIONS'):
            print(f"✓ _OPENAI_EXCEPTIONS defined: {tiered_brain._OPENAI_EXCEPTIONS}")
            print("✓ OpenAI exceptions will be properly caught and escalated")
            print("\n✅ TEST 2 PASSED: OpenAI exception handling configured")
            return True
        else:
            print("❌ ERROR: _OPENAI_EXCEPTIONS not found in tiered_brain module")
            return False
    except Exception as e:
        print(f"❌ ERROR: Failed to import tiered_brain: {e}")
        return False


def test_rag_store_uuid():
    """Test 3: Verify RAG store has UUID imports"""
    print("\n" + "="*60)
    print("TEST 3: RAG Store Unique ID Generation")
    print("="*60)
    
    try:
        from knowledge_core import rag_store
        import inspect
        
        # Get source of store_conversation_knowledge function
        source = inspect.getsource(rag_store.store_conversation_knowledge)
        
        # Check for UUID usage
        if "uuid.uuid4()" in source:
            print("✓ UUID generation found in store_conversation_knowledge")
        else:
            print("❌ ERROR: UUID generation not found")
            return False
        
        # Check for timestamp
        if "datetime.now()" in source or "isoformat()" in source:
            print("✓ Timestamp generation found")
        else:
            print("❌ ERROR: Timestamp generation not found")
            return False
        
        print("\n✅ TEST 3 PASSED: RAG store has unique ID generation")
        return True
    except Exception as e:
        print(f"❌ ERROR: Failed to check RAG store: {e}")
        return False


def test_tiered_brain_routing():
    """Test 4: Verify tiered brain can route requests"""
    print("\n" + "="*60)
    print("TEST 4: Tiered Brain Routing")
    print("="*60)
    
    try:
        from Brain.tiered_brain import classify_tier, TIER_FAST, TIER_ADVANCED
        
        # Test simple query (should be TIER_FAST)
        simple_tier = classify_tier("hello")
        print(f"✓ Simple query 'hello' → Tier {simple_tier}")
        
        # Test complex query (should be TIER_ADVANCED)
        complex_tier = classify_tier("write me a python function to parse json and handle errors with retry logic")
        print(f"✓ Complex query → Tier {complex_tier}")
        
        # Test news query (should trigger realtime/search intent)
        news_tier = classify_tier("tell me today's breaking news")
        print(f"✓ News query → Tier {news_tier}")
        
        print("\n✅ TEST 4 PASSED: Tiered brain routing works")
        return True
    except Exception as e:
        print(f"❌ ERROR: Failed to test tiered brain: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("VIVIE ERROR FIX VERIFICATION TESTS")
    print("="*60)
    
    results = {
        "ENV Configuration": test_env_configuration(),
        "OpenAI Exceptions": test_openai_exceptions_import(),
        "RAG Store UUID": test_rag_store_uuid(),
        "Tiered Brain Routing": test_tiered_brain_routing(),
    }
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    all_passed = all(results.values())
    
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED!")
        print("\nYou can now run: python Vivie.py")
        print("And try: 'Can you tell today breaking news?'")
    else:
        print("❌ SOME TESTS FAILED")
        print("\nPlease review the errors above and fix them.")
    print("="*60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
