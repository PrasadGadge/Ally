#!/usr/bin/env python3
"""
Direct test of breaking news query without STT/TTS
Tests the brain routing and response generation directly
"""

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

def test_breaking_news_query():
    """Test breaking news query directly via brain"""
    print("\n" + "="*60)
    print("TESTING: Breaking News Query")
    print("="*60)
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
        
        # Test 1: Check environment
        print("\n✓ Step 1: Checking environment...")
        nvidia_model = os.getenv("NVIDIA_MODEL")
        print(f"  NVIDIA_MODEL: {nvidia_model}")
        
        if not nvidia_model.startswith("nvidia/"):
            print("  ❌ ERROR: Model name doesn't have nvidia/ prefix!")
            return False
        print("  ✅ NVIDIA_MODEL correctly formatted")
        
        # Test 2: Import brain
        print("\n✓ Step 2: Importing brain components...")
        from Brain.tiered_brain import stream_response, classify_tier, TIERS
        print("  ✅ Brain imported successfully")
        
        # Test 3: Classify tier for breaking news query
        print("\n✓ Step 3: Classifying tier for 'breaking news' query...")
        query = "Can you tell today's breaking news?"
        tier = classify_tier(query)
        tier_name = TIERS[tier]['name']
        print(f"  Query: '{query}'")
        print(f"  → Tier: {tier} ({tier_name})")
        print("  ✅ Tier classification works")
        
        # Test 4: Stream response from brain
        print("\n✓ Step 4: Streaming response from brain...")
        print("  Sending query to brain...")
        
        response_text = ""
        try:
            for chunk in stream_response(query, forced_tier=None):
                response_text += chunk
                print(f"    {chunk}", end="", flush=True)
        except Exception as e:
            print(f"\n  ❌ ERROR during response: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        print("\n")
        
        if not response_text:
            print("  ❌ ERROR: No response from brain!")
            return False
        
        if "404" in response_text.lower() or "error" in response_text.lower():
            print(f"  ⚠️  Response contains error keywords: {response_text[:100]}")
            return False
        
        print(f"  ✅ Brain returned response ({len(response_text)} chars)")
        
        # Test 5: Check for cascading errors
        print("\n✓ Step 5: Checking for cascading errors...")
        
        if "All tiers failed" in response_text:
            print("  ❌ ERROR: All tiers failed (escalation not working)")
            return False
        
        if "404 page not found" in response_text:
            print("  ❌ ERROR: 404 error from NVIDIA (model name issue)")
            return False
        
        if "NO JSON" in response_text:
            print("  ❌ ERROR: JSON parsing failed")
            return False
        
        print("  ✅ No cascading errors detected")
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print(f"\nFull Response:\n{response_text}\n")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_breaking_news_query()
    sys.exit(0 if success else 1)
