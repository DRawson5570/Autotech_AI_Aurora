#!/usr/bin/env python3
"""
Deep inspection of Estimate Guide page structure to understand clickable operations.
"""

import asyncio
from playwright.async_api import async_playwright


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp('http://127.0.0.1:9222')
        page = browser.contexts[0].pages[0]
        await page.wait_for_load_state('networkidle')
        
        print("Navigating: Estimate Guide → Electrical → Charging System")
        
        # Navigate
        eg = page.locator('#estimateGuideAccess, a:has-text("Estimate Guide")')
        await eg.first.click(timeout=5000)
        await page.wait_for_timeout(2000)
        await page.wait_for_load_state('networkidle')
        
        elec = page.locator('a:text-is("Electrical"), div:text-is("Electrical")')
        await elec.first.click(timeout=5000)
        await page.wait_for_timeout(1500)
        
        cs = page.locator('a:text-is("Charging System"), div:text-is("Charging System")')
        await cs.first.click(timeout=5000)
        await page.wait_for_timeout(1500)
        await page.wait_for_load_state('networkidle')
        
        print("\n" + "="*70)
        print("NOW INSPECTING THE OPERATIONS LIST PAGE")
        print("="*70)
        
        # Get the full DOM structure of rightPane/itemsContainer
        print("\n--- Full itemsContainer DOM structure ---")
        dom_structure = await page.evaluate('''() => {
            const container = document.querySelector('.itemsContainer');
            if (!container) return 'NO .itemsContainer found';
            
            function getStructure(el, depth = 0) {
                let result = [];
                for (let child of el.children) {
                    const tag = child.tagName;
                    const cls = child.className || '';
                    const text = child.innerText?.trim().slice(0, 80) || '';
                    const hasClick = child.onclick || child.hasAttribute('data-click') || 
                                     (child.style.cursor === 'pointer');
                    
                    result.push({
                        depth,
                        tag,
                        cls: cls.slice(0, 50),
                        text: text.replace(/\\n/g, ' | '),
                        childCount: child.children.length,
                        clickable: hasClick
                    });
                    
                    if (child.children.length > 0 && child.children.length < 20) {
                        result = result.concat(getStructure(child, depth + 1));
                    }
                }
                return result;
            }
            
            return getStructure(container);
        }''')
        
        if isinstance(dom_structure, str):
            print(dom_structure)
        else:
            for item in dom_structure[:50]:
                indent = "  " * item['depth']
                click_marker = " [CLICK]" if item.get('clickable') else ""
                print(f"{indent}<{item['tag']}> class='{item['cls']}'{click_marker}")
                if item['text']:
                    print(f"{indent}   text: {item['text'][:70]}")
        
        # Test what Playwright can actually click
        print("\n--- Testing Playwright locators for 'ALTERNATOR' ---")
        test_text = "ALTERNATOR ASSEMBLY - Remove & Replace"
        
        # Try different approaches
        approaches = [
            ("text=", page.locator(f'text="{test_text}"')),
            ("*:text-is", page.locator(f'*:text-is("{test_text}")')),
            ("div.item:has-text", page.locator(f'.itemsContainer div.item:has-text("{test_text}")')),
            ("div.row:has-text", page.locator(f'.itemsContainer div.row:has-text("{test_text}")')),
            ("li:has-text", page.locator(f'.itemsContainer li:has-text("{test_text}")')),
            ("a:has-text", page.locator(f'.itemsContainer a:has-text("{test_text}")')),
            (".rightPane a", page.locator(f'.rightPane a:has-text("{test_text}")')),
            (".rightPane div", page.locator(f'.rightPane div:has-text("{test_text}")')),
        ]
        
        for name, loc in approaches:
            try:
                count = await loc.count()
                if count > 0:
                    first = loc.first
                    tag = await first.evaluate('el => el.tagName')
                    cls = await first.evaluate('el => el.className')
                    text = await first.inner_text()
                    text_clean = ' '.join(text.split())[:60]
                    print(f"  {name}: {count} matches")
                    print(f"    First: <{tag}> class='{cls[:40]}' text='{text_clean}'")
                else:
                    print(f"  {name}: 0 matches")
            except Exception as e:
                print(f"  {name}: ERROR - {str(e)[:50]}")
        
        # Get the actual clickable element structure
        print("\n--- Looking for click handlers on ALTERNATOR text ---")
        click_info = await page.evaluate('''() => {
            // Find the text node containing ALTERNATOR
            const walker = document.createTreeWalker(
                document.querySelector('.rightPane') || document.body,
                NodeFilter.SHOW_TEXT,
                null,
                false
            );
            
            let node;
            while (node = walker.nextNode()) {
                if (node.textContent.includes('ALTERNATOR ASSEMBLY')) {
                    const parent = node.parentElement;
                    // Walk up to find clickable ancestor
                    let el = parent;
                    let depth = 0;
                    let ancestry = [];
                    while (el && depth < 10) {
                        ancestry.push({
                            tag: el.tagName,
                            cls: el.className?.slice(0, 40) || '',
                            hasClick: !!el.onclick,
                            cursor: getComputedStyle(el).cursor
                        });
                        el = el.parentElement;
                        depth++;
                    }
                    return {
                        textContent: node.textContent.slice(0, 50),
                        parentTag: parent.tagName,
                        parentClass: parent.className,
                        ancestry
                    };
                }
            }
            return 'Not found';
        }''')
        
        print(f"Text node parent: <{click_info.get('parentTag', '?')}> class='{click_info.get('parentClass', '')}'")
        if 'ancestry' in click_info:
            print("Ancestry (child → parent):")
            for i, anc in enumerate(click_info['ancestry']):
                cursor_info = f" cursor={anc['cursor']}" if anc['cursor'] == 'pointer' else ""
                click_info_str = " [onclick]" if anc['hasClick'] else ""
                print(f"  {i}: <{anc['tag']}> class='{anc['cls']}'{click_info_str}{cursor_info}")
        
        # Check if there's an Ext JS grid or similar
        print("\n--- Checking for special grid/list structures ---")
        grid_info = await page.evaluate('''() => {
            const rp = document.querySelector('.rightPane');
            if (!rp) return 'No rightPane';
            
            // Check for common grid frameworks
            const structures = {
                extGrid: !!rp.querySelector('.x-grid, .x-grid-view'),
                kendoGrid: !!rp.querySelector('.k-grid'),
                table: !!rp.querySelector('table'),
                virtualList: !!rp.querySelector('[data-virtual], [data-virtualized]'),
                accordion: !!rp.querySelector('.accordion'),
                
                // Get all direct children of accordion
                accordionChildren: [],
            };
            
            const accordion = rp.querySelector('.accordion');
            if (accordion) {
                for (let child of accordion.children) {
                    structures.accordionChildren.push({
                        tag: child.tagName,
                        cls: child.className?.slice(0, 50) || '',
                        text: child.innerText?.slice(0, 40) || ''
                    });
                }
            }
            
            return structures;
        }''')
        
        print(f"Grid checks: {grid_info}")
        if grid_info.get('accordionChildren'):
            print("Accordion children:")
            for child in grid_info['accordionChildren'][:5]:
                print(f"  <{child['tag']}> class='{child['cls']}' text='{child['text']}'")
        
        # Screenshot
        await page.screenshot(path='/tmp/charging_system_ops.png')
        print("\nScreenshot saved to /tmp/charging_system_ops.png")
        
        # Return to landing
        onesearch = page.locator('#oneSearchPlusAccess, a:has-text("1SEARCH")')
        if await onesearch.count() > 0:
            await onesearch.first.click()
            await page.wait_for_timeout(1000)
            print("Returned to landing page")


if __name__ == "__main__":
    asyncio.run(main())
