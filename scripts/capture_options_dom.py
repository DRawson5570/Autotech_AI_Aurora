#!/usr/bin/env python3
"""
Quick script to capture the DOM structure of the Options panel.
Run this when the Options modal is already open in Chrome.
"""
import asyncio
import sys
sys.path.insert(0, '/home/drawson/autotech_ai')

from playwright.async_api import async_playwright

async def main():
    print("Connecting to Chrome...")
    
    async with async_playwright() as p:
        # Connect to existing Chrome via CDP
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        
        # Get the first context and page
        contexts = browser.contexts
        if not contexts:
            print("No browser contexts found!")
            return
        
        context = contexts[0]
        pages = context.pages
        if not pages:
            print("No pages found!")
            return
        
        page = pages[0]
        print(f"Connected to page: {page.url}")
        
        # Capture DOM structure
        dom_info = await page.evaluate("""
            () => {
                const info = {
                    driveTypeHeader: null,
                    driveOptions: [],
                    highlightedDiv: null
                };
                
                // Find all elements
                const allElements = document.querySelectorAll('*');
                
                for (const el of allElements) {
                    const text = el.textContent?.trim() || '';
                    const directText = el.childNodes[0]?.nodeType === 3 ? el.childNodes[0].textContent.trim() : '';
                    
                    // Find DRIVE TYPE: header (exact match on direct text)
                    if (directText === 'DRIVE TYPE:' || text === 'DRIVE TYPE:') {
                        info.driveTypeHeader = {
                            tag: el.tagName,
                            className: el.className,
                            id: el.id,
                            outerHTML: el.outerHTML.substring(0, 500)
                        };
                    }
                    
                    // Find 4WD, RWD options (exact match)
                    if (directText === '4WD' || directText === 'RWD' || directText === 'AWD' || directText === 'FWD') {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            info.driveOptions.push({
                                text: directText,
                                tag: el.tagName,
                                className: el.className,
                                id: el.id,
                                parentTag: el.parentElement?.tagName,
                                parentClass: el.parentElement?.className,
                                parentId: el.parentElement?.id,
                                outerHTML: el.outerHTML
                            });
                        }
                    }
                }
                
                // Find the light blue highlighted section
                const lightBlue = document.querySelector('div[style*="rgb(198, 217, 241)"], div[style*="198, 217, 241"], [style*="background"][style*="198"]');
                if (lightBlue) {
                    info.highlightedDiv = {
                        tag: lightBlue.tagName,
                        className: lightBlue.className,
                        innerHTML: lightBlue.innerHTML.substring(0, 1000)
                    };
                }
                
                return info;
            }
        """)
        
        print("\n" + "="*60)
        print("DOM CAPTURE RESULTS")
        print("="*60)
        
        print(f"\nDRIVE TYPE Header:")
        if dom_info.get('driveTypeHeader'):
            h = dom_info['driveTypeHeader']
            print(f"  Tag: <{h['tag']}>")
            print(f"  Class: '{h['className']}'")
            print(f"  ID: '{h['id']}'")
            print(f"  outerHTML: {h['outerHTML']}")
        else:
            print("  NOT FOUND")
        
        print(f"\nDrive Options (4WD, RWD, etc):")
        for opt in dom_info.get('driveOptions', []):
            print(f"  '{opt['text']}':")
            print(f"    Tag: <{opt['tag']}>")
            print(f"    Class: '{opt['className']}'")
            print(f"    ID: '{opt['id']}'")
            print(f"    Parent: <{opt['parentTag']}> class='{opt['parentClass']}' id='{opt['parentId']}'")
            print(f"    outerHTML: {opt['outerHTML']}")
        
        print(f"\nHighlighted Section:")
        if dom_info.get('highlightedDiv'):
            h = dom_info['highlightedDiv']
            print(f"  Tag: <{h['tag']}>")
            print(f"  Class: '{h['className']}'")
            print(f"  innerHTML (first 500): {h['innerHTML'][:500]}")
        else:
            print("  NOT FOUND")
        
        print("\n" + "="*60)

if __name__ == "__main__":
    asyncio.run(main())
