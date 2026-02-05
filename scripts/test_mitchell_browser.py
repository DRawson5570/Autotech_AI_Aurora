#!/usr/bin/env python3
"""
Mitchell Browser Test - Actually launches Chrome and executes tools
===================================================================

This script:
1. Launches Chrome with CDP (visible, not headless)
2. Connects via Playwright
3. Logs into ShopKeyPro
4. Executes MULTIPLE tool calls to test full pipeline
5. Returns the results

Run with: python scripts/test_mitchell_browser.py
"""

import asyncio
import sys
import json
import random
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def print_step(text):
    print(f"{CYAN}>>> {text}{RESET}")

def print_ok(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_fail(text):
    print(f"{RED}✗ {text}{RESET}")

def print_data(data, max_items=5):
    """Pretty print JSON data (limited items for readability)."""
    if isinstance(data, list) and len(data) > max_items:
        print(f"  [{len(data)} total items, showing first {max_items}]")
        print(json.dumps(data[:max_items], indent=2, default=str))
        print(f"  ... and {len(data) - max_items} more items")
    elif isinstance(data, dict) or isinstance(data, list):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)


async def run_tool_test(api, tool_name: str, vehicle: dict, **kwargs) -> dict:
    """Run a single tool test with delays between operations."""
    
    # Random delay before starting (1.5-3 seconds)
    delay = random.uniform(1.5, 3.0)
    print_step(f"Waiting {delay:.1f}s before {tool_name}...")
    await asyncio.sleep(delay)
    
    print_step(f"Executing {tool_name}...")
    
    if tool_name == "get_fluid_capacities":
        result = await api.get_fluid_capacities(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"]
        )
    elif tool_name == "get_torque_specs":
        result = await api.get_torque_specs(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"],
            component=kwargs.get("component", "")
        )
    elif tool_name == "get_reset_procedure":
        result = await api.get_reset_procedure(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"],
            procedure=kwargs.get("procedure", "oil")
        )
    elif tool_name == "get_dtc_info":
        result = await api.get_dtc_info(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"],
            dtc_code=kwargs.get("dtc_code", "P0300")
        )
    elif tool_name == "get_tsb_list":
        result = await api.get_tsb_list(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"],
            category=kwargs.get("category", "")
        )
    elif tool_name == "get_adas_calibration":
        result = await api.get_adas_calibration(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"],
            component=kwargs.get("component", "")
        )
    elif tool_name == "get_tire_specs":
        result = await api.get_tire_specs(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"]
        )
    elif tool_name == "search":
        result = await api.search(
            year=vehicle["year"],
            make=vehicle["make"],
            model=vehicle["model"],
            engine=vehicle["engine"],
            query=kwargs.get("query", "oil change")
        )
    else:
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    return result


async def main():
    """Run multi-tool browser test."""
    print_header("Mitchell Browser Test - ALL TOOLS Test")
    
    # Test vehicle - 2018 Ford F-150 5.0L
    test_vehicle = {
        "year": 2018,
        "make": "Ford",
        "model": "F-150",
        "engine": "5.0L"
    }
    
    # ALL tools to test
    tools_to_test = [
        {"name": "get_fluid_capacities", "kwargs": {}},
        {"name": "get_torque_specs", "kwargs": {"component": ""}},
        {"name": "get_reset_procedure", "kwargs": {"procedure": "oil"}},
        {"name": "get_dtc_info", "kwargs": {"dtc_code": "P0300"}},
        {"name": "get_tsb_list", "kwargs": {}},
        {"name": "get_adas_calibration", "kwargs": {}},
        {"name": "get_tire_specs", "kwargs": {}},
        {"name": "search", "kwargs": {"query": "oil change procedure"}},
    ]
    
    print(f"\n{YELLOW}Test Vehicle:{RESET} {test_vehicle['year']} {test_vehicle['make']} {test_vehicle['model']} {test_vehicle['engine']}")
    print(f"{YELLOW}Tools to test:{RESET} {len(tools_to_test)} tools")
    for i, t in enumerate(tools_to_test, 1):
        print(f"  {i}. {t['name']}")
    print(f"\n{YELLOW}NOTE: Chrome will open - watch it work!{RESET}\n")
    
    # Import and create API
    print_step("Importing MitchellAPI...")
    from addons.mitchell_agent.api import MitchellAPI
    
    # Create API instance with headless=False so we can watch
    print_step("Creating MitchellAPI (headless=False)...")
    api = MitchellAPI(headless=False)
    
    results = []
    
    try:
        # Connect (launches Chrome, logs in)
        print_step("Connecting to ShopKeyPro (watch Chrome!)...")
        connected = await api.connect()
        
        if not connected:
            print_fail("Failed to connect to ShopKeyPro")
            return 1
        
        print_ok("Connected to ShopKeyPro!")
        
        # Give user a moment to see the logged-in state
        print_step("Pausing 3 seconds so you can see the login state...")
        await asyncio.sleep(3)
        
        # Execute each tool
        for i, tool_info in enumerate(tools_to_test, 1):
            tool_name = tool_info["name"]
            kwargs = tool_info["kwargs"]
            
            print_header(f"TEST {i}/{len(tools_to_test)}: {tool_name}")
            
            result = await run_tool_test(api, tool_name, test_vehicle, **kwargs)
            results.append({"tool": tool_name, "result": result})
            
            # Show result summary
            if result.get("success"):
                data = result.get("data", [])
                item_count = len(data) if isinstance(data, list) else 1
                print_ok(f"{tool_name} succeeded: {item_count} items returned")
                print_data(data)
            elif result.get("needs_more_info"):
                # Required options needed
                print(f"{YELLOW}⚠ {tool_name} needs more information:{RESET}")
                required_opts = result.get("required_options", {})
                for opt_name, opt_values in required_opts.items():
                    print(f"   {opt_name}: {opt_values}")
                print(f"\n{YELLOW}To fix: Add 'options' to vehicle, e.g.:{RESET}")
                print(f'   vehicle.options = {{"drive_type": "4WD"}}')
            else:
                print_fail(f"{tool_name} failed: {result.get('error')}")
            
            # Random delay between tools (2-4 seconds)
            if i < len(tools_to_test):
                delay = random.uniform(2.0, 4.0)
                print_step(f"Waiting {delay:.1f}s before next tool...")
                await asyncio.sleep(delay)
        
        # Summary
        print_header("TEST SUMMARY")
        passed = sum(1 for r in results if r["result"].get("success"))
        failed = len(results) - passed
        
        print(f"\n{YELLOW}Results:{RESET}")
        for r in results:
            tool = r["tool"]
            success = r["result"].get("success")
            if success:
                data = r["result"].get("data", [])
                item_count = len(data) if isinstance(data, list) else 1
                print_ok(f"{tool}: {item_count} items")
            else:
                print_fail(f"{tool}: {r['result'].get('error')}")
        
        print(f"\n{GREEN if failed == 0 else YELLOW}Passed: {passed}/{len(results)}{RESET}")
        if failed > 0:
            print(f"{RED}Failed: {failed}/{len(results)}{RESET}")
        
        # Pause so user can see the result in browser
        print_step("Pausing 5 seconds before logout...")
        await asyncio.sleep(5)
        
    except Exception as e:
        print_fail(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Disconnect (logs out, closes browser)
        print_step("Disconnecting (logging out)...")
        await api.disconnect()
        print_ok("Disconnected")
    
    print_header("TEST COMPLETE")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
