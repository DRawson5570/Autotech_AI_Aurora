#!/usr/bin/env python3
"""
Test Gemini streaming directly to verify API behavior.
"""

import asyncio
import aiohttp
import json
import os
import sys

# Load API key
API_KEY_FILE = os.path.expanduser("~/gary_gemini_api_key")
with open(API_KEY_FILE) as f:
    API_KEY = f.read().strip()

# Models to test
MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro", 
    # "gemini-3-flash-preview",  # Uncomment to test Gemini 3
]

PROMPT = "Write a detailed 300-word essay about the history of automobiles, covering the invention, major developments, and modern electric vehicles."

async def test_streaming(model: str):
    """Test streaming with a specific model."""
    print(f"\n{'='*60}")
    print(f"Testing: {model}")
    print(f"{'='*60}")
    
    # Streaming endpoint with SSE
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?alt=sse&key={API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {
            "temperature": 1.0,  # Keep default for Gemini 3
            "maxOutputTokens": 256,
        }
    }
    
    print(f"URL: {url.replace(API_KEY, 'API_KEY')}")
    print(f"Prompt: {PROMPT}")
    print(f"\nStreaming response:")
    print("-" * 40)
    
    chunk_count = 0
    full_text = ""
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            print(f"Status: {response.status}")
            print(f"Content-Type: {response.headers.get('Content-Type')}")
            print("-" * 40)
            
            if response.status != 200:
                error = await response.text()
                print(f"ERROR: {error[:500]}")
                return
            
            # Read SSE stream - match the google.py logic exactly
            buffer = ""
            event_lines = []
            raw_chunk_count = 0
            
            async for chunk in response.content.iter_any():
                raw_chunk_count += 1
                if not chunk:
                    continue
                    
                try:
                    chunk_text = chunk.decode("utf-8", errors="ignore")
                except Exception:
                    continue
                    
                buffer += chunk_text
                print(f"\n[RAW CHUNK {raw_chunk_count}]: {repr(chunk_text[:100])}", flush=True)
                
                # Process lines (like google.py does)
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    stripped = line.strip()
                    
                    # Event boundary (empty line)
                    if stripped == "":
                        if not event_lines:
                            continue
                            
                        # Process accumulated event
                        for ev in event_lines:
                            if ev.startswith("data:"):
                                data = ev[5:].strip()  # Remove "data:" prefix
                                if data == "[DONE]":
                                    print("\n[DONE]")
                                    continue
                                    
                                try:
                                    obj = json.loads(data)
                                    candidates = obj.get("candidates", [])
                                    for candidate in candidates:
                                        parts = candidate.get("content", {}).get("parts", [])
                                        for part in parts:
                                            text = part.get("text", "")
                                            if text:
                                                chunk_count += 1
                                                full_text += text
                                                print(f"\n[CHUNK {chunk_count}]: {text}", flush=True)
                                except json.JSONDecodeError as e:
                                    print(f"\n[JSON Error: {e}]")
                        
                        event_lines = []
                        continue
                    
                    # Collect line
                    event_lines.append(stripped)
    
    print("\n" + "-" * 40)
    print(f"Total chunks received: {chunk_count}")
    print(f"Full text length: {len(full_text)}")


async def test_non_streaming(model: str):
    """Test non-streaming for comparison."""
    print(f"\n{'='*60}")
    print(f"Testing NON-STREAMING: {model}")
    print(f"{'='*60}")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": PROMPT}]}],
        "generationConfig": {
            "temperature": 1.0,
            "maxOutputTokens": 256,
        }
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as response:
            print(f"Status: {response.status}")
            
            if response.status != 200:
                error = await response.text()
                print(f"ERROR: {error[:500]}")
                return
            
            result = await response.json()
            text = result.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            print(f"Response (all at once): {text}")


async def main():
    print("Gemini Streaming Test")
    print("=" * 60)
    
    for model in MODELS:
        await test_streaming(model)
        await asyncio.sleep(1)  # Small delay between tests
    
    # Also test non-streaming for comparison
    print("\n\n" + "=" * 60)
    print("NON-STREAMING COMPARISON")
    print("=" * 60)
    
    for model in MODELS[:1]:  # Just test first model
        await test_non_streaming(model)


if __name__ == "__main__":
    asyncio.run(main())
