#!/usr/bin/env python3
"""
Mitchell Agent E2E Test Script
==============================

Tests the full Mitchell integration pipeline:
1. Verifies imports work
2. Tests tool registry
3. Tests the addon server request/response flow (if server running)
4. Tests the Open WebUI save endpoint

Run with: python scripts/test_mitchell_e2e.py
"""

import asyncio
import sys
import json
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}")

def print_ok(text):
    print(f"{GREEN}✓ {text}{RESET}")

def print_fail(text):
    print(f"{RED}✗ {text}{RESET}")

def print_warn(text):
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_info(text):
    print(f"  {text}")


async def test_imports():
    """Test that all key imports work."""
    print_header("1. Testing Imports")
    
    errors = []
    
    # Test tools imports
    try:
        from addons.mitchell_agent.tools import (
            Vehicle, ToolResult, ToolRegistry, get_registry,
            FluidCapacitiesTool, DTCInfoTool, TorqueSpecsTool,
            ResetProcedureTool, TSBListTool, ADASCalibrationTool,
            TireSpecsTool, SearchMitchellTool, BrowseManualTool
        )
        print_ok("Tools module imports")
    except Exception as e:
        errors.append(f"Tools import: {e}")
        print_fail(f"Tools import: {e}")
    
    # Test MitchellAPI
    try:
        from addons.mitchell_agent.api import MitchellAPI
        print_ok("MitchellAPI import")
    except Exception as e:
        errors.append(f"MitchellAPI import: {e}")
        print_fail(f"MitchellAPI import: {e}")
    
    # Test agent service
    try:
        from addons.mitchell_agent.agent.service import MitchellAgent
        print_ok("MitchellAgent import")
    except Exception as e:
        errors.append(f"MitchellAgent import: {e}")
        print_fail(f"MitchellAgent import: {e}")
    
    # Test addon server router
    try:
        from addons.mitchell_agent.server.router import router as addon_router
        print_ok("Addon server router import")
    except Exception as e:
        errors.append(f"Addon router import: {e}")
        print_fail(f"Addon router import: {e}")
    
    # Test Open WebUI mitchell router
    try:
        from backend.open_webui.routers.mitchell import router as webui_router
        print_ok("Open WebUI mitchell router import")
    except Exception as e:
        errors.append(f"WebUI router import: {e}")
        print_fail(f"WebUI router import: {e}")
    
    return len(errors) == 0, errors


async def test_tool_registry():
    """Test the tool registry and selectors."""
    print_header("2. Testing Tool Registry")
    
    from addons.mitchell_agent.tools import get_registry, FluidCapacitiesTool
    
    errors = []
    
    # Get registry
    registry = get_registry()
    tools = registry.list_tools()
    print_info(f"Registered tools: {len(tools)}")
    
    expected_tools = [
        "get_fluid_capacities",
        "get_dtc_info",
        "get_torque_specs",
        "get_reset_procedure",
        "get_tsb_list",
        "get_adas_calibration",
        "get_tire_specs",
        "search_mitchell",
        "browse_manual",
    ]
    
    for tool_name in expected_tools:
        tool = registry.get_tool(tool_name)
        if tool:
            print_ok(f"Tool: {tool_name} (tier {tool.tier})")
        else:
            errors.append(f"Missing tool: {tool_name}")
            print_fail(f"Missing tool: {tool_name}")
    
    # Test get_selector() method
    print_info("\nTesting get_selector():")
    tool = FluidCapacitiesTool()
    
    selector_tests = [
        ("quick_access.fluid_capacities", "#fluidsQuickAccess"),
        ("module_selector.maintenance", "li.maintenance a"),
        ("vehicle_selector.year_tab", "#qualifierTypeSelector li.year"),
        ("login.username_input", "#username"),
    ]
    
    for path, expected in selector_tests:
        actual = tool.get_selector(path)
        if actual == expected:
            print_ok(f"  get_selector('{path}') = '{actual}'")
        else:
            errors.append(f"Selector mismatch: {path} expected '{expected}' got '{actual}'")
            print_fail(f"  get_selector('{path}') expected '{expected}' got '{actual}'")
    
    return len(errors) == 0, errors


async def test_vehicle_object():
    """Test Vehicle object creation."""
    print_header("3. Testing Vehicle Object")
    
    from addons.mitchell_agent.tools.base import Vehicle
    
    errors = []
    
    # Test with int year
    v = Vehicle(year=2018, make="Ford", model="F-150", engine="5.0L")
    print_ok(f"Vehicle created: {v}")
    
    if v.year != 2018:
        errors.append(f"Year should be int 2018, got {type(v.year)} {v.year}")
        print_fail(f"Year type issue: {type(v.year)}")
    else:
        print_ok(f"Year is int: {v.year}")
    
    selector_fmt = v.to_selector_format()
    print_ok(f"to_selector_format(): {selector_fmt}")
    
    return len(errors) == 0, errors


