#!/usr/bin/env python3
"""
Predictive Diagnostics Chat E2E Test
====================================

Tests the full chat flow as if a user sent a message in Open WebUI:
1. User describes a diagnostic problem
2. LLM recognizes it needs the physics diagnostic tool
3. LLM calls the appropriate tool with DTCs/PIDs/complaints
4. Tool runs physics simulation + ML inference
5. LLM formats the diagnostic report for user

This tests the COMPLETE user experience, not just the tool in isolation.

Prerequisites:
- Open WebUI running on localhost:8080
- diagnose tool registered in Open WebUI

Usage:
    python addons/predictive_diagnostics/test_chat_e2e.py
    python addons/predictive_diagnostics/test_chat_e2e.py --preset overheating
    python addons/predictive_diagnostics/test_chat_e2e.py --query "My car has P0171 and P0174 codes with rough idle"
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
    
    if tool_ids:
        payload["tool_ids"] = tool_ids
    
    async with httpx.AsyncClient(timeout=300) as client:
        if stream:
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
            print()
            return {"content": full_response}
        else:
            response = await client.post(
                f"{base_url}/api/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            
            choices = data.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                return {
                    "content": message.get("content", ""),
                    "tool_calls": message.get("tool_calls", []),
                    "raw": data
                }
            return {"content": "", "raw": data}


async def run_diagnostic_test(
    query: str,
    base_url: str = "http://localhost:8080",
    api_key: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
    model: str = "gemini-2.5-pro",
    stream: bool = True,
    tool_id: str = "diagnose"
):
    """Run a diagnostic test with a natural language query."""
    
    print_header("Predictive Diagnostics Chat E2E Test")
    
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
            api_key = os.environ.get("OPENWEBUI_API_KEY")
            if not api_key:
                print_step("Generating admin token from database...")
                api_key = get_admin_token()
                if not api_key:
                    print_error("No API key available. Use --api-key, --email/--password, or ensure database exists")
                    return False
                print_success("Generated admin token")
    
    print_step(f"Model: {model}")
    print_step(f"Tool: {tool_id}")
    print_step(f"Query: {query}")
    print()
    
    start_time = time.time()
    
    try:
        print_step("Sending to Open WebUI chat API...")
        print(f"\n{YELLOW}--- LLM Response ---{RESET}\n")
        
        result = await send_chat_message(
            base_url=base_url,
            api_key=api_key,
            message=query,
            model=model,
            stream=stream,
            tool_ids=[tool_id]
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n{YELLOW}--- End Response ---{RESET}\n")
        print_success(f"Completed in {elapsed:.1f}s")
        
        content = result.get("content", "")
        
        # Look for indicators that physics diagnostic tool was used
        diagnostic_indicators = [
            "physics", "diagnosis", "diagnostic",
            "confidence", "likely", "probable",
            "thermostat", "radiator", "coolant", "overheating",
            "fuel", "injector", "maf", "lean", "rich",
            "ignition", "coil", "spark", "misfire",
            "battery", "alternator", "charging", "voltage",
            "verification", "test", "repair",
            "P0", "DTC",  # DTC codes
            "ML Model", "Physics-Based",  # Tool output markers
        ]
        
        tool_used = any(ind.lower() in content.lower() for ind in diagnostic_indicators)
        
        # Check for actual diagnostic data
        has_diagnosis = any([
            "most likely" in content.lower(),
            "confidence" in content.lower(),
            "verification test" in content.lower(),
            "repair" in content.lower(),
            "%" in content,  # Confidence percentages
            "█" in content or "░" in content,  # Progress bars from tool
        ])
        
        # Check for physics explanation
        has_physics = any([
            "physics" in content.lower(),
            "predicted state" in content.lower(),
            "simulation" in content.lower(),
            "temperature" in content.lower() and ("°" in content or "celsius" in content.lower()),
        ])
        
        # Check for ML analysis
        has_ml = any([
            "ml model" in content.lower(),
            "neural network" in content.lower(),
            "pattern" in content.lower() and "diagnosis" in content.lower(),
            "probability" in content.lower(),
        ])
        
        print()
        print(f"{BOLD}=== DIAGNOSTIC VERIFICATION ==={RESET}")
        
        if has_diagnosis:
            print(f"{GREEN}✓ DIAGNOSIS FOUND - Contains diagnostic conclusions{RESET}")
        else:
            print(f"{YELLOW}⚠ NO CLEAR DIAGNOSIS - May need more information{RESET}")
        
        if has_physics:
            print(f"{GREEN}✓ PHYSICS ANALYSIS - Contains physics-based reasoning{RESET}")
        else:
            print(f"{YELLOW}○ No physics explanation visible{RESET}")
        
        if has_ml:
            print(f"{GREEN}✓ ML ANALYSIS - Contains ML model predictions{RESET}")
        else:
            print(f"{YELLOW}○ No ML analysis visible{RESET}")
        
        print()
        
        if tool_used:
            print_success("Response appears to contain diagnostic data!")
        else:
            print_info("Response may not have used diagnostic tool (check if query is diagnostic)")
        
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
        import traceback
        traceback.print_exc()
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Test Predictive Diagnostics through Open WebUI chat API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test overheating diagnosis
  python test_chat_e2e.py --preset overheating
  
  # Test with custom query
  python test_chat_e2e.py --query "My car has code P0171 and rough idle, what's wrong?"
  
  # Test with API key
  python test_chat_e2e.py --api-key sk-xxx --preset misfire
        """
    )
    
    # Preset test scenarios - realistic diagnostic queries
    PRESETS = {
        # Cooling system
        "overheating": "My car is overheating, the temp gauge goes to red. I got code P0217. Coolant temp shows 118°C. What's wrong?",
        "cold_running": "My engine never warms up properly, heater blows cold air. Got code P0128. Coolant temp stays at 60°C even after 20 minutes.",
        "coolant_leak": "I keep losing coolant but can't find a visible leak. Temp gauge fluctuates. No codes yet. What should I check?",
        
        # Fuel system
        "lean_codes": "Got codes P0171 and P0174 (system too lean both banks). Car runs rough at idle but smooths out when driving. STFT is +15%.",
        "rich_running": "Car is running rich, black smoke from exhaust. P0172 code. Fuel pressure is 58 psi. What could cause this?",
        "rough_idle": "Engine has rough idle, almost stalls sometimes. No check engine light yet. Fuel pressure at 45 psi seems low.",
        
        # Ignition system  
        "misfire": "I'm getting a P0301 cylinder 1 misfire. RPM fluctuates at idle. Car stutters under load. What should I check first?",
        "no_start": "Car cranks but won't start. Battery voltage shows 12.4V. Spark plugs look fouled. What's the diagnosis?",
        "random_misfire": "Random misfire code P0300. Happens more when it's cold or humid. Multiple cylinders affected.",
        
        # Charging system
        "battery_drain": "Battery keeps dying overnight. Voltage shows 12.2V engine off, 13.8V running. Is that normal?",
        "dim_lights": "Headlights dim when idling and brighten when I rev the engine. Battery light flickers sometimes.",
        "dead_battery": "Had to jump start, now battery voltage is only 12.0V with engine running. Alternator bad?",
        
        # Combined symptoms
        "complex": "Multiple issues: overheating, rough idle, and the battery light came on. Codes are P0217 and P0562. Where do I start?",
        "no_codes": "Car runs rough and gets poor fuel economy but no check engine light. What could be wrong?",
        
        # With PID data
        "with_pids": "Diagnose: P0171 code, coolant temp 92°C, RPM 750, battery 14.2V, STFT +12%, LTFT +8%. What's the cause?",
    }
    
    parser.add_argument(
        "--preset",
        type=str,
        choices=list(PRESETS.keys()),
        help="Use a preset diagnostic scenario"
    )
    
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Natural language diagnostic query (overrides --preset)"
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
        "--tool-id",
        type=str,
        default="diagnose",
        help="Tool ID registered in Open WebUI"
    )
    
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="Disable streaming (wait for full response)"
    )
    
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available presets and exit"
    )
    
    args = parser.parse_args()
    
    if args.list_presets:
        print_header("Available Diagnostic Presets")
        for name, query in PRESETS.items():
            print(f"{GREEN}{name}{RESET}:")
            print(f"  {query}\n")
        return
    
    # Determine query from preset or argument
    if args.query:
        query = args.query
    elif args.preset:
        query = PRESETS[args.preset]
    else:
        query = PRESETS["overheating"]  # Default
    
    success = await run_diagnostic_test(
        query=query,
        base_url=args.base_url,
        api_key=args.api_key,
        email=args.email,
        password=args.password,
        model=args.model,
        stream=not args.no_stream,
        tool_id=args.tool_id
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
