"""
Common Specs & Procedures Tool - Retrieves specifications and procedures from ShopKeyPro.

Access: Quick Access Panel > Common Specs (#commonSpecsAccess)

The tool navigates a tree/table structure within COMMON SPECIFICATIONS & PROCEDURES:
  - Categories are displayed in a table with "System" and "Specification/Procedure" columns
  - Categories: Air Conditioning, Axle Nut/Hub Nut, Battery, Brakes, Charging, Drive Belts, etc.
  - Clicking a blue link opens a NEW PAGE inside the modal with detailed content

Content types:
  - **Specifications**: Tables with values (e.g., Refrigerant specs, torque values)
  - **Procedures**: Numbered steps with diagrams (e.g., Drive Belt Replacement)

This tool is invoked for:
  - Specs: "torque", "specification", "tightening", "clearance", "capacity"
  - Procedures: "how to", "procedure", "steps", "replace", "install", "remove", "routing"
"""
import asyncio
import base64
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Set up dedicated logger
SPECS_LOG_FILE = "/tmp/specs_procedures_tool.log"

def get_specs_logger() -> logging.Logger:
    """Get or create the specs/procedures tool logger."""
    logger = logging.getLogger("specs_procedures_tool")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        # File handler
        fh = logging.FileHandler(SPECS_LOG_FILE)
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        # Also log to stdout
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.setFormatter(formatter)
        logger.addHandler(sh)
    return logger

log = get_specs_logger()


