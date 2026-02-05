#!/usr/bin/env python3
"""Debug script to inspect fuse block page image elements."""

import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        # Connect to existing Chrome
        browser = await p.chromium.connect_over_cdp("http://localhost:9222")
        context = browser.contexts[0]
        page = context.pages[0]
        
        print("=== Inspecting modal for image elements ===\n")
        
        # Check for various image types
        result = await page.evaluate("""
            () => {
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return { error: 'No modal found' };
                
                const result = {
                    img_elements: [],
                    object_elements: [],
                    svg_elements: [],
                    image_refs: [],
                    all_elements_with_src: []
                };
                
                // Regular img elements
                const imgs = modal.querySelectorAll('img');
                for (const img of imgs) {
                    result.img_elements.push({
                        src: img.src?.substring(0, 100),
                        alt: img.alt,
                        class: img.className,
                        width: img.width,
                        height: img.height
                    });
                }
                
                // Object elements (SVG containers)
                const objects = modal.querySelectorAll('object');
                for (const obj of objects) {
                    result.object_elements.push({
                        data: obj.data,
                        type: obj.type,
                        class: obj.className
                    });
                }
                
                // Direct SVG elements
                const svgs = modal.querySelectorAll('svg');
                for (const svg of svgs) {
                    result.svg_elements.push({
                        width: svg.getAttribute('width'),
                        height: svg.getAttribute('height'),
                        class: svg.className?.baseVal
                    });
                }
                
                // Look for image ID references in the HTML
                const html = modal.innerHTML;
                const imageIdMatches = html.match(/[A-Z]{2}\\d{7}|GM\\d+/g);
                if (imageIdMatches) {
                    result.image_refs = [...new Set(imageIdMatches)];
                }
                
                // Any element with src attribute
                const withSrc = modal.querySelectorAll('[src]');
                for (const el of withSrc) {
                    result.all_elements_with_src.push({
                        tag: el.tagName,
                        src: el.src?.substring(0, 100),
                        class: el.className
                    });
                }
                
                // Check for clsArticleImage elements (Mitchell's image container)
                const articleImages = modal.querySelectorAll('.clsArticleImage, [class*="Image"], [class*="image"]');
                result.article_images = [];
                for (const el of articleImages) {
                    result.article_images.push({
                        tag: el.tagName,
                        class: el.className,
                        innerHTML_preview: el.innerHTML?.substring(0, 200)
                    });
                }
                
                return result;
            }
        """)
        
        print("IMG elements:", result.get('img_elements', []))
        print("\nOBJECT elements:", result.get('object_elements', []))
        print("\nSVG elements:", result.get('svg_elements', []))
        print("\nImage ID references found:", result.get('image_refs', []))
        print("\nAll elements with src:", result.get('all_elements_with_src', []))
        print("\nArticle/Image class elements:", result.get('article_images', []))
        
        # Take a screenshot of the modal
        modal = await page.query_selector('.modalDialogView')
        if modal:
            await modal.screenshot(path='/tmp/fuse_modal_debug.png')
            print("\n\nScreenshot saved to /tmp/fuse_modal_debug.png")

if __name__ == "__main__":
    asyncio.run(main())
