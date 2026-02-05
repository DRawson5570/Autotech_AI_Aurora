#!/usr/bin/env python3
"""
Mitchell Explorer Script
========================
Simple script that:
1. Launches Chrome with CDP
2. Navigates to ShopKeyPro
3. Logs in
4. STOPS and waits for you to manually explore

Use this to navigate to the page you need and inspect the DOM.
Press Ctrl+C when done.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    print("=" * 60)
    print("  Mitchell Explorer - Login and Pause")
    print("=" * 60)
    print()
    
    from addons.mitchell_agent.api import MitchellAPI
    
    # Always run headless=False so you can see and interact
    api = MitchellAPI(headless=False)
    
    try:
        print("[1/3] Connecting to ShopKeyPro...")
        connected = await api.connect()
        
        if not connected:
            print("ERROR: Failed to connect!")
            return
        
        page = api._page
        print(f"[2/3] Connected! Current URL: {page.url}")
        
        print("[3/3] Login complete. Browser is now open for exploration.")
        print()
        print("=" * 60)
        print("  BROWSER IS READY FOR MANUAL NAVIGATION")
        print("=" * 60)
        print()
        print("You can now:")
        print("  - Select a vehicle (2018 Ford F-150 5.0L)")
        print("  - Click 'Use This Vehicle' to trigger Options modal")
        print("  - Navigate to DRIVE TYPE options")
        print("  - Use DevTools (F12) to inspect elements")
        print()
        print("When done exploring, press ENTER to disconnect...")
        print()
        
        # Wait for user to press Enter
        input(">>> Press ENTER to disconnect and exit...\n")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    finally:
        print("Disconnecting...")
        await api.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
