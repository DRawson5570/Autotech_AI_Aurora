#!/usr/bin/env python3
"""
Test the Autotech Expert model (no tools, pure LLM diagnostic reasoning).

Usage:
    python addons/mitchell_agent/test_autotech_expert.py
    python addons/mitchell_agent/test_autotech_expert.py --query "What usually goes wrong on a 2010 Honda Accord?"
"""

import asyncio
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import httpx

# Change to backend dir so secret key file is found
import os
REPO_ROOT = Path(__file__).parent.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
os.chdir(BACKEND_DIR)

# Add backend to path
sys.path.insert(0, str(BACKEND_DIR))
from open_webui.utils.auth import create_token

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def get_admin_token() -> str:
    """Generate a JWT token for the admin user."""
    db_path = Path(__file__).parent.parent.parent / "backend" / "data" / "webui.db"
    con = sqlite3.connect(str(db_path))
    row = con.execute("SELECT id, email FROM user WHERE role='admin' LIMIT 1").fetchone()
    con.close()
    
    if not row:
        raise Exception("No admin user found")
    
    user_id, email = row
    print(f"{CYAN}>>> Using admin: {email}{RESET}")
    return create_token({"id": user_id}, expires_delta=None)


async def test_chat(
    query: str,
    model: str = "gemini-2.5-flash",
    base_url: str = "http://localhost:8080"
):
    """Test the Autotech Expert model with a diagnostic query."""
    
    print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
    print(f"{BLUE}{BOLD}Autotech Expert Test{RESET}")
    print(f"{BLUE}{BOLD}{'='*60}{RESET}\n")
    
    token = get_admin_token()
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": query}],
        "stream": True
        # NOTE: No tool_ids - pure LLM reasoning
    }
    
    print(f"{CYAN}>>> Model: {model}{RESET}")
    print(f"{CYAN}>>> Query: {query}{RESET}")
    print(f"\n{YELLOW}--- Response ---{RESET}\n")
    
    start_time = time.time()
    full_response = ""
    
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{base_url}/api/chat/completions",
            headers=headers,
            json=payload
        ) as response:
            if response.status_code != 200:
                text = await response.aread()
                print(f"Error {response.status_code}: {text.decode()}")
                return False
                
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            print(content, end="", flush=True)
                            full_response += content
                    except json.JSONDecodeError:
                        continue
    
    elapsed = time.time() - start_time
    
    print(f"\n\n{YELLOW}--- End Response ---{RESET}\n")
    print(f"{GREEN}✓ Completed in {elapsed:.1f}s{RESET}")
    
    # Check for structured response
    has_diagnosis = "DIAGNOSIS" in full_response.upper()
    has_check_first = "CHECK FIRST" in full_response.upper()
    has_common_cause = "COMMON CAUSE" in full_response.upper()
    has_next_step = "NEXT STEP" in full_response.upper()
    
    print(f"\n{BOLD}Response Structure:{RESET}")
    print(f"  DIAGNOSIS:    {'✓' if has_diagnosis else '✗'}")
    print(f"  CHECK FIRST:  {'✓' if has_check_first else '✗'}")
    print(f"  COMMON CAUSE: {'✓' if has_common_cause else '✗'}")
    print(f"  NEXT STEP:    {'✓' if has_next_step else '✗'}")
    
    return True


async def main():
    parser = argparse.ArgumentParser(description="Test Autotech Expert model")
    parser.add_argument("--query", type=str, 
                       default="My 2015 Chevy Malibu is running rough and has code P0300. What should I check first?",
                       help="Diagnostic query to test")
    parser.add_argument("--model", type=str, default="gemini-2.5-flash",
                       help="Model to use")
    parser.add_argument("--base-url", type=str, default="http://localhost:8080",
                       help="Open WebUI base URL")
    
    args = parser.parse_args()
    
    success = await test_chat(
        query=args.query,
        model=args.model,
        base_url=args.base_url
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
