"""
TSB List Tool - Retrieves Technical Service Bulletins.
"""
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Dedicated logger for TSB tool
log = logging.getLogger("tsb_tool")
log.setLevel(logging.DEBUG)

# File handler for TSB-specific logs
_fh = logging.FileHandler("/tmp/tsb_tool.log")
_fh.setLevel(logging.DEBUG)
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_fh)

# Also log to console
_ch = logging.StreamHandler()
_ch.setLevel(logging.INFO)
_ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.addHandler(_ch)


class TSBListTool(MitchellTool):
    """
    Retrieves Technical Service Bulletins (TSBs) for a vehicle.
    
    Access: Quick Access Panel > Technical Bulletins (#technicalBulletinAccess)
    
    TSBs are organized by category with counts showing how many
    bulletins are available for each system.
    """
    
    name = "get_tsb_list"
    description = "Get Technical Service Bulletins for the vehicle"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        category: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get TSBs for the vehicle.
        
        Args:
            vehicle: Vehicle specification
            category: Optional category filter (e.g., "engine", "transmission")
            query: Alternative query string
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with TSB list
        """
        # Enable debug screenshots if requested
        if kwargs.get('debug_screenshots'):
            self.debug_screenshots = True
            self._screenshot_counter = 0
        
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Step 1: Initial state
            await self.save_debug_screenshot("01_initial_state")
            
            # Skip vehicle selection if flag is set (vehicle already selected via plate lookup)
            if kwargs.get('skip_vehicle_selection'):
                print(f"[TSBTool] Skipping vehicle selection (already selected)")
                vehicle_selected = True
            else:
                # Ensure vehicle is selected
                vehicle_selected = await self.ensure_vehicle_selected(vehicle)
            
            # Step 2: After vehicle selection
            await self.save_debug_screenshot("02_after_vehicle_select")
            
            # Check if additional options are required
            if not vehicle_selected:
                required_opts = self.get_pending_required_options()
                if required_opts:
                    return ToolResult(
                        success=False,
                        error="Additional vehicle options required",
                        source=self.name,
                        needs_more_info=True,
                        required_options=required_opts
                    )
                return ToolResult(
                    success=False,
                    error="Could not select vehicle",
                    source=self.name
                )
            
            # Quick Access panel is on the HOME view, not inside any module
            tsb_selector = self.get_selector("quick_access.technical_bulletins") or "#technicalBulletinAccess"
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            
            # First check if quick access is already visible
            quick_access_visible = False
            try:
                qa_elem = await self.browser.query_selector("#quickLinkRegion")
                if qa_elem and await qa_elem.is_visible():
                    quick_access_visible = True
            except:
                pass
            
            if not quick_access_visible:
                # Navigate to Home to get the quick access panel
                await random_delay(500, 1000)
                try:
                    await self.browser.click(home_sel, timeout=5000)
                except:
                    pass
                await random_delay(1200, 2000)
            
            # Close any existing modal
            await self.close_modal()
            
            # Remove any modal mask
            await self.browser.evaluate(
                "document.querySelector('.modal_mask')?.remove()"
            )
            
            # Step 3: Before clicking TSB
            await self.save_debug_screenshot("03_before_tsb_click")
            
            # Click Technical Bulletins quick access (use #quickLinkRegion prefix)
            selector = tsb_selector
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3500)
            
            # Step 4: TSB modal open
            await self.save_debug_screenshot("04_tsb_modal_open")
            
            # Extract TSB categories with counts
            tsb_categories = await self._extract_tsb_categories()
            
            # Step 5: After categories extracted
            await self.save_debug_screenshot("05_categories_extracted")
            
            # If category specified, get TSBs for that category
            search_term = category or query
            if search_term:
                tsbs = await self._get_category_tsbs(search_term)
                
                # Step 6: After category search
                await self.save_debug_screenshot("06_after_category_search")
                
                await self.close_modal()
                
                # Step 7: Final state
                await self.save_debug_screenshot("07_final_state")
                
                return ToolResult(
                    success=True,
                    data={
                        "category": search_term,
                        "tsbs": tsbs,
                        "count": len(tsbs)
                    },
                    source=self.name
                )
            
            # Close the modal
            await self.close_modal()
            
            # Step 7: Final state
            await self.save_debug_screenshot("07_final_state")
            
            if not tsb_categories:
                return ToolResult(
                    success=False,
                    error="Could not extract TSB categories",
                    source=self.name
                )
            
            return ToolResult(
                success=True,
                data={
                    "categories": tsb_categories,
                    "total_count": sum(c.get("count", 0) for c in tsb_categories)
                },
                source=self.name,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving TSBs: {str(e)}",
                source=self.name
            )
    
    async def _extract_tsb_categories(self) -> List[Dict[str, Any]]:
        """Extract TSB categories with counts from the modal."""
        if not self.browser:
            return []
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const categories = [];
                    
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return categories;
                    
                    // TSB categories are li.usercontrol.node with text in <a> child
                    // Format: "Category Name (count)"
                    const nodes = modal.querySelectorAll('li.usercontrol.node');
                    
                    for (const node of nodes) {
                        // Text is in the <a> element inside the li
                        const linkEl = node.querySelector('a');
                        if (!linkEl) continue;
                        
                        const text = linkEl.textContent.trim();
                        if (!text) continue;
                        
                        // Parse "Category Name (count)" format
                        const match = text.match(/^(.+?)\\s*\\((\\d+)\\)$/);
                        if (match) {
                            categories.push({
                                category: match[1].trim(),
                                count: parseInt(match[2], 10)
                            });
                        } else {
                            categories.push({
                                category: text,
                                count: 0
                            });
                        }
                    }
                    
                    return categories;
                })()
            """)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error extracting TSB categories: {e}")
            return []
    
    async def _get_category_tsbs(self, category: str) -> List[Dict[str, str]]:
        """Get TSBs for a specific category by clicking it and reading the table."""
        log.info(f"_get_category_tsbs() started: category='{category}'")
        
        if not self.browser:
            log.error("  Browser not available")
            return []
        
        try:
            # Click on the category's <a> element to select it
            # Use Playwright locator for reliable clicking
            category_lower = category.lower()
            
            # Try exact match first, then partial
            locator = self.browser.locator(f'.modalDialogView li.usercontrol.node:has-text("{category}") a')
            count = await locator.count()
            log.info(f"  Locator found {count} matches for '{category}'")
            
            if count == 0:
                # Try case-insensitive partial match via JS
                log.info(f"  Trying JS click with partial match for '{category_lower}'")
                clicked = await self.browser.evaluate(f"""
                    (() => {{
                        const target = '{category_lower}';
                        const modal = document.querySelector('.modalDialogView');
                        if (!modal) return {{ clicked: false, reason: 'no modal' }};
                        
                        const nodes = modal.querySelectorAll('li.usercontrol.node');
                        const found = [];
                        for (const node of nodes) {{
                            const link = node.querySelector('a');
                            if (!link) continue;
                            const text = link.textContent.toLowerCase();
                            if (text.includes(target)) {{
                                found.push(text.trim());
                                link.click();
                                return {{ clicked: true, text: text.trim() }};
                            }}
                        }}
                        return {{ clicked: false, reason: 'not found', totalNodes: nodes.length }};
                    }})()
                """)
                log.info(f"  JS click result: {clicked}")
                if not clicked or not clicked.get('clicked'):
                    log.warning(f"  Category '{category}' not found")
                    return []
            else:
                await locator.first.click()
                log.info(f"  Clicked via Playwright locator")
            
            # Wait for table to load
            log.info("  Waiting for table to load...")
            await asyncio.sleep(2.0)
            
            # Extract TSBs from the table
            result = await self.browser.evaluate("""
                (() => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return { error: 'no modal', tsbs: [] };
                    
                    const table = modal.querySelector('table');
                    if (!table) return { error: 'no table', tsbs: [] };
                    
                    const tsbs = [];
                    const rows = table.querySelectorAll('tr');
                    
                    // Skip header row (index 0)
                    for (let i = 1; i < rows.length; i++) {
                        const cells = rows[i].querySelectorAll('td');
                        if (cells.length >= 3) {
                            tsbs.push({
                                oem_ref: cells[0].innerText.trim(),
                                title: cells[1].innerText.trim(),
                                pub_date: cells[2].innerText.trim()
                            });
                        } else if (cells.length >= 2) {
                            tsbs.push({
                                oem_ref: cells[0].innerText.trim(),
                                title: cells[1].innerText.trim(),
                                pub_date: ''
                            });
                        }
                    }
                    
                    return { totalRows: rows.length, tsbs };
                })()
            """)
            
            log.info(f"  Table extraction result: totalRows={result.get('totalRows', 0)}, tsbs={len(result.get('tsbs', []))}")
            if result.get('error'):
                log.warning(f"  Table extraction error: {result.get('error')}")
            
            return result.get('tsbs', []) if isinstance(result, dict) else []
        except Exception as e:
            log.error(f"Error getting category TSBs: {e}")
            return []
    
    async def get_tsb_details(
        self,
        vehicle: Vehicle,
        tsb_title: str
    ) -> ToolResult:
        """
        Get detailed content for a specific TSB.
        
        Args:
            vehicle: Vehicle specification
            tsb_title: Title of the TSB to retrieve
            
        Returns:
            ToolResult with TSB content
        """
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Navigate to TSBs
            await self.ensure_vehicle_selected(vehicle)
            
            # Quick Access panel is on Home view
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            try:
                await self.browser.click(home_sel, timeout=5000)
            except:
                pass
            await asyncio.sleep(1)
            await self.close_modal()
            await self.browser.evaluate(
                "document.querySelector('.modal_mask')?.remove()"
            )
            tsb_selector = self.get_selector("quick_access.technical_bulletins") or "#technicalBulletinAccess"
            selector = f"#quickLinkRegion {tsb_selector}" if tsb_selector.startswith("#") else tsb_selector
            await self.browser.click(selector, timeout=10000)
            await asyncio.sleep(2)
            
            # Escape title for JavaScript
            escaped_title = tsb_title.lower().replace("'", "\\'")
            
            # Find and click the TSB
            js_code = f"""
                (() => {{
                    const target = '{escaped_title}';
                    const nodes = document.querySelectorAll('.modalDialogView li.usercontrol.node.leaf');
                    
                    for (const node of nodes) {{
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.toLowerCase() || '';
                        if (text.includes(target)) {{
                            const showIcon = node.querySelector('.showContentIcon');
                            if (showIcon) {{
                                showIcon.click();
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }})()
            """
            clicked = await self.browser.evaluate(js_code)
            
            if not clicked:
                await self.close_modal()
                return ToolResult(
                    success=False,
                    error=f"TSB '{tsb_title}' not found",
                    source=self.name
                )
            
            await asyncio.sleep(2)
            
            # Extract TSB content
            content = await self.browser.evaluate("""
                (() => {
                    const modal = document.querySelector('.modalDialogView:last-child');
                    if (!modal) return { title: '', content: '' };
                    
                    const title = modal.querySelector('.breadcrumb, h1, .title')?.textContent?.trim() || '';
                    const content = modal.querySelector('.content')?.innerText || '';
                    
                    return { title, content };
                })()
            """)
            
            # Capture any images from the TSB modal before closing
            images = await self.extract_images_from_modal()
            if images:
                print(f"[TSBTool] Captured {len(images)} images from TSB detail")
            
            await self.close_modal()
            
            return ToolResult(
                success=True,
                data=content,
                source=self.name,
                images=images if images else None,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error getting TSB details: {str(e)}",
                source=self.name
            )
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        
        if not data:
            return "No Technical Service Bulletins found."
        
        # TSB details
        if isinstance(data, dict) and "content" in data:
            title = data.get("title", "TSB")
            content = data.get("content", "")
            return f"**{title}**\n\n{content}"
        
        # Category-specific TSBs
        if isinstance(data, dict) and "tsbs" in data:
            category = data.get("category", "")
            tsbs = data.get("tsbs", [])
            count = data.get("count", 0)
            
            lines = [f"**TSBs for {category}** ({count} found)\n"]
            for tsb in tsbs:
                lines.append(f"  - {tsb.get('title', '')}")
            return "\n".join(lines)
        
        # Category list
        if isinstance(data, dict) and "categories" in data:
            categories = data.get("categories", [])
            total = data.get("total_count", 0)
            
            lines = [f"**Technical Service Bulletins** ({total} total)\n"]
            for cat in categories:
                lines.append(f"  - {cat.get('category', '')}: {cat.get('count', 0)}")
            return "\n".join(lines)
        
        return str(data)
