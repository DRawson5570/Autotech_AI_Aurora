#!/usr/bin/env python3
"""
Capture Options Panel Selectors
================================
Launches Chrome, logs in, selects a vehicle to trigger the Options modal,
then captures the exact DOM structure of the drive type options.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    print("=== Capture Options Panel Selectors ===\n")
    
    from addons.mitchell_agent.api import MitchellAPI
    
    api = MitchellAPI(headless=False)
    
    try:
        print("1. Connecting to ShopKeyPro...")
        connected = await api.connect()
        
        if not connected:
            print("Failed to connect!")
            return
        
        page = api._page
        print(f"   Connected! URL: {page.url}")
        
        # Select a vehicle that requires DRIVE TYPE
        print("\n2. Selecting 2018 Ford F-150 5.0L (triggers Options modal)...")
        
        # Click vehicle selector button
        await page.click("#vehicleSelectorButton", timeout=5000)
        await asyncio.sleep(1.5)
        
        # Year
        await page.click("#qualifierTypeSelector li.year", timeout=5000)
        await asyncio.sleep(0.5)
        await page.click("#qualifierValueSelector li.qualifier:has-text('2018')", timeout=5000)
        await asyncio.sleep(0.5)
        
        # Make
        await page.click("#qualifierTypeSelector li.make", timeout=5000)
        await asyncio.sleep(0.5)
        await page.click("#qualifierValueSelector li.qualifier:has-text('Ford')", timeout=5000)
        await asyncio.sleep(0.5)
        
        # Model
        await page.click("#qualifierTypeSelector li.model", timeout=5000)
        await asyncio.sleep(0.5)
        await page.click("#qualifierValueSelector li.qualifier:has-text('F-150')", timeout=5000)
        await asyncio.sleep(0.5)
        
        # Engine
        await page.click("#qualifierTypeSelector li.engine", timeout=5000)
        await asyncio.sleep(0.5)
        await page.click("#qualifierValueSelector li.qualifier:has-text('5.0L')", timeout=5000)
        await asyncio.sleep(0.5)
        
        # Submodel (first one)
        try:
            await page.click("#qualifierTypeSelector li.submodel", timeout=3000)
            await asyncio.sleep(0.5)
            await page.click("#qualifierValueSelector li.qualifier:first-child", timeout=3000)
            await asyncio.sleep(0.5)
        except:
            print("   No submodel tab")
        
        # Click Use This Vehicle to trigger options requirement
        print("\n3. Clicking 'Use This Vehicle' to trigger Options modal...")
        await page.click("input[data-action='SelectComplete']", timeout=5000)
        await asyncio.sleep(2)
        
        # Take screenshot
        await page.screenshot(path="/tmp/options_modal.png")
        print("   Screenshot saved: /tmp/options_modal.png")
        
        # NOW CAPTURE THE DOM STRUCTURE
        print("\n4. Capturing DOM structure of Options panel...")
        
        dom_info = await page.evaluate("""
            () => {
                const results = {
                    allElements: [],
                    driveTypeExpanded: null
                };
                
                // Find all elements that contain 4WD or RWD as direct text
                const walker = document.createTreeWalker(
                    document.body,
                    NodeFilter.SHOW_ELEMENT,
                    null,
                    false
                );
                
                while (walker.nextNode()) {
                    const el = walker.currentNode;
                    const rect = el.getBoundingClientRect();
                    
                    // Skip invisible elements
                    if (rect.width === 0 || rect.height === 0) continue;
                    
                    // Get direct text content (not from children)
                    let directText = '';
                    for (const child of el.childNodes) {
                        if (child.nodeType === 3) { // Text node
                            directText += child.textContent.trim();
                        }
                    }
                    
                    // Look for drive type options
                    if (directText === '4WD' || directText === 'RWD' || 
                        directText === 'AWD' || directText === 'FWD' || directText === '2WD') {
                        results.allElements.push({
                            directText: directText,
                            tag: el.tagName.toLowerCase(),
                            className: el.className,
                            id: el.id || '',
                            parentTag: el.parentElement?.tagName.toLowerCase() || '',
                            parentClass: el.parentElement?.className || '',
                            parentId: el.parentElement?.id || '',
                            grandparentTag: el.parentElement?.parentElement?.tagName.toLowerCase() || '',
                            grandparentClass: el.parentElement?.parentElement?.className || '',
                            outerHTML: el.outerHTML
                        });
                    }
                    
                    // Also find DRIVE TYPE header
                    if (directText === 'DRIVE TYPE:' || directText.startsWith('DRIVE TYPE')) {
                        results.driveTypeExpanded = {
                            directText: directText,
                            tag: el.tagName.toLowerCase(),
                            className: el.className,
                            id: el.id || '',
                            parentTag: el.parentElement?.tagName.toLowerCase() || '',
                            parentClass: el.parentElement?.className || '',
                            outerHTML: el.outerHTML.substring(0, 500)
                        };
                    }
                }
                
                return results;
            }
        """)
        
        print("\n" + "="*70)
        print("DRIVE TYPE HEADER:")
        print("="*70)
        if dom_info.get('driveTypeExpanded'):
            h = dom_info['driveTypeExpanded']
            print(f"  Tag: <{h['tag']}>")
            print(f"  Class: '{h['className']}'")
            print(f"  ID: '{h['id']}'")
            print(f"  Parent: <{h['parentTag']}> class='{h['parentClass']}'")
            print(f"  outerHTML: {h['outerHTML']}")
        else:
            print("  NOT FOUND")
        
        print("\n" + "="*70)
        print("DRIVE OPTIONS (4WD, RWD, etc.):")
        print("="*70)
        for i, opt in enumerate(dom_info.get('allElements', [])):
            print(f"\n  [{i+1}] '{opt['directText']}':")
            print(f"      Tag: <{opt['tag']}>")
            print(f"      Class: '{opt['className']}'")
            print(f"      ID: '{opt['id']}'")
            print(f"      Parent: <{opt['parentTag']}> class='{opt['parentClass']}' id='{opt['parentId']}'")
            print(f"      Grandparent: <{opt['grandparentTag']}> class='{opt['grandparentClass']}'")
            print(f"      outerHTML: {opt['outerHTML']}")
        
        if not dom_info.get('allElements'):
            print("  NO ELEMENTS FOUND!")
            print("\n  Dumping all visible text on page containing '4WD'...")
            text_search = await page.evaluate("""
                () => {
                    const results = [];
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        if (el.innerText?.includes('4WD')) {
                            results.push({
                                tag: el.tagName,
                                class: el.className,
                                text: el.innerText.substring(0, 100)
                            });
                        }
                    }
                    return results.slice(0, 20);
                }
            """)
            for item in text_search:
                print(f"    <{item['tag']}> class='{item['class']}': {item['text']}")
        
        print("\n" + "="*70)
        
        print("\n5. Pausing 30 seconds - inspect the Chrome window...")
        await asyncio.sleep(30)
        
    finally:
        print("\n6. Disconnecting...")
        await api.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
