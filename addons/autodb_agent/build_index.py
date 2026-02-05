#!/usr/bin/env python3
"""
Build site index for a vehicle.

Usage:
    python -m addons.autodb_agent.build_index 2012 Jeep Liberty
    python -m addons.autodb_agent.build_index --all-common  # Build common test vehicles
"""

import argparse
import asyncio
import logging
import sys

from .site_index import SiteIndexer
from .config import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
log = logging.getLogger("build_index")

# Common test vehicles to pre-index
COMMON_VEHICLES = [
    {"year": 2012, "make": "Jeep", "model": "Liberty"},
    {"year": 2015, "make": "Chevrolet", "model": "Silverado 1500"},
    {"year": 2018, "make": "Ford", "model": "F-150"},
    {"year": 2020, "make": "Toyota", "model": "Camry"},
    {"year": 2019, "make": "Honda", "model": "Civic"},
]


async def build_vehicle_index(year: int, make: str, model: str) -> str:
    """Build index for a single vehicle."""
    log.info(f"Building index for {year} {make} {model}...")
    
    indexer = SiteIndexer(config.base_url)
    try:
        index_path = await indexer.build_index(year, make, model)
        if index_path:
            log.info(f"✓ Index built: {index_path}")
            return index_path
        else:
            log.error(f"✗ Failed to build index for {year} {make} {model}")
            return None
    finally:
        await indexer.close()


async def build_all_common():
    """Build indexes for all common test vehicles."""
    log.info(f"Building indexes for {len(COMMON_VEHICLES)} common vehicles...")
    
    results = []
    for vehicle in COMMON_VEHICLES:
        path = await build_vehicle_index(
            vehicle["year"],
            vehicle["make"],
            vehicle["model"],
        )
        results.append((vehicle, path))
    
    # Summary
    log.info("\n=== SUMMARY ===")
    success = sum(1 for _, p in results if p)
    log.info(f"Built {success}/{len(results)} indexes")
    for vehicle, path in results:
        status = "✓" if path else "✗"
        log.info(f"  {status} {vehicle['year']} {vehicle['make']} {vehicle['model']}")


def main():
    parser = argparse.ArgumentParser(description="Build site index for vehicles")
    parser.add_argument("year", nargs="?", type=int, help="Vehicle year")
    parser.add_argument("make", nargs="?", help="Vehicle make")
    parser.add_argument("model", nargs="?", help="Vehicle model")
    parser.add_argument("--all-common", action="store_true", help="Build all common test vehicles")
    
    args = parser.parse_args()
    
    if args.all_common:
        asyncio.run(build_all_common())
    elif args.year and args.make and args.model:
        asyncio.run(build_vehicle_index(args.year, args.make, args.model))
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
