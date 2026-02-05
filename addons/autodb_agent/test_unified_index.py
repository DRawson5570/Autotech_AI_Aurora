#!/usr/bin/env python3
"""Test unified index search functionality."""

import asyncio
import logging
from pathlib import Path

from .models import Vehicle
from .page_parser import PageParser
from .tools import Tools

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

async def test_egrep_unified():
    """Test egrep with unified index."""
    
    # Create a vehicle (1985 Jeep Truck which we indexed)
    vehicle = Vehicle(
        year="1985",
        make="Jeep Truck",
        model="L4-150 2.5L VIN U 1-bbl",  # Engine acts as model
        engine=""
    )
    
    # Create tools
    parser = PageParser()
    tools = Tools(parser, vehicle)
    
    print(f"\n=== Testing egrep with unified index ===")
    print(f"Vehicle: {vehicle.year} {vehicle.make} {vehicle.model}")
    print(f"Index path: {tools._get_index_path()}")
    print(f"Using unified index: {tools._unified_index}")
    
    # Test 1: Search for fuse
    print("\n--- Test 1: Search 'fuse' ---")
    result = tools.egrep("fuse")
    print(f"Success: {result.success}")
    print(f"Hint: {result.hint}")
    if result.extracted_content:
        print(f"Results:\n{result.extracted_content[:500]}...")
    
    # Test 2: Search for relay
    print("\n--- Test 2: Search 'relay' ---")
    result = tools.egrep("relay")
    print(f"Success: {result.success}")
    print(f"Hint: {result.hint}")
    if result.extracted_content:
        # Just show first few lines
        lines = result.extracted_content.split('\n')[:10]
        print("Results (first 10 lines):")
        for line in lines:
            print(f"  {line}")
    
    # Test 3: Search for oil
    print("\n--- Test 3: Search 'oil.*capacity|capacity.*oil' ---")
    result = tools.egrep("oil.*capacity|capacity.*oil")
    print(f"Success: {result.success}")
    print(f"Hint: {result.hint}")
    if result.extracted_content:
        print(f"Results:\n{result.extracted_content[:500]}...")

if __name__ == "__main__":
    asyncio.run(test_egrep_unified())
