#!/usr/bin/env python3
"""
Mitchell Tool End-to-End Test
=============================

Tests the full pipeline as if an AI model called the tool:
1. openwebui_tool.py receives the call
2. Tool queues request to server
3. Remote agent picks up request
4. Agent navigates Mitchell and extracts data
5. Result returns through the pipeline

Prerequisites:
- Server running: cd /home/drawson/autotech_ai && python -m backend.main
- Agent running: cd /home/drawson/autotech_ai && ./test.sh

Usage:
    python addons/mitchell_agent/test_tool_e2e.py
    python addons/mitchell_agent/test_tool_e2e.py --tool get_fluid_capacities
    python addons/mitchell_agent/test_tool_e2e.py --vehicle "2020 Toyota Camry 2.5L"
"""

import asyncio
import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Configure logging - show everything
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set specific loggers
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.WARNING)

logger = logging.getLogger("test-tool-e2e")

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


def print_warning(text: str):
    print(f"{YELLOW}⚠ {text}{RESET}")


def print_info(text: str):
    print(f"  {text}")


def parse_vehicle_string(vehicle_str: str) -> dict:
    """
    Parse a vehicle string like "2018 Ford F-150 5.0L XL 2D Pickup 4WD"
    into component parts.
    """
    import re
    
    result = {
        "year": None,
        "make": None,
        "model": None,
        "engine": None,
        "submodel": None,
        "body_style": None,
        "drive_type": None
    }
    
    # Extract year
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', vehicle_str)
    if year_match:
        result["year"] = int(year_match.group(1))
    
    # Common makes
    makes = ["Ford", "Chevrolet", "Chevy", "Toyota", "Honda", "Nissan", "Dodge", "Ram", 
             "Jeep", "GMC", "BMW", "Mercedes", "Audi", "Volkswagen", "VW", "Hyundai", 
             "Kia", "Mazda", "Subaru", "Lexus", "Acura", "Infiniti", "Cadillac", "Buick",
             "Lincoln", "Chrysler", "Porsche", "Volvo", "Tesla", "Mitsubishi"]
    for make in makes:
        if re.search(rf'\b{make}\b', vehicle_str, re.IGNORECASE):
            result["make"] = make
            break
    
    # Drive types
    drive_match = re.search(r'\b(4WD|AWD|RWD|FWD|2WD|4x4)\b', vehicle_str, re.IGNORECASE)
    if drive_match:
        result["drive_type"] = drive_match.group(1).upper()
    
    # Body styles
    body_match = re.search(r'(\d+D\s+(?:Pickup|Sedan|Hatchback|Coupe|SUV|Wagon|Van|Cab))', vehicle_str, re.IGNORECASE)
    if body_match:
        result["body_style"] = body_match.group(1)
    
    # Engine
    engine_match = re.search(r'\b(\d+\.\d+L?)\b', vehicle_str)
    if engine_match:
        engine = engine_match.group(1)
        if not engine.endswith('L'):
            engine += 'L'
        result["engine"] = engine
    
    # Model - word after make
    if result["make"]:
        pattern = rf'\b{result["make"]}\s+(\S+)'
        model_match = re.search(pattern, vehicle_str, re.IGNORECASE)
        if model_match:
            result["model"] = model_match.group(1)
    
    # Submodel - common trim levels
    trims = ["XL", "XLT", "Lariat", "King Ranch", "Platinum", "Limited", "SE", "SEL", 
             "LE", "XLE", "LX", "EX", "Sport", "Touring", "Base", "Premium", "S", "SV"]
    for trim in trims:
        if re.search(rf'\b{trim}\b', vehicle_str, re.IGNORECASE):
            result["submodel"] = trim
            break
    
    return result


