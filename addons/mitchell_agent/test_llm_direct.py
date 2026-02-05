#!/usr/bin/env python3
"""
Direct LLM Test - Bypasses Open WebUI to test if Gemini reliably includes images.

Tests whether the issue is:
- Gemini itself (fails here too)
- How we construct/deliver prompts through Open WebUI (works here, fails in Open WebUI)
"""

import asyncio
import httpx
import os
import sys
from pathlib import Path

# Sample image markdown that would come from the tool
SAMPLE_IMAGES = """
![Fig 1: Automatic A/C Circuit (1 of 3) (Part 1)](/static/mitchell/diagram_abc123.png)
![Fig 1: Automatic A/C Circuit (1 of 3) (Part 2)](/static/mitchell/diagram_def456.png)
![Fig 1: Automatic A/C Circuit (1 of 3) (Part 3)](/static/mitchell/diagram_ghi789.png)
![Fig 1: Automatic A/C Circuit (1 of 3) (Part 4)](/static/mitchell/diagram_jkl012.png)
![Fig 1: Automatic A/C Circuit (1 of 3) (Part 5)](/static/mitchell/diagram_mno345.png)
![Fig 1: Automatic A/C Circuit (1 of 3) (Part 6)](/static/mitchell/diagram_pqr678.png)
"""

# The RAG template we use
RAG_TEMPLATE = """### Task:
You are Aurora AI, a sovereign automotive diagnostic assistant for professional mechanics.

### Source Context:
{context}

### MOST IMPORTANT RULE - READ THIS FIRST:
If the context contains image markdown like ![...](/static/mitchell/...), those images ARE the data you must provide.
- Wiring diagrams = images. If user asks for wiring diagram and context has ![...] images, OUTPUT THOSE IMAGES.
- Do NOT say "DATA UNVERIFIED" if images exist - the images ARE the verified data!
- Copy all ![image](url) markdown EXACTLY into your response.

### Rules:
1. **Vehicle Details**: If query lacks Year/Make/Model/Engine AND context has no vehicle info, ask for it.
2. **Source Supremacy**: Use ONLY context data. Never say data unavailable if context has it.
3. **UNVERIFIED Rule**: ONLY say "DATA UNVERIFIED" if context has NO relevant data AND NO images.
4. **Citations**: Add [sourceid] after data.
5. **Tables**: Preserve exactly.
6. **IMAGES = DATA**: For wiring diagrams, the images ARE the data. Output them!

### Response Format:
- SUMMARY: (1-line)
- ACTION STEPS: (max 5)
- SPECS: (values from context, or N/A for diagram-only queries)
- IMAGES: (ALL ![...](...) markdown from context - REQUIRED if images exist)
- VERIFICATION: (how to confirm)
- RISKS: (safety)
- NEXT: (follow-up)

### User Query:
{query}"""

# Simulated tool result context
TOOL_CONTEXT = f"""**DIAGRAM IMAGES:**

{SAMPLE_IMAGES}

**Wiring Diagram Result**
Captured 6 wiring diagram(s) for the Automatic A/C Circuit.
The diagrams contain wire colors, pin numbers, connector IDs, and component locations.
Refer to the images above for specific values.

Vehicle: 2014 Chevrolet Cruze 1.4L LT
Source: Mitchell ProDemand
"""


async def test_gemini_direct(api_key: str, num_tests: int = 5, delay: int = 5):
    """Test Gemini directly with the same context we'd send through Open WebUI."""
    
    query = "Show me ac wiring diagram for 2014 chevy cruze 1.4 lt"
    prompt = RAG_TEMPLATE.format(context=TOOL_CONTEXT, query=query)
    
    print("=" * 60)
    print("Direct LLM Test - Gemini 2.5 Flash")
    print("=" * 60)
    print(f"Tests: {num_tests}, Delay: {delay}s")
    print(f"Context contains {SAMPLE_IMAGES.count('![')}) image(s)")
    print()
    
    results = {"pass": 0, "fail": 0, "empty": 0}
    
    async with httpx.AsyncClient(timeout=120) as client:
        for i in range(1, num_tests + 1):
            print(f"--- Test {i}/{num_tests} ---")
            
            try:
                response = await client.post(
                    "https://generativelanguage.googleapis.com/v1/models/gemini-2.5-flash:generateContent",
                    params={"key": api_key},
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": 0.7,
                            "maxOutputTokens": 4096
                        }
                    }
                )
                
                if response.status_code != 200:
                    print(f"  ❌ API Error: {response.status_code}")
                    print(f"     {response.text[:200]}")
                    results["fail"] += 1
                    continue
                
                data = response.json()
                
                # Extract response text
                candidates = data.get("candidates", [])
                if not candidates:
                    print("  ❌ Empty response (no candidates)")
                    results["empty"] += 1
                    continue
                
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    print("  ❌ Empty response (no parts)")
                    results["empty"] += 1
                    continue
                
                text = parts[0].get("text", "")
                
                if not text:
                    print("  ❌ Empty response text")
                    results["empty"] += 1
                    continue
                
                # Check for images in response
                image_count = text.count("/static/mitchell/diagram_")
                has_unverified = "DATA UNVERIFIED" in text
                has_impossible = "impossible" in text.lower() or "cannot provide" in text.lower()
                
                if image_count >= 6:
                    print(f"  ✅ PASS - {image_count} images included")
                    results["pass"] += 1
                elif image_count > 0:
                    print(f"  ⚠️ PARTIAL - Only {image_count}/6 images")
                    results["fail"] += 1
                elif has_impossible:
                    print(f"  ❌ FAIL - Hallucinated 'impossible'")
                    results["fail"] += 1
                elif has_unverified:
                    print(f"  ❌ FAIL - Said 'DATA UNVERIFIED' (ignored images)")
                    results["fail"] += 1
                else:
                    print(f"  ❌ FAIL - No images in response")
                    print(f"     Preview: {text[:150]}...")
                    results["fail"] += 1
                
            except Exception as e:
                print(f"  ❌ Exception: {e}")
                results["fail"] += 1
            
            if i < num_tests:
                await asyncio.sleep(delay)
    
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    total = num_tests
    print(f"Pass:  {results['pass']}/{total} ({results['pass']*100//total}%)")
    print(f"Fail:  {results['fail']}/{total}")
    print(f"Empty: {results['empty']}/{total}")
    
    return results["pass"] == total


async def main():
    # Get API key from environment or config
    api_key = os.environ.get("GOOGLE_API_KEY")
    
    if not api_key:
        # Try to get from Open WebUI config
        try:
            import sqlite3
            import json
            db_path = Path(__file__).parent.parent.parent / "backend" / "data" / "webui.db"
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM config LIMIT 1")
            row = cursor.fetchone()
            if row and row[0]:
                config = json.loads(row[0])
                if 'google' in config and 'api_keys' in config['google']:
                    keys = config['google']['api_keys']
                    if keys:
                        api_key = keys[0]
                        print(f"✓ Found API key in Open WebUI config")
            conn.close()
        except Exception as e:
            print(f"Could not get API key from config: {e}")
    
    if not api_key:
        print("ERROR: No GOOGLE_API_KEY found")
        print("Set GOOGLE_API_KEY environment variable or configure in Open WebUI")
        sys.exit(1)
    
    num_tests = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    delay = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    success = await test_gemini_direct(api_key, num_tests, delay)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