class SpecsProceduresTool(MitchellTool):
    """
    Retrieves common specifications and procedures from ShopKeyPro.
    
    Access: Quick Access Panel > Common Specs (#commonSpecsAccess)
    
    Usage:
    - search="drive belt" → Searches for drive belt related specs/procedures
    - category="Charging" → Direct category navigation
    - topic="DRIVE BELT REPLACEMENT" → Direct link to specific topic
    
    Returns specification tables or procedure text with images.
    """
    
    name = "get_specs_procedures"
    description = "Get common specifications or service procedures"
    tier = 1
    
    # Semantic mapping for search terms
    SEARCH_MAPPING = {
        # Specs keywords
        "torque": ["Torque", "FASTENER TIGHTENING"],
        "lug nut": ["Axle Nut/Hub Nut", "Wheel Lug Nut"],
        "axle nut": ["Axle Nut/Hub Nut"],
        "hub nut": ["Axle Nut/Hub Nut"],
        "wheel bearing": ["Axle Nut/Hub Nut"],
        "refrigerant": ["Air Conditioning", "REFRIGERANT SYSTEM"],
        "a/c": ["Air Conditioning"],
        "ac": ["Air Conditioning"],
        "air conditioning": ["Air Conditioning"],
        "freon": ["Air Conditioning", "REFRIGERANT"],
        "coolant": ["Engine Cooling"],
        "cooling": ["Engine Cooling"],
        "thermostat": ["Engine Cooling"],
        "brake": ["Brakes"],
        "caliper": ["Brakes"],
        "rotor": ["Brakes"],
        "charging": ["Charging"],
        "alternator": ["Charging", "Generator"],
        "generator": ["Charging", "Generator"],
        "battery": ["Battery", "Charging"],
        
        # Procedure keywords
        "belt": ["Drive Belts"],
        "drive belt": ["Drive Belts", "DRIVE BELT REPLACEMENT"],
        "serpentine": ["Drive Belts", "DRIVE BELT REPLACEMENT"],
        "belt routing": ["Drive Belts", "Drive Belt Routing"],
        "timing belt": ["Engine Mechanical - Timing"],
        "timing chain": ["Engine Mechanical - Timing"],
    }
    
    async def execute(
        self,
        vehicle: Vehicle,
        search: Optional[str] = None,
        category: Optional[str] = None,
        topic: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get common specifications or procedures.
        
        Args:
            vehicle: Vehicle specification
            search: Search term (e.g., "drive belt", "torque specs")
            category: Category name (e.g., "Charging", "Drive Belts")
            topic: Specific topic link to click (e.g., "DRIVE BELT REPLACEMENT")
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with specifications or procedures
        """
        log.info("=" * 60)
        log.info("SPECS/PROCEDURES TOOL EXECUTE START")
        log.info(f"  vehicle: {vehicle}")
        log.info(f"  search: {search}")
        log.info(f"  category: {category}")
        log.info(f"  topic: {topic}")
        log.info("=" * 60)
        
        if not self.browser:
            log.error("Browser not available")
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Step 1: Ensure vehicle is selected
            log.info("Step 1: Ensuring vehicle selection")
            
            # Skip vehicle selection if flag is set (vehicle already selected via plate lookup)
            if kwargs.get('skip_vehicle_selection'):
                log.info(f"[SpecsProceduresTool] Skipping vehicle selection (already selected)")
                vehicle_selected = True
            else:
                vehicle_selected = await self.ensure_vehicle_selected(vehicle)
            log.info(f"Step 1 result: vehicle_ok={vehicle_selected}")
            
            if not vehicle_selected:
                return ToolResult(
                    success=False,
                    error="Could not select vehicle",
                    source=self.name
                )
            
            # Step 2: Determine what to look for
            log.info("Step 2: Determining target")
            target_category = category
            target_topic = topic
            
            if search and not target_category:
                # Map search term to category
                search_lower = search.lower().strip()
                for keyword, categories in self.SEARCH_MAPPING.items():
                    if keyword in search_lower or search_lower in keyword:
                        target_category = categories[0]
                        if len(categories) > 1:
                            target_topic = categories[1]
                        log.info(f"  Mapped '{search}' -> category='{target_category}', topic='{target_topic}'")
                        break
            
            log.info(f"  target_category: {target_category}")
            log.info(f"  target_topic: {target_topic}")
            
            # Step 3: Open Common Specs modal
            log.info("Step 3: Opening Common Specs modal")
            modal_opened = await self._open_common_specs_modal()
            log.info(f"Step 3 result: modal_opened={modal_opened}")
            
            if not modal_opened:
                return ToolResult(
                    success=False,
                    error="Could not open Common Specs modal",
                    source=self.name
                )
            
            # Step 4: Navigate to category and/or topic
            if target_category or target_topic:
                log.info(f"Step 4: Navigating to content")
                result = await self._navigate_and_extract(
                    category=target_category,
                    topic=target_topic,
                    search_term=search
                )
            else:
                # List available categories
                log.info("Step 4: Listing available categories")
                categories = await self._list_categories()
                result = ToolResult(
                    success=True,
                    data={
                        "message": "Available categories in Common Specs & Procedures",
                        "categories": categories
                    },
                    source=self.name
                )
            
            # Step 5: Close modal and return
            log.info("Step 5: Cleanup")
            await self.close_modal()
            
            return result
            
        except Exception as e:
            log.error(f"Exception in execute: {e}")
            log.error(traceback.format_exc())
            await self.close_modal()
            return ToolResult(
                success=False,
                error=f"Error: {str(e)}",
                source=self.name
            )
    
    async def _open_common_specs_modal(self) -> bool:
        """Open the Common Specs quick access modal."""
        log.info("_open_common_specs_modal() started")
        
        if not self.browser:
            return False
        
        try:
            specs_selector = self.get_selector("quick_access.common_specs") or "#commonSpecsAccess"
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            
            # Check if quick access panel is visible
            quick_access_visible = False
            try:
                qa_elem = await self.browser.query_selector("#quickLinkRegion")
                if qa_elem and await qa_elem.is_visible():
                    quick_access_visible = True
                    log.info("  Quick access panel already visible")
            except:
                pass
            
            if not quick_access_visible:
                # Navigate to Home
                log.info("  Navigating to Home for quick access panel")
                try:
                    await self.browser.click(home_sel, timeout=5000)
                except:
                    pass
                await random_delay(1200, 2000)
            
            # Close any existing modal
            log.info("  Closing any existing modal")
            await self.close_modal()
            await self.browser.evaluate("document.querySelector('.modal_mask')?.remove()")
            
            # Click Common Specs quick access
            selector = specs_selector
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            
            log.info(f"  Clicking Common Specs: {selector}")
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3000)
            
            # Wait for modal to appear
            try:
                await self.browser.wait_for_selector(
                    ".modalDialogView",
                    timeout=10000
                )
                log.info("  Modal appeared")
            except:
                log.error("  Modal did not appear")
                return False
            
            # Take screenshot
            try:
                screenshot_path = f"/tmp/specs_modal_{datetime.now().strftime('%H%M%S')}.png"
                await self.browser.screenshot(path=screenshot_path)
                log.info(f"  Screenshot: {screenshot_path}")
            except:
                pass
            
            return True
            
        except Exception as e:
            log.error(f"Exception in _open_common_specs_modal: {e}")
            return False
    
    async def _list_categories(self) -> List[Dict[str, Any]]:
        """List available categories in the Common Specs modal."""
        log.info("_list_categories() started")
        
        if not self.browser:
            return []
        
        try:
            # The modal has a table with categories
            result = await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return { error: 'No modal found' };
                    
                    const categories = [];
                    const seen = new Set();
                    
                    // Look for category headers (bold text, typically in first column)
                    const rows = modal.querySelectorAll('table tr, .contentTable tr');
                    
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const system = cells[0]?.textContent?.trim() || '';
                            const spec = cells[1]?.textContent?.trim() || '';
                            
                            // Skip empty rows and headers
                            if (!system && !spec) continue;
                            if (system === 'System') continue;
                            
                            // Check if this is a category header (no link in spec column)
                            const hasLink = cells[1]?.querySelector('a');
                            
                            if (system && !seen.has(system)) {
                                seen.add(system);
                                categories.push({
                                    name: system,
                                    type: hasLink ? 'item' : 'category'
                                });
                            }
                        }
                    }
                    
                    // Also look for tree nodes
                    const nodes = modal.querySelectorAll('li.usercontrol.node');
                    for (const node of nodes) {
                        const text = node.querySelector('a, span')?.textContent?.trim();
                        if (text && !seen.has(text)) {
                            seen.add(text);
                            categories.push({
                                name: text,
                                type: 'tree_node'
                            });
                        }
                    }
                    
                    return categories;
                }
            """)
            
            log.info(f"  Found {len(result) if isinstance(result, list) else 0} categories")
            return result if isinstance(result, list) else []
            
        except Exception as e:
            log.error(f"Exception in _list_categories: {e}")
            return []
    
    async def _navigate_and_extract(
        self,
        category: Optional[str] = None,
        topic: Optional[str] = None,
        search_term: Optional[str] = None
    ) -> ToolResult:
        """Navigate to a category/topic and extract the content."""
        log.info(f"_navigate_and_extract() started")
        log.info(f"  category: {category}, topic: {topic}, search: {search_term}")
        
        if not self.browser:
            return ToolResult(success=False, error="Browser not available", source=self.name)
        
        try:
            # If we have a specific topic, click it directly
            if topic:
                log.info(f"  Looking for topic link: '{topic}'")
                topic_clicked = await self._click_link_in_modal(topic)
                
                if topic_clicked:
                    log.info("  Topic clicked, waiting for content to load")
                    await random_delay(2000, 3000)
                    
                    # Extract the content (could be specs table or procedure)
                    content = await self._extract_page_content()
                    
                    return ToolResult(
                        success=True,
                        data=content,
                        source=self.name,
                        images=content.get("images", [])
                    )
                else:
                    log.warning(f"  Could not find topic: '{topic}'")
            
            # If we have a category, find links within that category
            if category:
                log.info(f"  Looking for category: '{category}'")
                
                # First, try to find and click the category to expand/navigate
                links = await self._find_links_for_category(category, search_term)
                
                if links:
                    log.info(f"  Found {len(links)} links for category '{category}'")
                    
                    # If only one link, click it
                    if len(links) == 1:
                        clicked = await self._click_link_in_modal(links[0]["text"])
                        if clicked:
                            await random_delay(2000, 3000)
                            content = await self._extract_page_content()
                            return ToolResult(
                                success=True,
                                data=content,
                                source=self.name,
                                images=content.get("images", [])
                            )
                    else:
                        # Multiple links - return the list for user to choose
                        return ToolResult(
                            success=True,
                            data={
                                "message": f"Found {len(links)} items for '{category}'",
                                "category": category,
                                "available_links": links
                            },
                            source=self.name
                        )
                else:
                    log.warning(f"  No links found for category: '{category}'")
            
            # Fallback - extract whatever is visible
            content = await self._extract_table_content()
            return ToolResult(
                success=True,
                data=content,
                source=self.name
            )
            
        except Exception as e:
            log.error(f"Exception in _navigate_and_extract: {e}")
            return ToolResult(success=False, error=str(e), source=self.name)
    
    async def _click_link_in_modal(self, link_text: str) -> bool:
        """Click a link inside the modal by text."""
        log.info(f"_click_link_in_modal() started: '{link_text}'")
        
        if not self.browser:
            return False
        
        try:
            # Use Playwright locator to find and click
            locator = self.browser.locator(f'.modalDialogView a:has-text("{link_text}")').first
            count = await locator.count()
            log.info(f"  Found {count} links matching '{link_text}'")
            
            if count > 0:
                await locator.click()
                log.info(f"  Clicked link: '{link_text}'")
                return True
            
            # Try partial match
            link_upper = link_text.upper()
            clicked = await self.browser.evaluate(f"""
                () => {{
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return null;
                    const links = modal.querySelectorAll('a');
                    for (const link of links) {{
                        const text = link.textContent?.trim().toUpperCase() || '';
                        if (text.includes('{link_upper}')) {{
                            link.click();
                            return text;
                        }}
                    }}
                    return null;
                }}
            """)
            
            if clicked:
                log.info(f"  Clicked via JS: '{clicked}'")
                return True
            
            log.warning(f"  Link not found: '{link_text}'")
            return False
            
        except Exception as e:
            log.error(f"Exception in _click_link_in_modal: {e}")
            return False
    
    async def _find_links_for_category(
        self, 
        category: str, 
        search_term: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Find all links within a category."""
        log.info(f"_find_links_for_category() started: category='{category}'")
        
        if not self.browser:
            return []
        
        try:
            category_upper = category.upper()
            search_upper = (search_term or "").upper()
            
            result = await self.browser.evaluate(f"""
                () => {{
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return [];
                    
                    const categoryName = '{category_upper}';
                    const searchTerm = '{search_upper}';
                    const links = [];
                    
                    // Look through table rows
                    const rows = modal.querySelectorAll('table tr');
                    let inCategory = false;
                    
                    for (const row of rows) {{
                        const cells = row.querySelectorAll('td');
                        if (cells.length < 2) continue;
                        
                        const system = cells[0]?.textContent?.trim().toUpperCase() || '';
                        const specCell = cells[1];
                        
                        // Check if this is our category header
                        if (system.includes(categoryName)) {{
                            inCategory = true;
                        }} else if (system && !system.includes(categoryName) && inCategory) {{
                            // We've moved to a different category
                            inCategory = false;
                        }}
                        
                        // If in our category (or the system cell mentions it), collect links
                        if (inCategory || system.includes(categoryName)) {{
                            const anchors = specCell?.querySelectorAll('a') || [];
                            for (const a of anchors) {{
                                const text = a.textContent?.trim();
                                if (text) {{
                                    // If search term specified, filter
                                    if (searchTerm && !text.toUpperCase().includes(searchTerm)) {{
                                        continue;
                                    }}
                                    links.push({{
                                        text: text,
                                        href: a.href || ''
                                    }});
                                }}
                            }}
                        }}
                    }}
                    
                    // Also search all links if nothing found
                    if (links.length === 0) {{
                        const allLinks = modal.querySelectorAll('a');
                        for (const a of allLinks) {{
                            const text = a.textContent?.trim();
                            if (text && text.toUpperCase().includes(categoryName)) {{
                                links.push({{
                                    text: text,
                                    href: a.href || ''
                                }});
                            }}
                        }}
                    }}
                    
                    return links.slice(0, 20);
                }}
            """)
            
            log.info(f"  Found {len(result)} links")
            return result if isinstance(result, list) else []
            
        except Exception as e:
            log.error(f"Exception in _find_links_for_category: {e}")
            return []
    
    async def _extract_page_content(self) -> Dict[str, Any]:
        """Extract content from the current page (after clicking a link)."""
        log.info("_extract_page_content() started")
        
        if not self.browser:
            return {"error": "Browser not available"}
        
        try:
            # Take screenshot
            screenshot_path = f"/tmp/specs_content_{datetime.now().strftime('%H%M%S')}.png"
            await self.browser.screenshot(path=screenshot_path)
            log.info(f"  Screenshot: {screenshot_path}")
            
            # Extract text content
            content = await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return { error: 'No modal found' };
                    
                    // Get the title/heading
                    const title = modal.querySelector('h1, h2, .title, .articleTitle')?.textContent?.trim() || 
                                  modal.querySelector('.breadcrumb')?.textContent?.trim() || '';
                    
                    // Get table data (for specs)
                    const tables = [];
                    const tableElems = modal.querySelectorAll('table');
                    for (const table of tableElems) {
                        const rows = [];
                        const tableRows = table.querySelectorAll('tr');
                        for (const row of tableRows) {
                            const cells = [];
                            const cellElems = row.querySelectorAll('td, th');
                            for (const cell of cellElems) {
                                cells.push(cell.textContent?.trim() || '');
                            }
                            if (cells.length > 0 && cells.some(c => c)) {
                                rows.push(cells);
                            }
                        }
                        if (rows.length > 0) {
                            tables.push(rows);
                        }
                    }
                    
                    // Get procedure steps (for procedures)
                    const steps = [];
                    const orderedLists = modal.querySelectorAll('ol');
                    for (const ol of orderedLists) {
                        const items = ol.querySelectorAll('li');
                        for (let i = 0; i < items.length; i++) {
                            steps.push({
                                number: i + 1,
                                text: items[i].textContent?.trim() || ''
                            });
                        }
                    }
                    
                    // Also get any numbered paragraphs
                    const paragraphs = modal.querySelectorAll('p, div.step');
                    for (const p of paragraphs) {
                        const text = p.textContent?.trim() || '';
                        const match = text.match(/^(\\d+)\\.\\s*(.+)/);
                        if (match) {
                            steps.push({
                                number: parseInt(match[1]),
                                text: match[2]
                            });
                        }
                    }
                    
                    // Get all text content
                    const allText = modal.textContent?.trim() || '';
                    
                    // Get image count
                    const images = modal.querySelectorAll('img, object, svg');
                    
                    return {
                        title: title,
                        tables: tables,
                        steps: steps,
                        imageCount: images.length,
                        textPreview: allText.substring(0, 2000)
                    };
                }
            """)
            
            log.info(f"  Extracted: title='{content.get('title', '')[:50]}', tables={len(content.get('tables', []))}, steps={len(content.get('steps', []))}")
            
            # Capture images
            images = await self._capture_images()
            if images:
                content["images"] = images
                log.info(f"  Captured {len(images)} images")
            
            return content
            
        except Exception as e:
            log.error(f"Exception in _extract_page_content: {e}")
            return {"error": str(e)}
    
    async def _extract_table_content(self) -> Dict[str, Any]:
        """Extract table content from the modal (initial view)."""
        log.info("_extract_table_content() started")
        
        if not self.browser:
            return {"error": "Browser not available"}
        
        try:
            content = await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return { error: 'No modal found' };
                    
                    const specs = [];
                    const rows = modal.querySelectorAll('table tr');
                    
                    for (const row of rows) {
                        const cells = row.querySelectorAll('td');
                        if (cells.length >= 2) {
                            const system = cells[0]?.textContent?.trim() || '';
                            const spec = cells[1]?.textContent?.trim() || '';
                            
                            if (system || spec) {
                                specs.push({
                                    system: system,
                                    specification: spec
                                });
                            }
                        }
                    }
                    
                    return {
                        type: 'specs_table',
                        count: specs.length,
                        specs: specs.slice(0, 50)
                    };
                }
            """)
            
            log.info(f"  Extracted {content.get('count', 0)} spec entries")
            return content
            
        except Exception as e:
            log.error(f"Exception in _extract_table_content: {e}")
            return {"error": str(e)}
    
    async def _capture_images(self) -> List[Dict[str, str]]:
        """Capture images from the current page."""
        log.info("_capture_images() started")
        
        if not self.browser:
            return []
        
        images = []
        try:
            # Find image holders
            holders = await self.browser.query_selector_all('.modalDialogView .imageHolder, .modalDialogView img, .modalDialogView object')
            log.info(f"  Found {len(holders)} image elements")
            
            for i, holder in enumerate(holders[:5]):  # Limit to 5 images
                try:
                    # Get caption if available
                    caption = await holder.evaluate("""
                        el => {
                            const cap = el.querySelector('.imageCaption') || 
                                       el.closest('.imageHolder')?.querySelector('.imageCaption');
                            return cap?.textContent?.trim() || `Figure ${arguments[0] + 1}`;
                        }
                    """, i)
                    
                    # Take screenshot of the element
                    screenshot = await holder.screenshot(type="png")
                    if screenshot:
                        b64 = base64.b64encode(screenshot).decode('utf-8')
                        images.append({
                            "name": caption or f"Figure {i+1}",
                            "base64": b64,
                            "mime_type": "image/png"
                        })
                        log.info(f"  Captured image {i+1}: {caption}")
                except Exception as e:
                    log.debug(f"  Could not capture image {i+1}: {e}")
            
        except Exception as e:
            log.error(f"Exception in _capture_images: {e}")
        
        return images
