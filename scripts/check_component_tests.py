#!/usr/bin/env python
"""Quick script to check Component Tests tree state."""
import asyncio
import os
from playwright.async_api import async_playwright

async def check_tree():
    cdp_url = os.environ.get("CHROME_CDP_URL", "http://localhost:9222")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        contexts = browser.contexts
        page = contexts[0].pages[0]
        
        # Get modal HTML structure to understand tree
        result = await page.evaluate("""() => {
            const modal = document.querySelector(".modalDialogView");
            if (!modal) return {error: "no modal"};
            
            // Get tree structure
            const tree = modal.querySelector("ul.tree, ul.usercontrol");
            if (!tree) return {error: "no tree found"};
            
            // Get all li nodes - check for BOTH class patterns
            const nodes = modal.querySelectorAll("li.usercontrol, li.node");
            const info = [];
            
            nodes.forEach(n => {
                const link = n.querySelector(":scope > a");
                const name = link ? link.textContent.trim() : n.textContent.trim().split("\\n")[0];
                const isOpen = n.classList.contains("open");
                const isBranch = n.classList.contains("branch");
                const isLeaf = n.classList.contains("leaf");
                const isVisible = n.offsetHeight > 0;
                
                // What clickable elements are inside?
                const expander = n.querySelector('.expander');
                const toggle = n.querySelector('span.toggle');
                const directLink = n.querySelector(':scope > a');
                
                info.push({
                    name: name.substring(0, 40), 
                    isOpen, 
                    isBranch, 
                    isLeaf,
                    isVisible,
                    classes: n.className,
                    hasExpander: !!expander,
                    hasToggle: !!toggle,
                    hasDirectLink: !!directLink,
                    expanderClass: expander ? expander.className : null,
                    directLinkHref: directLink ? directLink.getAttribute('href') : null
                });
            });
            
            return {nodes: info, treeClass: tree.className};
        }""")
        
        if result.get("error"):
            print(f"Error: {result['error']}")
            return
        
        print(f"Tree class: {result.get('treeClass')}")
        print(f"\nFound {len(result.get('nodes', []))} nodes:\n")
        
        for r in result.get("nodes", []):
            name = r.get("name", "?")
            is_branch = r.get("isBranch")
            is_open = r.get("isOpen")
            is_visible = r.get("isVisible")
            has_expander = r.get("hasExpander")
            has_toggle = r.get("hasToggle")
            has_link = r.get("hasDirectLink")
            
            if is_branch:
                status = "[▼ OPEN]" if is_open else "[▶ closed]"
                vis = "" if is_visible else " [HIDDEN]"
                clickable = []
                if has_expander:
                    clickable.append(f"expander({r.get('expanderClass')})")
                if has_toggle:
                    clickable.append("toggle")
                if has_link:
                    clickable.append("link")
                click_info = f" → click: {', '.join(clickable)}" if clickable else " → NO CLICKABLE!"
                print(f"{status} {name}{vis}{click_info}")
            else:
                indent = "    "
                vis = "" if is_visible else " [HIDDEN]"
                print(f"{indent}• {name}{vis}")

if __name__ == "__main__":
    asyncio.run(check_tree())
