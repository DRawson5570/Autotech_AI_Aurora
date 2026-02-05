#!/usr/bin/env python3
"""
Mitchell Debug Script - See what's on the page
==============================================

Takes screenshots and dumps element info to diagnose issues.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    print("=== Mitchell Debug Script ===\n")
    
    from addons.mitchell_agent.api import MitchellAPI
    
    api = MitchellAPI(headless=False)
    
    try:
        print("1. Connecting to ShopKeyPro...")
        connected = await api.connect()
        
        if not connected:
            print("Failed to connect!")
            return
        
        print("2. Connected! Taking screenshot...")
        page = api._page
        
        # Take screenshot
        await page.screenshot(path="/tmp/mitchell_debug_1.png")
        print("   Screenshot saved: /tmp/mitchell_debug_1.png")
        
        # Get current URL
        print(f"3. Current URL: {page.url}")
        
        # Check for vehicle selector button
        print("\n4. Looking for vehicle selector elements...")
        
        selectors_to_check = [
            ("#vehicleSelectorButton", "Vehicle Selector Button"),
            ("#VehicleSelectorContainer", "Vehicle Selector Container"),
            ("#qualifierTypeSelector", "Qualifier Type Selector"),
            ("#qualifierTypeSelector li.year", "Year Tab"),
            ("#qualifierValueSelector", "Qualifier Value Selector"),
            (".modal", "Any Modal"),
            (".modalDialogView", "Modal Dialog View"),
            ("#quickAccessPanel", "Quick Access Panel"),
        ]
        
        for selector, name in selectors_to_check:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    visible = await elem.is_visible()
                    box = await elem.bounding_box()
                    print(f"   ✓ {name}: FOUND (visible={visible}, box={box})")
                else:
                    print(f"   ✗ {name}: NOT FOUND")
            except Exception as e:
                print(f"   ? {name}: ERROR - {e}")
        
        # Try clicking the vehicle selector button
        print("\n5. Clicking vehicle selector button...")
        try:
            await page.click("#vehicleSelectorButton", timeout=5000)
            await asyncio.sleep(2)
            print("   Clicked! Taking another screenshot...")
            await page.screenshot(path="/tmp/mitchell_debug_2.png")
            print("   Screenshot saved: /tmp/mitchell_debug_2.png")
        except Exception as e:
            print(f"   Error clicking: {e}")
        
        # Check again what's visible
        print("\n6. After clicking, checking elements again...")
        for selector, name in selectors_to_check:
            try:
                elem = await page.query_selector(selector)
                if elem:
                    visible = await elem.is_visible()
                    print(f"   {'✓' if visible else '○'} {name}: found (visible={visible})")
                else:
                    print(f"   ✗ {name}: NOT FOUND")
            except Exception as e:
                print(f"   ? {name}: ERROR - {e}")
        
        # Get the HTML of the vehicle selector area
        print("\n7. Getting vehicle selector HTML snippet...")
        try:
            html = await page.evaluate("""
                () => {
                    const container = document.querySelector('#VehicleSelectorContainer') 
                                   || document.querySelector('#vehicleSelectorButton')?.parentElement;
                    if (container) {
                        return container.outerHTML.substring(0, 2000);
                    }
                    return 'Container not found';
                }
            """)
            print(f"   {html[:500]}...")
        except Exception as e:
            print(f"   Error: {e}")
        
        print("\n8. Pausing 30 seconds - look at Chrome window and screenshots...")
        print("   Screenshots at /tmp/mitchell_debug_1.png and /tmp/mitchell_debug_2.png")
        await asyncio.sleep(30)
        
    finally:
        print("\n9. Disconnecting...")
        await api.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