async def test_tool_call(
    tool_name: str,
    vehicle: dict,
    params: dict = None,
    shop_id: str = "test_shop",
    timeout: int = 180
) -> dict:
    """
    Call a tool as if the AI model called it.
    
    Returns dict with:
        - success: bool
        - result: str (the tool's response)
        - duration: float (seconds)
        - error: str (if failed)
    """
    from addons.mitchell_agent.openwebui_tool import Tools
    
    print_step(f"Creating Tools instance...")
    tools = Tools()
    
    # Configure valves
    tools.valves.SHOP_ID = shop_id
    tools.valves.API_BASE_URL = "http://localhost:8080"
    tools.valves.REQUEST_TIMEOUT = timeout
    
    print_info(f"Shop ID: {tools.valves.SHOP_ID}")
    print_info(f"API URL: {tools.valves.API_BASE_URL}")
    print_info(f"Timeout: {tools.valves.REQUEST_TIMEOUT}s")
    
    # Build the call arguments
    kwargs = {
        "year": vehicle["year"],
        "make": vehicle["make"],
        "model": vehicle["model"],
        "engine": vehicle.get("engine") or "",
        "submodel": vehicle.get("submodel") or "",
        "body_style": vehicle.get("body_style") or "",
        "drive_type": vehicle.get("drive_type") or "",
        "__user__": {"id": "test_user_123"}
    }
    
    # Add tool-specific params
    if params:
        kwargs.update(params)
    
    print_step(f"Calling tool: {tool_name}")
    print_info(f"Vehicle: {vehicle['year']} {vehicle['make']} {vehicle['model']}")
    if vehicle.get("engine"):
        print_info(f"Engine: {vehicle['engine']}")
    if vehicle.get("submodel"):
        print_info(f"Submodel: {vehicle['submodel']}")
    if vehicle.get("body_style"):
        print_info(f"Body Style: {vehicle['body_style']}")
    if vehicle.get("drive_type"):
        print_info(f"Drive Type: {vehicle['drive_type']}")
    if params:
        print_info(f"Params: {params}")
    
    start_time = time.time()
    
    try:
        # Get the tool method
        method = getattr(tools, tool_name, None)
        if not method:
            return {
                "success": False,
                "result": None,
                "duration": 0,
                "error": f"Unknown tool: {tool_name}"
            }
        
        # Call the tool
        print_step("Waiting for result from agent...")
        result = await method(**kwargs)
        
        duration = time.time() - start_time
        
        return {
            "success": True,
            "result": result,
            "duration": duration,
            "error": None
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.exception(f"Tool call failed: {e}")
        return {
            "success": False,
            "result": None,
            "duration": duration,
            "error": str(e)
        }


async def test_lookup_vehicle(
    vin: str = None,
    plate: str = None,
    state: str = None,
    raw_input: str = None,
    shop_id: str = "test_shop",
    timeout: int = 180
) -> dict:
    """
    Test the lookup_vehicle tool which decodes VIN or plate to vehicle info.
    
    Returns dict with:
        - success: bool
        - result: str (the tool's response)
        - vehicle: dict (parsed vehicle info if successful)
        - duration: float (seconds)
        - error: str (if failed)
    """
    from addons.mitchell_agent.openwebui_tool import Tools
    
    print_step(f"Creating Tools instance for VIN/Plate lookup...")
    tools = Tools()
    
    # Configure valves
    tools.valves.SHOP_ID = shop_id
    tools.valves.API_BASE_URL = "http://localhost:8080"
    tools.valves.REQUEST_TIMEOUT = timeout
    
    print_info(f"Shop ID: {tools.valves.SHOP_ID}")
    print_info(f"API URL: {tools.valves.API_BASE_URL}")
    print_info(f"Timeout: {tools.valves.REQUEST_TIMEOUT}s")
    
    # Build lookup params
    print_step(f"Calling lookup_vehicle")
    if raw_input:
        print_info(f"Raw input: {raw_input}")
    if vin:
        print_info(f"VIN: {vin}")
    if plate:
        print_info(f"Plate: {plate}, State: {state}")
    
    start_time = time.time()
    
    try:
        result = await tools.lookup_vehicle(
            raw_input=raw_input or "",
            vin=vin or "",
            plate=plate or "",
            state=state or "",
            __user__={"id": "test_user_123"}
        )
        
        duration = time.time() - start_time
        
        # Try to parse vehicle info from result
        vehicle = parse_lookup_result(result)
        
        return {
            "success": True,
            "result": result,
            "vehicle": vehicle,
            "duration": duration,
            "error": None
        }
        
    except Exception as e:
        duration = time.time() - start_time
        logger.exception(f"Lookup failed: {e}")
        return {
            "success": False,
            "result": None,
            "vehicle": None,
            "duration": duration,
            "error": str(e)
        }


def parse_lookup_result(result: str) -> dict:
    """
    Parse the lookup_vehicle result to extract vehicle info.
    
    The result is markdown-formatted, we need to extract:
    - year, make, model, engine, vin
    """
    import re
    
    vehicle = {
        "year": None,
        "make": None,
        "model": None,
        "engine": None,
        "vin": None
    }
    
    if not result or "Error" in result:
        return vehicle
    
    # Try to find key-value pairs in the result
    # Pattern: "- key: value" or "**key**: value" or "key: value"
    
    # Year
    year_match = re.search(r'year[:\s]+["\']?(\d{4})["\']?', result, re.IGNORECASE)
    if year_match:
        vehicle["year"] = int(year_match.group(1))
    
    # Make
    make_match = re.search(r'make[:\s]+["\']?([A-Za-z]+)["\']?', result, re.IGNORECASE)
    if make_match:
        vehicle["make"] = make_match.group(1)
    
    # Model
    model_match = re.search(r'model[:\s]+["\']?([A-Za-z0-9\-]+)["\']?', result, re.IGNORECASE)
    if model_match:
        vehicle["model"] = model_match.group(1)
    
    # Engine
    engine_match = re.search(r'engine[:\s]+["\']?([0-9.]+L?)["\']?', result, re.IGNORECASE)
    if engine_match:
        vehicle["engine"] = engine_match.group(1)
    
    # VIN
    vin_match = re.search(r'vin[:\s]+["\']?([A-HJ-NPR-Z0-9]{17})["\']?', result, re.IGNORECASE)
    if vin_match:
        vehicle["vin"] = vin_match.group(1)
    
    return vehicle


async def run_lookup_test(
    vin: str = None,
    plate: str = None,
    state: str = None,
    raw_input: str = None,
    then_tool: str = None,
    then_params: dict = None,
    shop_id: str = "test_shop"
):
    """
    Run VIN/Plate lookup test, optionally chaining to another tool.
    
    Args:
        vin: VIN to lookup
        plate: License plate
        state: State code for plate
        raw_input: Raw OCR text like "aue709 mi"
        then_tool: Tool to call after lookup with decoded vehicle
        then_params: Additional params for the chained tool
        shop_id: Shop ID
    """
    print_header("VIN/Plate Lookup Test")
    
    # Step 1: Lookup vehicle
    result = await test_lookup_vehicle(
        vin=vin,
        plate=plate,
        state=state,
        raw_input=raw_input,
        shop_id=shop_id
    )
    
    print_header("Lookup Result")
    
    if result["success"]:
        print_success(f"Lookup completed in {result['duration']:.1f}s")
        print("\n--- Response ---")
        print(result["result"])
        print("--- End Response ---\n")
        
        if result["vehicle"]:
            print_step("Parsed vehicle info:")
            for k, v in result["vehicle"].items():
                if v:
                    print_info(f"{k}: {v}")
        
        # Step 2: Chain to another tool if requested
        if then_tool and result["vehicle"]:
            vehicle = result["vehicle"]
            
            # Validate we have enough info
            if not vehicle.get("year") or not vehicle.get("make") or not vehicle.get("model"):
                print_warning("Cannot chain to next tool - missing vehicle info from lookup")
                print_info("Need year, make, and model to call other tools")
                return True
            
            print_header(f"Chaining to {then_tool}")
            print_step(f"Using decoded vehicle: {vehicle['year']} {vehicle['make']} {vehicle['model']}")
            
            chain_result = await test_tool_call(
                tool_name=then_tool,
                vehicle=vehicle,
                params=then_params,
                shop_id=shop_id
            )
            
            print_header(f"{then_tool} Result")
            
            if chain_result["success"]:
                print_success(f"Tool completed in {chain_result['duration']:.1f}s")
                print("\n--- Response ---")
                print(chain_result["result"])
                print("--- End Response ---\n")
                return True
            else:
                print_error(f"Chained tool failed: {chain_result['error']}")
                return False
        
        return True
    else:
        print_error(f"Lookup failed after {result['duration']:.1f}s")
        print_error(f"Error: {result['error']}")
        return False


async def test_query_by_plate(
    plate: str,
    state: str,
    request_type: str,
    dtc_code: str = "",
    search_query: str = "",
    system: str = "",
    reset_type: str = "",
    shop_id: str = "test_shop",
    api_url: str = "http://localhost:8080",
    timeout: int = 180
):
    """
    Test query_by_plate which chains plate lookup + info tool.
    
    Args:
        plate: License plate number
        state: 2-letter state code
        request_type: Type of info: fluids, torque, dtc, reset, adas, tire, tsb, wiring, search
        dtc_code: DTC code (required if request_type=dtc)
        search_query: Search query (required if request_type=search)
        system: System for wiring (optional if request_type=wiring)
        reset_type: Reset type (optional if request_type=reset)
    """
    from openwebui_tool import Tools
    
    print_header("Query By Plate Test")
    print_info(f"Plate: {plate}, State: {state}, Request: {request_type}")
    
    print_step("Creating Tools instance...")
    tools = Tools()
    tools.valves.SHOP_ID = shop_id
    tools.valves.API_BASE_URL = api_url
    tools.valves.REQUEST_TIMEOUT = timeout
    print_info(f"Shop ID: {shop_id}")
    print_info(f"API URL: {api_url}")
    print_info(f"Timeout: {timeout}s")
    
    print_step(f"Calling query_by_plate({plate}, {state}, {request_type})")
    
    start = time.time()
    try:
        result = await tools.query_by_plate(
            plate=plate,
            state=state,
            request_type=request_type,
            dtc_code=dtc_code,
            search_query=search_query,
            system=system,
            reset_type=reset_type
        )
        duration = time.time() - start
        
        print_header("Query By Plate Result")
        if "Error" in result:
            print_error(f"Failed after {duration:.1f}s")
            print(result)
            return False
        else:
            print_success(f"Completed in {duration:.1f}s")
            print("\n--- Response ---")
            print(result)
            print("--- End Response ---\n")
            return True
    except Exception as e:
        duration = time.time() - start
        print_error(f"Exception after {duration:.1f}s: {e}")
        return False


async def run_test(
    tool_name: str = "get_fluid_capacities",
    vehicle_str: str = None,
    vehicle_dict: dict = None,
    params: dict = None,
    shop_id: str = "test_shop"
):
    """Run a single tool test."""
    
    print_header(f"Mitchell Tool E2E Test: {tool_name}")
    
    # Parse vehicle
    if vehicle_dict:
        vehicle = vehicle_dict
    elif vehicle_str:
        print_step(f"Parsing vehicle string: {vehicle_str}")
        vehicle = parse_vehicle_string(vehicle_str)
    else:
        # Default test vehicle
        vehicle = {
            "year": 2018,
            "make": "Ford",
            "model": "F-150",
            "engine": "5.0L",
            "submodel": "XL",
            "body_style": "2D Pickup",
            "drive_type": "4WD"
        }
    
    print_info(f"Parsed vehicle: {json.dumps(vehicle, indent=2)}")
    
    # Validate required fields
    if not vehicle.get("year") or not vehicle.get("make") or not vehicle.get("model"):
        print_error("Vehicle must have year, make, and model")
        return False
    
    # Run the test
    result = await test_tool_call(
        tool_name=tool_name,
        vehicle=vehicle,
        params=params,
        shop_id=shop_id
    )
    
    print_header("Result")
    
    if result["success"]:
        print_success(f"Tool completed in {result['duration']:.1f}s")
        print("\n--- Response ---")
        print(result["result"])
        print("--- End Response ---\n")
        
        # Check if it was a clarification request
        if "Additional information needed" in str(result["result"]):
            print_warning("Tool returned a clarification request")
            print_info("The LLM would need to call the tool again with the missing info")
        
        return True
    else:
        print_error(f"Tool failed after {result['duration']:.1f}s")
        print_error(f"Error: {result['error']}")
        return False


async def run_clarification_test(shop_id: str = "test_shop"):
    """
    Test the clarification flow:
    1. Call with incomplete info
    2. Verify clarification is requested
    3. Call again with complete info
    4. Verify success
    """
    print_header("Clarification Flow Test")
    
    # Step 1: Call with incomplete info (no drive_type for F-150)
    print_step("Step 1: Calling with incomplete vehicle info (no drive_type)")
    
    vehicle_incomplete = {
        "year": 2018,
        "make": "Ford",
        "model": "F-150",
        "engine": "5.0L",
        "submodel": "XL",
        "body_style": "2D Pickup",
        # No drive_type - should trigger clarification
    }
    
    result1 = await test_tool_call(
        tool_name="get_fluid_capacities",
        vehicle=vehicle_incomplete,
        shop_id=shop_id
    )
    
    if not result1["success"]:
        print_error(f"First call failed unexpectedly: {result1['error']}")
        return False
    
    # Check if clarification was requested
    response1 = result1["result"]
    if "Additional information needed" in response1 or "Drive Type" in response1:
        print_success("Clarification was correctly requested")
        print_info(f"Response snippet: {response1[:200]}...")
    else:
        print_warning("No clarification requested - vehicle may have been fully specified")
        print_info(f"Response: {response1[:500]}")
    
    # Step 2: Call again with complete info
    print_step("\nStep 2: Calling with complete vehicle info (including drive_type)")
    
    vehicle_complete = {
        "year": 2018,
        "make": "Ford",
        "model": "F-150",
        "engine": "5.0L",
        "submodel": "XL",
        "body_style": "2D Pickup",
        "drive_type": "4WD"  # Now included
    }
    
    result2 = await test_tool_call(
        tool_name="get_fluid_capacities",
        vehicle=vehicle_complete,
        shop_id=shop_id
    )
    
    if result2["success"]:
        response2 = result2["result"]
        if "Additional information needed" not in response2:
            print_success("Second call succeeded without clarification!")
            print("\n--- Fluid Capacities ---")
            print(response2[:1000])
            print("--- End ---\n")
            return True
        else:
            print_warning("Second call still requested clarification")
            print_info(response2[:500])
            return False
    else:
        print_error(f"Second call failed: {result2['error']}")
        return False


async def main():
    parser = argparse.ArgumentParser(
        description="Test Mitchell tool end-to-end",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with default vehicle (2018 Ford F-150 5.0L XL 2D Pickup 4WD)
  python test_tool_e2e.py
  
  # Test specific tool
  python test_tool_e2e.py --tool get_dtc_info --dtc P0300
  
  # Test with different vehicle
  python test_tool_e2e.py --vehicle "2020 Toyota Camry 2.5L LE"
  
  # Test clarification flow
  python test_tool_e2e.py --test-clarification
  
  # VIN/Plate lookup - decode vehicle from plate
  python test_tool_e2e.py --raw-input "aue709 mi"
  
  # VIN/Plate lookup - decode from VIN
  python test_tool_e2e.py --vin "1G1PC5SB8E7123456"
  
  # VIN/Plate lookup - plate with state
  python test_tool_e2e.py --plate AUE709 --state MI
  
  # Lookup then chain to another tool (e.g., get oil capacity for decoded vehicle)
  python test_tool_e2e.py --raw-input "aue709 mi" --then-tool get_fluid_capacities
        """
    )
    
    parser.add_argument(
        "--tool", 
        default="get_fluid_capacities",
        choices=[
            "get_fluid_capacities",
            "get_dtc_info", 
            "get_torque_specs",
            "get_reset_procedure",
            "get_tsb_list",
            "get_adas_calibration",
            "get_tire_specs",
            "get_wiring_diagram",
            "get_specs_procedures",
            "get_component_location",
            "get_component_tests",
            "lookup_vehicle",
            "search_mitchell",
            "query_mitchell"
        ],
        help="Tool to test"
    )
    
    parser.add_argument(
        "--vehicle",
        type=str,
        help="Vehicle string, e.g. '2018 Ford F-150 5.0L XL 2D Pickup 4WD'"
    )
    
    parser.add_argument(
        "--year", type=int, help="Vehicle year"
    )
    parser.add_argument(
        "--make", type=str, help="Vehicle make"
    )
    parser.add_argument(
        "--model", type=str, help="Vehicle model"
    )
    parser.add_argument(
        "--engine", type=str, help="Engine"
    )
    parser.add_argument(
        "--submodel", type=str, help="Submodel/trim"
    )
    parser.add_argument(
        "--body-style", type=str, help="Body style"
    )
    parser.add_argument(
        "--drive-type", type=str, help="Drive type (4WD, RWD, etc.)"
    )
    
    # VIN/Plate lookup params
    parser.add_argument(
        "--vin", type=str, help="17-character VIN for lookup_vehicle"
    )
    parser.add_argument(
        "--plate", type=str, help="License plate number for lookup_vehicle"
    )
    parser.add_argument(
        "--state", type=str, help="2-letter state code for plate lookup (e.g., 'MI', 'OH')"
    )
    parser.add_argument(
        "--raw-input", type=str, help="Raw OCR text for lookup_vehicle (e.g., 'aue709 mi')"
    )
    parser.add_argument(
        "--then-tool", type=str, 
        help="After lookup_vehicle, call this tool with the decoded vehicle (e.g., 'get_fluid_capacities')"
    )
    parser.add_argument(
        "--request-type", type=str,
        help="For query_by_plate: 'fluids', 'torque', 'dtc', 'reset', 'adas', 'tire', 'tsb', 'wiring', 'search'"
    )
    
    # Tool-specific params
    parser.add_argument(
        "--dtc", type=str, help="DTC code for get_dtc_info"
    )
    parser.add_argument(
        "--component", type=str, help="Component for get_torque_specs"
    )
    parser.add_argument(
        "--procedure", type=str, help="Procedure for get_reset_procedure"
    )
    parser.add_argument(
        "--category", type=str, help="Category for get_tsb_list (e.g., 'Charging Systems')"
    )
    parser.add_argument(
        "--query", type=str, help="Search query for search_mitchell"
    )
    parser.add_argument(
        "--question", type=str, help="Question for query_mitchell"
    )
    # Wiring diagram params
    parser.add_argument(
        "--system", type=str, help="Electrical system for get_wiring_diagram (e.g., 'Engine')"
    )
    parser.add_argument(
        "--subsystem", type=str, help="Subsystem for get_wiring_diagram (e.g., 'Starting/Charging')"
    )
    parser.add_argument(
        "--diagram", type=str, help="Specific diagram for get_wiring_diagram (e.g., 'Starter Circuit')"
    )
    parser.add_argument(
        "--search", type=str, help="Search term for get_wiring_diagram or get_specs_procedures"
    )
    # Specs/procedures params
    parser.add_argument(
        "--topic", type=str, help="Topic for get_specs_procedures (e.g., 'DRIVE BELT REPLACEMENT')"
    )
    # ADAS info_type param
    parser.add_argument(
        "--info-type", type=str, help="Info type for get_adas_calibration drill-down (e.g., 'specs', 'remove', 'wiring')"
    )
    
    parser.add_argument(
        "--shop-id",
        default="test_shop",
        help="Shop ID to use (must match running agent)"
    )
    
    parser.add_argument(
        "--test-clarification",
        action="store_true",
        help="Run the clarification flow test"
    )
    
    args = parser.parse_args()
    
    print(f"\n{BOLD}Mitchell Tool E2E Test{RESET}")
    print(f"Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Shop ID: {args.shop_id}")
    
    # Run clarification test if requested
    if args.test_clarification:
        success = await run_clarification_test(shop_id=args.shop_id)
        sys.exit(0 if success else 1)
    
    # Check if this is a VIN/plate lookup test
    raw_input = getattr(args, 'raw_input', None)
    request_type = getattr(args, 'request_type', None)
    
    # Check for query_by_plate (plate + state + request_type)
    if args.plate and args.state and request_type:
        success = await test_query_by_plate(
            plate=args.plate,
            state=args.state,
            request_type=request_type,
            dtc_code=args.dtc or "",
            search_query=args.query or "",
            system=args.system or "",
            reset_type=args.procedure or "",
            shop_id=args.shop_id
        )
        sys.exit(0 if success else 1)
    
    # Check if this is a simple lookup_vehicle test
    if args.tool == "lookup_vehicle" or raw_input or args.vin or args.plate:
        # Build tool params for chained tool
        then_params = {}
        if args.dtc:
            then_params["dtc_code"] = args.dtc
        if args.component:
            then_params["component"] = args.component
        if args.procedure:
            then_params["procedure"] = args.procedure
        if args.category:
            then_params["category"] = args.category
        if args.query:
            then_params["query"] = args.query
        if args.question:
            then_params["question"] = args.question
        if args.system:
            then_params["system"] = args.system
        if args.search:
            then_params["search"] = args.search
        
        success = await run_lookup_test(
            vin=args.vin,
            plate=args.plate,
            state=args.state,
            raw_input=raw_input,
            then_tool=args.then_tool,
            then_params=then_params if then_params else None,
            shop_id=args.shop_id
        )
        sys.exit(0 if success else 1)
    
    # Build vehicle dict
    vehicle = None
    if args.year and args.make and args.model:
        vehicle = {
            "year": args.year,
            "make": args.make,
            "model": args.model,
            "engine": args.engine,
            "submodel": args.submodel,
            "body_style": args.body_style,
            "drive_type": args.drive_type
        }
    
    # Build tool params
    params = {}
    if args.dtc:
        params["dtc_code"] = args.dtc
    if args.component:
        params["component"] = args.component
    if args.procedure:
        params["procedure"] = args.procedure
    if args.category:
        params["category"] = args.category
    if args.query:
        params["query"] = args.query
    if args.question:
        params["question"] = args.question
    # Wiring diagram params
    if args.system:
        params["system"] = args.system
    if args.subsystem:
        params["subsystem"] = args.subsystem
    if args.diagram:
        params["diagram"] = args.diagram
    if args.search:
        params["search"] = args.search
    # Specs/procedures params
    if args.topic:
        params["topic"] = args.topic
    # ADAS info_type
    if hasattr(args, 'info_type') and args.info_type:
        params["info_type"] = args.info_type
    
    # Run the test
    success = await run_test(
        tool_name=args.tool,
        vehicle_str=args.vehicle,
        vehicle_dict=vehicle,
        params=params if params else None,
        shop_id=args.shop_id
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())
