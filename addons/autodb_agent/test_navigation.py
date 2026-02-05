#!/usr/bin/env python3
"""
Test AutoDB Navigator with various data point queries.

Tests the agent's ability to find specific automotive data.
"""

import asyncio
import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autodb_agent.navigator import AutodbNavigator
from autodb_agent.models import Vehicle

# Test vehicle
TEST_VEHICLE = Vehicle(
    year="1997",
    make="Jeep Truck",
    model="Cherokee 4WD",
    engine="L6-4.0L VIN S"
)

# Test queries - different types of data
TEST_QUERIES = [
    "engine oil capacity",
    "spark plug gap",
    "firing order",
    "coolant capacity",
    "lug nut torque",
    "automatic transmission fluid capacity",
    "brake fluid type",
    "timing belt specifications",
    "valve clearance",
    "fuel pump pressure",
]


async def test_single_query(query: str, vehicle: Vehicle) -> dict:
    """Test a single query and return results."""
    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print(f"VEHICLE: {vehicle.year} {vehicle.make} {vehicle.model} {vehicle.engine}")
    print("="*60)
    
    navigator = AutodbNavigator(
        model="gemini-2.0-flash",
        base_url="http://automotive.aurora-sentient.net/autodb"
    )
    
    try:
        result = await navigator.navigate(
            goal=query,
            vehicle=vehicle,
            max_steps=10
        )
        
        print(f"\nSUCCESS: {result.success}")
        print(f"STEPS: {result.steps_taken}")
        
        if result.success:
            print(f"URL: {result.url}")
            print(f"BREADCRUMB: {result.breadcrumb}")
            if result.images:
                print(f"IMAGES: {len(result.images)}")
                for img in result.images:
                    print(f"  - {img[:80]}...")
            print(f"\nCONTENT ({len(result.content)} chars):")
            print("-" * 40)
            print(result.content[:500])
            if len(result.content) > 500:
                print("...")
        else:
            print(f"ERROR: {result.error}")
        
        if result.path_taken:
            print(f"\nPATH TAKEN:")
            for step in result.path_taken:
                print(f"  {step.action} {step.result_hint}")
        
        return {
            "query": query,
            "success": result.success,
            "steps": result.steps_taken,
            "content_length": len(result.content) if result.content else 0,
            "images": len(result.images) if result.images else 0,
            "error": result.error if not result.success else None
        }
        
    except Exception as e:
        print(f"EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return {
            "query": query,
            "success": False,
            "steps": 0,
            "content_length": 0,
            "images": 0,
            "error": str(e)
        }


async def main():
    """Run all test queries."""
    # Check if specific query provided
    if len(sys.argv) > 1:
        queries = [" ".join(sys.argv[1:])]
    else:
        queries = TEST_QUERIES  # Run all queries
    
    print(f"\nTesting {len(queries)} queries...")
    
    results = []
    for query in queries:
        result = await test_single_query(query, TEST_VEHICLE)
        results.append(result)
        
        # Small delay between queries
        if query != queries[-1]:
            await asyncio.sleep(2)
    
    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"Success: {success_count}/{len(results)}")
    
    for r in results:
        status = "✓" if r["success"] else "✗"
        print(f"  {status} {r['query']}: {r['steps']} steps, {r['content_length']} chars, {r['images']} images")
        if r["error"]:
            print(f"      Error: {r['error'][:60]}")


if __name__ == "__main__":
    asyncio.run(main())
