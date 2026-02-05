#!/usr/bin/env python3
"""
Mitchell Chat E2E Test
======================

Tests the full chat flow as if a user sent a message in Open WebUI:
1. User sends natural language query
2. LLM recognizes it needs Mitchell data
3. LLM calls the appropriate Mitchell tool
4. Tool queues request to server
5. Agent processes and returns data
6. LLM formats response for user

This tests the COMPLETE user experience, not just the tool in isolation.

Prerequisites:
- Open WebUI running on localhost:8080
- Mitchell agent running

Usage:
    python addons/mitchell_agent/test_chat_e2e.py
    python addons/mitchell_agent/test_chat_e2e.py --query "What oil does a 2020 Toyota Camry need?"
    python addons/mitchell_agent/test_chat_e2e.py --api-key sk-xxx
"""

import asyncio
import argparse
import json
import os
import sys
import time
import sqlite3
from pathlib import Path
from typing import Optional

import httpx

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from open_webui.utils.auth import create_token

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


def print_header(text: str):
    print(f"\n{BLUE}{BOLD}{'='*60}{RESET}")
    print(f"{BLUE}{BOLD}{text}{RESET}")
    print(f"{BLUE}{BOLD}{'='*60}{RESET}\n")


def print_step(text: str):
    print(f"{CYAN}>>> {text}{RESET}")


def print_success(text: str):
    print(f"{GREEN}✓ {text}{RESET}")


def print_error(text: str):
    print(f"{RED}✗ {text}{RESET}")


def print_info(text: str):
    print(f"  {text}")


def get_admin_token() -> Optional[str]:
    """Generate a JWT token for the admin user from the database."""
    db_path = Path(__file__).parent.parent.parent / "backend" / "data" / "webui.db"
    if not db_path.exists():
        print_error(f"Database not found at {db_path}")
        return None
    
    try:
        con = sqlite3.connect(str(db_path))
        row = con.execute("SELECT id, email, role FROM user WHERE role='admin' LIMIT 1").fetchone()
        con.close()
        
        if not row:
            print_error("No admin user found in database")
            return None
        
        user_id, email, role = row
        print_info(f"Using admin account: {email}")
        
        # Create a token that doesn't expire
        token = create_token({"id": user_id}, expires_delta=None)
        return token
    except Exception as e:
        print_error(f"Failed to create token: {e}")
        return None


