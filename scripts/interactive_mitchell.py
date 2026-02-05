#!/usr/bin/env python3
"""
Interactive Mitchell Navigator
===============================
Launches Chrome with CDP, logs in, then pauses so YOU can navigate manually.
When you have the Options panel open with DRIVE TYPE showing, 
press Enter and this script will capture the DOM.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    print("=== Interactive Mitchell Navigator ===\n")
    
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
        
        print("\n" + "="*70)
        print("MANUAL NAVIGATION REQUIRED:")
        print("="*70)
        print("""
1. In the Chrome window, select a vehicle:
   - Year: 2018
   - Make: Ford
   - Model: F-150
   - Engine: 5.0L
   
2. Click 'Use This Vehicle' to trigger the Options modal

3. When you see the 'Highlighted sections are required.' message
   with DRIVE TYPE showing 4WD and RWD options, come back here.
""")
        print("="*70)
        
        input("\n>>> Press ENTER when the Options panel is open with DRIVE TYPE showing...\n")
        
        print("Capturing DOM structure...")
        
        # Capture the DOM structure
        dom_info = await page.evaluate("""
            () => {
                const results = {
                    driveOptions: [],
                    driveTypeHeader: null,
                    parentStructure: null
                };
                
                // Find all elements and check for direct text content
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
                    
                    // Find drive type options
                    if (directText === '4WD' || directText === 'RWD' || 
                        directText === 'AWD' || directText === 'FWD' || directText === '2WD') {
                        results.driveOptions.push({
                            text: directText,
                            tag: el.tagName.toLowerCase(),
                            className: el.className,
                            id: el.id || '',
                            
                            // Parent info
                            parentTag: el.parentElement?.tagName.toLowerCase() || '',
                            parentClass: el.parentElement?.className || '',
                            parentId: el.parentElement?.id || '',
                            
                            // Grandparent info
                            gpTag: el.parentElement?.parentElement?.tagName.toLowerCase() || '',
                            gpClass: el.parentElement?.parentElement?.className || '',
                            gpId: el.parentElement?.parentElement?.id || '',
                            
                            // Full outer HTML
                            outerHTML: el.outerHTML,
                            
                            // Parent outer HTML (truncated)
                            parentOuterHTML: el.parentElement?.outerHTML?.substring(0, 500) || ''
                        });
                    }
                    
                    // Find DRIVE TYPE header
                    if (directText.includes('DRIVE TYPE')) {
                        results.driveTypeHeader = {
                            text: directText,
                            tag: el.tagName.toLowerCase(),
                            className: el.className,
                            outerHTML: el.outerHTML.substring(0, 500)
                        };
                    }
                }
                
                return results;
            }
        """)
        
        print("\n" + "="*70)
        print("DOM CAPTURE RESULTS")
        print("="*70)
        
        print("\nDRIVE TYPE HEADER:")
        if dom_info.get('driveTypeHeader'):
            h = dom_info['driveTypeHeader']
            print(f"  Text: '{h['text']}'")
            print(f"  Tag: <{h['tag']}>")
            print(f"  Class: '{h['className']}'")
            print(f"  outerHTML: {h['outerHTML']}")
        else:
            print("  NOT FOUND")
        
        print(f"\nDRIVE OPTIONS FOUND: {len(dom_info.get('driveOptions', []))}")
        for i, opt in enumerate(dom_info.get('driveOptions', [])):
            print(f"\n[{i+1}] '{opt['text']}':")
            print(f"    Tag: <{opt['tag']}>")
            print(f"    Class: '{opt['className']}'")
            print(f"    ID: '{opt['id']}'")
            print(f"    outerHTML: {opt['outerHTML']}")
            print(f"    ---")
            print(f"    Parent: <{opt['parentTag']}> class='{opt['parentClass']}' id='{opt['parentId']}'")
            print(f"    Grandparent: <{opt['gpTag']}> class='{opt['gpClass']}' id='{opt['gpId']}'")
            print(f"    Parent outerHTML: {opt['parentOuterHTML']}")
        
        if not dom_info.get('driveOptions'):
            print("\nNO OPTIONS FOUND - Searching for any element containing '4WD'...")
            fallback = await page.evaluate("""
                () => {
                    const results = [];
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const text = el.textContent || '';
                        if (text.includes('4WD') && !text.includes('DRIVE TYPE')) {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0 && text.length < 50) {
                                results.push({
                                    tag: el.tagName,
                                    className: el.className,
                                    id: el.id,
                                    text: text.substring(0, 50),
                                    outerHTML: el.outerHTML.substring(0, 300)
                                });
                            }
                        }
                    }
                    return results.slice(0, 10);
                }
            """)
            for item in fallback:
                print(f"  <{item['tag']}> class='{item['className']}' id='{item['id']}'")
                print(f"    text: {item['text']}")
                print(f"    outerHTML: {item['outerHTML']}")
        
        print("\n" + "="*70)
        print("RECOMMENDED SELECTOR:")
        print("="*70)
        if dom_info.get('driveOptions'):
            opt = dom_info['driveOptions'][0]
            if opt['className']:
                print(f"  {opt['tag']}.{opt['className'].split()[0]}:has-text('4WD')")
            elif opt['parentClass']:
                print(f"  {opt['parentTag']}.{opt['parentClass'].split()[0]} {opt['tag']}:has-text('4WD')")
            else:
                print(f"  text=4WD (direct text selector)")
        
        print("\n" + "="*70)
        
        input("\n>>> Press ENTER to disconnect and exit...\n")
        
    finally:
        print("Disconnecting...")
        await api.disconnect()
        print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