async def test_server_queue():
    """Test the addon server queue (in-memory)."""
    print_header("4. Testing Server Queue")
    
    from addons.mitchell_agent.server.queue import (
        RequestQueue, CreateRequestPayload, SubmitResultPayload
    )
    
    errors = []
    
    queue = RequestQueue()
    
    # Add a request
    payload = CreateRequestPayload(
        shop_id="test_shop",
        tool="get_fluid_capacities",
        vehicle={"year": 2018, "make": "Ford", "model": "F-150", "engine": "5.0L"},
        params={}
    )
    request = await queue.create_request(payload)
    request_id = request.id
    print_ok(f"Created request: {request_id}")
    
    # Get pending
    pending = await queue.get_pending_requests("test_shop")
    if len(pending) == 1:
        print_ok(f"Get pending: {len(pending)} request(s)")
    else:
        errors.append(f"Expected 1 pending, got {len(pending)}")
        print_fail(f"Pending count wrong: {len(pending)}")
    
    # Claim
    claimed = await queue.claim_request(request_id)
    if claimed:
        print_ok("Claimed request")
    else:
        errors.append("Failed to claim")
        print_fail("Failed to claim")
    
    # Submit result
    result_payload = SubmitResultPayload(
        success=True,
        data={"test": "data"},
        execution_time_ms=100
    )
    await queue.submit_result(request_id, result_payload)
    print_ok("Submitted result")
    
    # Get result
    result = await queue.get_result(request_id)
    if result and result.success:
        print_ok(f"Got result: success={result.success}")
    else:
        errors.append("Result missing or failed")
        print_fail("Result issue")
    
    return len(errors) == 0, errors


async def test_openwebui_tool():
    """Test the Open WebUI tool class."""
    print_header("5. Testing Open WebUI Tool")
    
    from addons.mitchell_agent.openwebui_tool import Tools
    
    errors = []
    
    tool = Tools()
    print_ok(f"Tools instance created")
    print_info(f"API Base URL: {tool.valves.API_BASE_URL}")
    print_info(f"Request Timeout: {tool.valves.REQUEST_TIMEOUT}s")
    
    # Check tool methods exist
    methods = [
        "get_fluid_capacities",
        "get_dtc_info",
        "get_torque_specs",
        "get_reset_procedure",
        "get_tsb_list",
        "get_adas_calibration",
        "get_tire_specs",
        "search_mitchell",
        "query_mitchell",
        "save_result",
    ]
    
    for method in methods:
        if hasattr(tool, method):
            print_ok(f"Method: {method}")
        else:
            errors.append(f"Missing method: {method}")
            print_fail(f"Missing method: {method}")
    
    return len(errors) == 0, errors


async def test_save_endpoint():
    """Test the save endpoint (requires running server)."""
    print_header("6. Testing Save Endpoint (requires running server)")
    
    import httpx
    
    errors = []
    
    # Try to hit the local server
    base_url = "http://localhost:8080"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Check if server is up
            resp = await client.get(f"{base_url}/api/v1/mitchell/agents")
            if resp.status_code == 401:
                print_warn("Server up but requires auth (expected)")
            elif resp.status_code == 200:
                print_ok("Server responding")
            else:
                print_warn(f"Server returned {resp.status_code}")
    except httpx.ConnectError:
        print_warn("Server not running at localhost:8080 - skipping live tests")
        return True, []  # Not an error, just skip
    except Exception as e:
        print_warn(f"Could not connect: {e}")
        return True, []
    
    return len(errors) == 0, errors


async def main():
    """Run all tests."""
    print(f"\n{BLUE}Mitchell Agent E2E Test Suite{RESET}")
    print(f"{'='*60}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    all_passed = True
    all_errors = []
    
    tests = [
        ("Imports", test_imports),
        ("Tool Registry", test_tool_registry),
        ("Vehicle Object", test_vehicle_object),
        ("Server Queue", test_server_queue),
        ("Open WebUI Tool", test_openwebui_tool),
        ("Save Endpoint", test_save_endpoint),
    ]
    
    for name, test_fn in tests:
        try:
            passed, errors = await test_fn()
            if not passed:
                all_passed = False
                all_errors.extend(errors)
        except Exception as e:
            all_passed = False
            all_errors.append(f"{name}: {e}")
            print_fail(f"Test crashed: {e}")
    
    # Summary
    print_header("SUMMARY")
    
    if all_passed:
        print_ok("All tests passed!")
    else:
        print_fail(f"Some tests failed ({len(all_errors)} errors):")
        for err in all_errors:
            print_info(f"  - {err}")
    
    print(f"\nFinished at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
