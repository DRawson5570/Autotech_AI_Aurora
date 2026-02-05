#!/usr/bin/env python3
"""
Test AutoDB Navigator with unified index.

Tests the agent's ability to find specific automotive data using egrep on unified index.
"""

import asyncio
import sys
import os

# Add parent to path  
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodb_agent.navigator import AutodbNavigator
from autodb_agent.models import Vehicle

# Test vehicle that's in our unified index (Jeep Truck 1985)
TEST_VEHICLE = Vehicle(
    year="1985",
    make="Jeep Truck",
    model="L4-150 2.5L VIN U 1-bbl",  # Engine is part of path
    engine=""
)


async def test_query(query: str, vehicle: Vehicle, max_steps: int = 10) -> dict:
    """Test a single query and return results."""
    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print(f"VEHICLE: {vehicle.year} {vehicle.make} {vehicle.model}")
    print("="*60)
    
    navigator = AutodbNavigator(
        model="gemini-2.0-flash",
        base_url="http://automotive.aurora-sentient.net/autodb"
    )
    
    try:
        result = await navigator.navigate(
            goal=query,
            vehicle=vehicle,
            max_steps=max_steps
        )
        
        print(f"\nSUCCESS: {result.success}")
        print(f"STEPS: {result.steps_taken}")
        
        if result.success:
            print(f"URL: {result.url}")
            print(f"BREADCRUMB: {result.breadcrumb}")
            if result.images:
                print(f"IMAGES: {len(result.images)}")
            print(f"\nCONTENT ({len(result.content)} chars):")
            print("-" * 40)
            print(result.content[:800] if result.content else "(empty)")
            if result.content and len(result.content) > 800:
                print("...")
        else:
            print(f"ERROR: {result.error}")
        
        if result.path_taken:
            print(f"\nPATH TAKEN:")
            for step in result.path_taken:
                print(f"  {step}")
        
        return {
            "query": query,
            "success": result.success,
            "steps": result.steps_taken,
            "content_length": len(result.content) if result.content else 0,
        }
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return {
            "query": query,
            "success": False,
            "error": str(e)
        }


async def main():
    """Run test queries."""
    # Test queries that should work with our index
    queries = [
        # "where is the fuse box",  # Should find fuse block info
        "relay box location",     # Should find relay info
        # "brake fluid capacity",   # Should find fluid specs
    ]
    
    results = []
    for query in queries:
        result = await test_query(query, TEST_VEHICLE)
        results.append(result)
        print("\n" + "="*60)
        input("Press Enter for next query...")
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    for r in results:
        status = "✓" if r.get("success") else "✗"
        print(f"{status} {r['query']}: {r.get('steps', 'N/A')} steps")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Run specific query from command line
        query = " ".join(sys.argv[1:])
        asyncio.run(test_query(query, TEST_VEHICLE))
    else:
        asyncio.run(main())
