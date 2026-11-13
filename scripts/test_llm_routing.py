import os
import sys
import time

# Add root directory to python path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from Core_structure.llm_intent_router import route_with_llm

QUERIES = [
    "What is the weather in Tokyo?",
    "Can you create a file called project_plan.txt for me?",
    "Hey Vivie, please check my unread emails on Gmail.",
    "Do I have any meetings tomorrow?",
    "Send a whatsapp to Mom saying I will be late.",
    "What's my internet speed right now?",
    "Generate an image of a cyberpunk city at night.",
    "How much is 245 times 18?",
    "Just wanted to say hi!",
    "Can you search the web for the latest Python 3.14 features?"
]

def run_tests():
    print("=" * 60)
    print("LLM ROUTING CUTOVER SIMULATOR")
    print("=" * 60)
    
    success_count = 0
    total = len(QUERIES)
    
    for i, query in enumerate(QUERIES, 1):
        print(f"\n[{i}/{total}] Query: '{query}'")
        
        start_time = time.time()
        result = route_with_llm(query, timeout_seconds=4.0)
        latency = (time.time() - start_time) * 1000
        
        if result and result.get("tool"):
            tool = result["tool"]
            args = result.get("arguments", {})
            print(f"[OK] Routed successfully in {latency:.0f}ms")
            print(f"   Tool: {tool}")
            print(f"   Args: {args}")
            success_count += 1
        elif result and result.get("tool") is None:
            print(f"[OK] Classified as chat in {latency:.0f}ms")
            print(f"   Tool: null")
            success_count += 1
        else:
            print(f"[FAIL] Failed or timed out ({latency:.0f}ms)")
            print(f"   Result returned: {result}")
            
    print("\n" + "=" * 60)
    print(f"RESULTS: {success_count}/{total} successful routes.")
    print("=" * 60)

if __name__ == "__main__":
    run_tests()
