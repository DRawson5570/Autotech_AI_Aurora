#!/usr/bin/env python3
"""
Mitchell CDP Server
===================
Launches Chrome with CDP, logs in, then keeps running so CDP commands can be sent.
The browser stays open on port 9222 for external control.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def main():
    print("=" * 60)
    print("  Mitchell CDP Server - Login and Keep Open")
    print("=" * 60)
    
    from addons.mitchell_agent.api import MitchellAPI
    
    api = MitchellAPI(headless=False)
    
    print("[1/3] Connecting to ShopKeyPro...")
    connected = await api.connect()
    
    if not connected:
        print("ERROR: Failed to connect!")
        return
    
    page = api._page
    cdp_port = api._cdp_port
    
    print(f"[2/3] Connected! URL: {page.url}")
    print(f"[3/3] CDP Port: {cdp_port}")
    print()
    print("=" * 60)
    print(f"  BROWSER READY - CDP available on port {cdp_port}")
    print("=" * 60)
    print()
    print("Browser is logged in and waiting for CDP commands.")
    print("To stop: Press Ctrl+C")
    print()
    
    # Keep alive - wait forever until interrupted
    try:
        while True:
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        print("\nShutting down...")
    finally:
        await api.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