async def get_api_key(base_url: str, email: str, password: str) -> Optional[str]:
    """Get API key by logging in with credentials."""
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            # Login to get session
            response = await client.post(
                f"{base_url}/api/v1/auths/signin",
                json={"email": email, "password": password}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("token")
        except Exception as e:
            print_error(f"Failed to login: {e}")
            return None


async def send_chat_message(
    base_url: str,
    api_key: str,
    message: str,
    model: str = "gemini-2.5-pro",
    stream: bool = False,
    tool_ids: Optional[list] = None
) -> dict:
    """
    Send a chat message through the Open WebUI API.
    
    This mimics exactly what happens when you type in the chat interface.
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ],
        "stream": stream
    }
    
    # Add tool_ids if provided
    if tool_ids:
        payload["tool_ids"] = tool_ids
    
    async with httpx.AsyncClient(timeout=300) as client:
        if stream:
            # Streaming response
            full_response = ""
            async with client.stream(
                "POST",
                f"{base_url}/api/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
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
            print()  # Newline after streaming
            return {"content": full_response}
        else:
            # Non-streaming response
            response = await client.post(
                f"{base_url}/api/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract the assistant's response
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls", []),
                    "raw": data
                }
            return {"content": "", "raw": data}


async def run_chat_test(
    query: str,
    base_url: str = "http://localhost:8080",
    api_key: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    model: str = "gemini-2.5-pro",
    stream: bool = True
):
    """Run a chat test with a natural language query."""
    
    print_header("Mitchell Chat E2E Test")
    
    # Get API key if not provided
    if not api_key:
        if email and password:
            print_step("Logging in to get API key...")
            api_key = await get_api_key(base_url, email, password)
            if not api_key:
                print_error("Failed to get API key")
                return False
            print_success("Got API key from login")
        else:
            # Try to get from environment
            api_key = os.environ.get("OPENWEBUI_API_KEY")
            if not api_key:
                # Auto-generate from database
                print_step("Generating admin token from database...")
                api_key = get_admin_token()
                if not api_key:
                    print_error("No API key available. Use --api-key, --email/--password, or ensure database exists")
                    return False
                print_success("Generated admin token")
    
    print_step(f"Model: {model}")
    print_step(f"Query: {query}")
    print()
    
    start_time = time.time()
    
    try:
        print_step("Sending to Open WebUI chat API...")
        print_step("Requesting tool: mitchell_automotive_data")
        print(f"\n{YELLOW}--- LLM Response ---{RESET}\n")
        
        result = await send_chat_message(
            base_url=base_url,
            api_key=api_key,
            message=query,
            model=model,
            stream=stream,
            tool_ids=["mitchell_automotive_data"]
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n{YELLOW}--- End Response ---{RESET}\n")
        print_success(f"Completed in {elapsed:.1f}s")
        
        # Check if the response contains Mitchell data
        content = result.get("content", "")
        
        # Show the actual response content
        if content:
            print_step("Response content:")
            print(f"\n{content}\n")
        else:
            print_info("(Empty response content)")
        
        # Look for indicators that Mitchell tool was used
        mitchell_indicators = [
            "fluid", "oil", "coolant", "transmission",
            "capacit", "quart", "liter",
            "DTC", "P0", "diagnostic",
            "torque", "ft-lb", "N·m",
            "TSB", "bulletin",
            "ADAS", "calibration",
            "wiring", "diagram"
        ]
        
        tool_used = any(ind.lower() in content.lower() for ind in mitchell_indicators)
        
        # Check for REAL data vs fallback/clarification
        fallback_indicators = [
            "DATA UNVERIFIED IN LOCAL VAULT",
            "Reference OEM Manual",
            "not available in the current data vault",
            "I need the specific submodel",
            "I need the",
            "Can you confirm?",
            "Please specify",
            "Additional information needed"
        ]
        
        is_fallback = any(ind.lower() in content.lower() for ind in fallback_indicators)
        is_clarification = "submodel" in content.lower() and ("confirm" in content.lower() or "specify" in content.lower() or "need" in content.lower())
        
        # Check for actual spec data (real numbers/values)
        has_real_specs = any([
            "QTS" in content or "qts" in content,
            "GALS" in content or "gals" in content,
            "OZS" in content or "ozs" in content,
            "ft-lb" in content.lower() or "n·m" in content.lower() or "nm" in content.lower(),
            any(f"{i}.{j}" in content for i in range(1,20) for j in range(0,10)),  # Decimal numbers like "8.8", "15.6"
        ])
        
        print()
        print(f"{BOLD}=== DATA VERIFICATION ==={RESET}")
        if is_clarification:
            print(f"{YELLOW}⚠ CLARIFICATION REQUEST - Needs more vehicle info{RESET}")
        elif is_fallback and not has_real_specs:
            print(f"{RED}✗ FALLBACK RESPONSE - No real data retrieved{RESET}")
        elif has_real_specs:
            print(f"{GREEN}✓ REAL DATA - Contains actual specifications{RESET}")
        elif tool_used:
            print(f"{YELLOW}⚠ TOOL USED - But may not have specific data{RESET}")
        else:
            print(f"{RED}✗ NO MITCHELL DATA - Tool may not have been called{RESET}")
        print()
        
        if tool_used:
            print_success("Response appears to contain Mitchell data!")
        else:
            print_info("Response may not have used Mitchell tool (check if query requires it)")
        
        return True
        
    except httpx.HTTPStatusError as e:
        print_error(f"HTTP Error: {e.response.status_code}")
        try:
            text = e.response.read().decode() if hasattr(e.response, 'read') else str(e)
            print_info(f"Response: {text[:500]}")
        except:
            print_info(f"Could not read response body")
        return False
    except Exception as e:
        print_error(f"Error: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Test Mitchell agent through Open WebUI chat API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test fluid capacities query
  python test_chat_e2e.py --query "What are the fluid capacities for a 2018 Ford F-150 5.0L XL 2D Pickup 4WD?"
  
  # Test with specific API key
  python test_chat_e2e.py --api-key sk-xxx --query "What oil does a 2020 Toyota Camry need?"
  
  # Test with login credentials
  python test_chat_e2e.py --email user@example.com --password mypass --query "..."
  
  # Test wiring diagram
  python test_chat_e2e.py --query "Show me the starter wiring diagram for a 2019 Honda Civic"
  
  # Test preset scenarios
  python test_chat_e2e.py --preset fluids
  python test_chat_e2e.py --preset dtc
  python test_chat_e2e.py --preset tsb
  python test_chat_e2e.py --preset clarification
        """
    )
    
    # Preset test scenarios
    PRESETS = {
        "fluids": "What are the fluid capacities for a 2018 Ford F-150 with the 5.0L engine, XL trim, 2D Pickup body, 4WD?",
        "dtc": "What does DTC code P0301 mean on a 2019 Honda Civic 2.0L?",
        "tsb": "Are there any TSBs for a 2020 Toyota Camry 2.5L about transmission issues?",
        "torque": "What are the wheel lug nut torque specs for a 2018 Ford F-150?",
        "reset": "How do I reset the oil life monitor on a 2019 Honda Civic?",
        "clarification": "What are the fluid capacities for a 2018 Ford F-150?",  # Missing engine/trim - should trigger clarification
        "adas": "What ADAS calibrations are needed after windshield replacement on a 2021 Toyota RAV4?",
        "plate_lookup": "What vehicle is license plate AUE709 from Michigan?",
        "plate_fluids": "Look up plate AUE709 from Michigan and tell me the fluid capacities.",
        "plate_torque": "I have a car with plate AUE709, Michigan. What are the wheel lug nut torque specs?"
    }
    
    parser.add_argument(
        "--preset",
        type=str,
        choices=list(PRESETS.keys()),
        help="Use a preset test scenario"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Natural language query to send (overrides --preset)"
    )
    
    parser.add_argument(
        "--api-key",
        type=str,
        help="Open WebUI API key"
    )
    
    parser.add_argument(
        "--email",
        type=str,
        help="Open WebUI login email"
    )
    
    parser.add_argument(
        "--password",
        type=str,
        help="Open WebUI login password"
    )
    
    parser.add_argument(
        "--base-url",
        type=str,
        default="http://localhost:8080",
        help="Open WebUI base URL"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="gemini-2.5-pro",
        help="Model to use for chat"
    )
    
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming (wait for full response)"
    )
    
    args = parser.parse_args()
    
    # Determine query from preset or argument
    if args.query:
        query = args.query
    elif args.preset:
        query = PRESETS[args.preset]
    else:
        query = PRESETS["fluids"]  # Default
    
    success = await run_chat_test(
        query=query,
        base_url=args.base_url,
        api_key=args.api_key,
        email=args.email,
        password=args.password,
        model=args.model,
        stream=not args.no_stream
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
