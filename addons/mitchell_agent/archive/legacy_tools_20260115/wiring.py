"""
Wiring Diagram Tool - Retrieves wiring diagrams from ShopKeyPro.

Wiring diagrams are accessed via Quick Access Panel > Wiring Diagrams (#wiringDiagramsAccess)

The tool navigates a tree structure within SYSTEM WIRING DIAGRAMS:
  Category (e.g., "STARTING/CHARGING", "AIR CONDITIONING")
    └── Engine variant (for ENGINE PERFORMANCE and TRANSMISSION only)
        └── Diagram figures (SVG images)

Most categories are "leaf" nodes - clicking them loads all diagrams directly.
ENGINE PERFORMANCE and TRANSMISSION are "branch" nodes requiring engine selection.

The WIRING_SEMANTIC_MAP in selectors.py maps common search terms
to categories (e.g., "alternator" → "STARTING/CHARGING").
"""
import asyncio
import base64
import logging
import traceback
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

from .base import MitchellTool, ToolResult, Vehicle, random_delay
from .. import selectors as SEL

# Set up dedicated wiring tool logger
WIRING_LOG_FILE = "/tmp/wiring_tool.log"

def get_wiring_logger() -> logging.Logger:
    """Get or create the wiring tool logger."""
    logger = logging.getLogger("wiring_tool")
    if not logger.handlers:
        logger.setLevel(logging.DEBUG)
        # File handler
        fh = logging.FileHandler(WIRING_LOG_FILE)
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

log = get_wiring_logger()


class WiringDiagramTool(MitchellTool):
    """
    Retrieves wiring diagrams for vehicle electrical systems.
    
    Access: Quick Access Panel > Wiring Diagrams (#wiringDiagramsAccess)
    
    Usage:
    - search="alternator" → Uses semantic mapping to find STARTING/CHARGING
    - category="AIR CONDITIONING" → Direct category navigation
    - No params → Lists available categories
    
    Returns diagram images for LLM analysis.
    """
    
    name = "get_wiring_diagram"
    description = "Get wiring diagrams for vehicle electrical systems"
    tier = 1
    
    def _find_category_for_search(self, search_term: str) -> Optional[str]:
        """
        Find the wiring diagram category for a search term using semantic mapping.
        
        Examples:
            "alternator" → "STARTING/CHARGING"
            "A/C compressor" → "AIR CONDITIONING"
            "headlight" → "HEADLIGHTS"
        """
        mapping = SEL.WIRING_SEMANTIC_MAP
        search_lower = search_term.lower().strip()
        
        # Direct match first
        if search_lower in mapping:
            return mapping[search_lower]
        
        # Partial match - check if search term contains a mapped keyword
        for keyword, category in mapping.items():
            if keyword in search_lower or search_lower in keyword:
                log.info(f"Mapped '{search_term}' → '{category}' (via '{keyword}')")
                return category
        
        return None
    
    async def execute(
        self,
        vehicle: Vehicle,
        category: Optional[str] = None,
        search: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get wiring diagrams for the vehicle.
        
        Args:
            vehicle: Vehicle specification
            category: Direct category name (e.g., "STARTING/CHARGING", "AIR CONDITIONING")
            search: Search term - will be mapped to category via WIRING_SEMANTIC_MAP
            
        Returns:
            ToolResult with diagram images and category info
        """
        log.info("="*60)
        log.info(f"WIRING TOOL EXECUTE START")
        log.info(f"  vehicle: {vehicle}")
        log.info(f"  category: {category}")
        log.info(f"  search: {search}")
        log.info("="*60)
        
        if not self.browser:
            log.error("Browser controller not available")
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Skip vehicle selection if flag is set (vehicle already selected via plate lookup)
            if kwargs.get('skip_vehicle_selection'):
                log.info(f"[WiringTool] Skipping vehicle selection (already selected)")
                vehicle_ok = True
            else:
                # Ensure vehicle is selected
                log.info(f"Step 1: Ensuring vehicle selection: {vehicle}")
                vehicle_ok = await self.ensure_vehicle_selected(vehicle)
            log.info(f"Step 1 result: vehicle_ok={vehicle_ok}")
            
            if not vehicle_ok:
                required_opts = self.get_pending_required_options()
                log.warning(f"Vehicle selection failed. Required options: {required_opts}")
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
            
            # Determine target category
            target_category = None
            search_term = search
            
            log.info(f"Step 2: Determining target category")
            if category:
                target_category = category.upper()
                log.info(f"  Direct category specified: {target_category}")
            elif search:
                log.info(f"  Searching for mapping for: '{search}'")
                target_category = self._find_category_for_search(search)
                if target_category:
                    log.info(f"  Found semantic mapping: '{search}' -> '{target_category}'")
                else:
                    # No mapping found - try to find in tree directly
                    log.info(f"  No semantic mapping for '{search}', will search tree directly")
            else:
                log.info(f"  No category or search specified, will list categories")
            
            # Open wiring diagrams page (not a modal - it's page navigation)
            log.info(f"Step 3: Opening wiring diagrams page")
            page_opened = await self._open_wiring_page()
            log.info(f"Step 3 result: page_opened={page_opened}")
            
            if not page_opened:
                log.error("Could not open Wiring Diagrams page")
                return ToolResult(
                    success=False,
                    error="Could not open Wiring Diagrams page",
                    source=self.name
                )
            
            # Page should already be at SYSTEM WIRING DIAGRAMS with category links visible
            log.info(f"Step 4: Verifying SYSTEM WIRING DIAGRAMS page")
            await self._verify_wiring_page()
            
            # If no category specified, list available categories
            if not target_category and not search:
                log.info(f"Step 5: No category/search - listing categories")
                categories = await self._list_categories()
                log.info(f"  Found {len(categories)} categories")
                # Navigate back home after listing
                await self._navigate_home()
                return ToolResult(
                    success=True,
                    data={
                        "message": "Available wiring diagram categories. Use 'category' or 'search' parameter to get diagrams.",
                        "categories": categories,
                        "hint": "Example: search='alternator' will get STARTING/CHARGING diagrams"
                    },
                    source=self.name
                )
            
            # Navigate to category and capture diagrams
            if target_category:
                log.info(f"Step 5: Getting diagrams for category: {target_category}")
                result = await self._get_category_diagrams(target_category, vehicle, search_term)
                log.info(f"Step 5 result: success={result.success}, images={len(result.images) if result.images else 0}")
                return result
            else:
                # Try direct tree search
                log.info(f"Step 5: Searching tree directly for: {search}")
                result = await self._search_tree_for_term(search, vehicle)
                log.info(f"Step 5 result: success={result.success}")
                return result
            
        except Exception as e:
            log.error(f"EXCEPTION in execute(): {e}")
            log.error(traceback.format_exc())
            # Try to take a screenshot for debugging
            try:
                if self.browser:
                    screenshot_path = f"/tmp/wiring_error_{datetime.now().strftime('%H%M%S')}.png"
                    await self.browser.screenshot(path=screenshot_path)
                    log.info(f"Error screenshot saved to {screenshot_path}")
            except:
                pass
            return ToolResult(
                success=False,
                error=f"Error retrieving wiring diagrams: {str(e)}",
                source=self.name
            )
    
    async def _open_wiring_page(self) -> bool:
        """Open the wiring diagrams page via quick access panel.
        
        Note: Wiring Diagrams opens as a PAGE navigation, not a modal.
        After clicking #wiringDiagramsAccess, browser navigates to:
        Wiring Diagrams > SYSTEM WIRING DIAGRAMS page with category links.
        """
        log.info("_open_wiring_page() started")
        
        if not self.browser:
            log.error("  Browser not available")
            return False
        
        try:
            # Get selectors
            wiring_sel = self.get_selector("quick_access.wiring_diagrams") or "#wiringDiagramsAccess"
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            log.debug(f"  Selectors: wiring={wiring_sel}, home={home_sel}")
            
            # Check if quick access panel is visible
            quick_access_visible = False
            try:
                qa_elem = await self.browser.query_selector("#quickLinkRegion")
                if qa_elem and await qa_elem.is_visible():
                    quick_access_visible = True
                    log.info("  Quick access panel already visible")
            except Exception as e:
                log.debug(f"  Error checking quick access: {e}")
            
            if not quick_access_visible:
                log.info("  Navigating to Home for quick access panel...")
                try:
                    await self.browser.click(home_sel, timeout=5000)
                    await random_delay(1500, 2500)
                    log.info("  Clicked Home button")
                except Exception as e:
                    log.warning(f"  Could not click Home: {e}")
            
            # Wait for quick access panel
            try:
                await self.browser.wait_for_selector("#quickLinkRegion", timeout=8000)
                log.info("  Quick access panel appeared")
            except Exception as e:
                log.warning(f"  Timeout waiting for quick access panel: {e}")
            
            # Close any existing modal
            log.info("  Closing any existing modal")
            await self.close_modal()
            
            # Remove any modal mask
            await self.browser.evaluate("document.querySelector('.modal_mask')?.remove()")
            
            # Click Wiring Diagrams quick access
            selector = wiring_sel
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            
            log.info(f"  Clicking wiring diagrams access: {selector}")
            await random_delay(400, 800)
            
            clicked = await self.click_quick_access(selector)
            log.info(f"  Click result: {clicked}")
            if not clicked:
                log.error("  Failed to click wiring diagrams access")
                return False
            
            await random_delay(2000, 3000)
            
            # Wiring Diagrams opens in a .modalDialogView modal
            # The modal shows a tree structure:
            # - "SYSTEM WIRING DIAGRAMS" (parent - needs to be clicked to navigate)
            #   - clicking shows "AIR CONDITIONING", "STARTING/CHARGING", etc. (categories)
            log.info("  Waiting for wiring diagrams modal to load...")
            
            page_loaded = False
            try:
                # Wait for SYSTEM WIRING DIAGRAMS link to appear INSIDE THE MODAL
                await self.browser.wait_for_selector(
                    ".modalDialogView a:has-text('SYSTEM WIRING DIAGRAMS'), .modalDialogView a:has-text('System Wiring Diagrams')",
                    timeout=15000
                )
                log.info("  Wiring diagrams modal loaded - found SYSTEM WIRING DIAGRAMS link")
                await random_delay(500, 1000)
                page_loaded = True
            except Exception as e:
                log.warning(f"  Timeout waiting for wiring page: {e}")
                page_loaded = False
            
            if page_loaded:
                # Now click SYSTEM WIRING DIAGRAMS to expand it
                log.info("  Clicking SYSTEM WIRING DIAGRAMS to expand categories...")
                expanded = await self._expand_system_wiring_diagrams()
                if expanded:
                    log.info("  SYSTEM WIRING DIAGRAMS expanded - categories should be visible")
                    await random_delay(1000, 1500)
                else:
                    log.warning("  Could not expand SYSTEM WIRING DIAGRAMS")
            
            # Take screenshot for debugging
            try:
                screenshot_path = f"/tmp/wiring_page_{datetime.now().strftime('%H%M%S')}.png"
                await self.browser.screenshot(path=screenshot_path)
                log.info(f"  Screenshot saved: {screenshot_path}")
            except Exception as e:
                log.debug(f"  Could not take screenshot: {e}")
            
            return page_loaded
            
        except Exception as e:
            log.error(f"Exception in _open_wiring_modal: {e}")
            log.error(traceback.format_exc())
            return False
    
    async def _expand_system_wiring_diagrams(self) -> bool:
        """Click on SYSTEM WIRING DIAGRAMS to expand and show category links.
        
        The wiring diagrams opens in .modalDialogView modal.
        Click 'SYSTEM WIRING DIAGRAMS' link to navigate to the category list.
        """
        log.info("_expand_system_wiring_diagrams() started")
        
        if not self.browser:
            log.error("  Browser not available")
            return False
        
        try:
            # Look for SYSTEM WIRING DIAGRAMS link INSIDE THE MODAL
            locator = self.browser.locator(".modalDialogView a:has-text('SYSTEM WIRING DIAGRAMS')")
            count = await locator.count()
            log.info(f"  Found {count} 'SYSTEM WIRING DIAGRAMS' links in modal")
            
            if count == 0:
                # Try case-insensitive
                locator = self.browser.locator(".modalDialogView a:has-text('System Wiring Diagrams')")
                count = await locator.count()
                log.info(f"  Found {count} 'System Wiring Diagrams' links (case-insensitive)")
            
            if count > 0:
                await locator.first.click()
                log.info("  Clicked SYSTEM WIRING DIAGRAMS")
                await random_delay(1500, 2500)
                
                # Wait for categories to appear inside modal
                try:
                    await self.browser.wait_for_selector(
                        ".modalDialogView a:has-text('STARTING/CHARGING'), .modalDialogView a:has-text('AIR CONDITIONING'), .modalDialogView a:has-text('HEADLIGHTS')",
                        timeout=10000
                    )
                    log.info("  Categories expanded and visible in modal")
                    return True
                except Exception as e:
                    log.warning(f"  Categories did not appear after click: {e}")
                    # Take screenshot for debugging
                    try:
                        screenshot_path = f"/tmp/wiring_after_swd_click_{datetime.now().strftime('%H%M%S')}.png"
                        await self.browser.screenshot(path=screenshot_path)
                        log.info(f"  Screenshot saved: {screenshot_path}")
                    except:
                        pass
                    return False
            else:
                log.error("  Could not find SYSTEM WIRING DIAGRAMS link in modal")
                return False
                
        except Exception as e:
            log.error(f"Exception in _expand_system_wiring_diagrams: {e}")
            log.error(traceback.format_exc())
            return False
    
    async def _verify_wiring_page(self) -> bool:
        """Verify we're on the SYSTEM WIRING DIAGRAMS page with category links.
        
        After expansion, categories appear as <a> links under SYSTEM WIRING DIAGRAMS.
        """
        log.info("_verify_wiring_page() started")
        
        if not self.browser:
            log.error("  Browser not available")
            return False
        
        try:
            # Check page content - find expanded category links
            log.info("  Checking page for expanded category links...")
            result = await self.browser.evaluate("""
                () => {
                    // Find all links on the page
                    const links = document.querySelectorAll('a');
                    const categories = [];
                    
                    // These are the categories that should be visible after expanding SYSTEM WIRING DIAGRAMS
                    const knownCategories = [
                        'AIR CONDITIONING', 'STARTING/CHARGING', 'STARTING', 'CHARGING',
                        'HEADLIGHTS', 'ANTI-LOCK BRAKES', 'ANTI-THEFT', 'BODY CONTROL',
                        'COMPUTER DATA', 'COOLING FAN', 'CRUISE CONTROL',
                        'DEFOGGERS', 'ENGINE PERFORMANCE', 'EXTERIOR LIGHTS',
                        'GROUND DISTRIBUTION', 'HORN', 'INSTRUMENT CLUSTER',
                        'POWER WINDOWS', 'RADIO', 'SHIFT INTERLOCK'
                    ];
                    
                    for (const link of links) {
                        const text = link.textContent?.trim().toUpperCase() || '';
                        if (!text) continue;
                        
                        // Check if this link exactly matches a known category
                        for (const cat of knownCategories) {
                            if (text === cat || text.includes(cat)) {
                                categories.push(text.substring(0, 50));
                                break;
                            }
                        }
                    }
                    
                    // Also check breadcrumb
                    const breadcrumb = document.querySelector('#mainBreadCrumb');
                    const breadcrumbText = breadcrumb?.textContent || '';
                    
                    // Check if SYSTEM WIRING DIAGRAMS is in breadcrumb (means we're in the right section)
                    const inSystemWiring = breadcrumbText.toUpperCase().includes('SYSTEM WIRING');
                    
                    return {
                        found: categories.length > 0,
                        categories: categories.slice(0, 20),
                        breadcrumb: breadcrumbText.substring(0, 100),
                        inSystemWiring: inSystemWiring,
                        totalLinks: links.length
                    };
                }
            """)
            log.info(f"  Page check result: {result}")
            
            if result.get("found"):
                cats = result.get('categories', [])
                log.info(f"  Found {len(cats)} category links: {cats[:5]}")
                return True
            elif result.get("inSystemWiring"):
                log.info("  In SYSTEM WIRING section but no categories found yet")
                return True  # We're in the right place
            else:
                log.warning(f"  No category links found. Breadcrumb: {result.get('breadcrumb')}")
                return False
            
        except Exception as e:
            log.error(f"Exception in _verify_wiring_page: {e}")
            log.error(traceback.format_exc())
            return False
    
    async def _list_categories(self) -> List[Dict[str, Any]]:
        """List available wiring diagram categories from the page."""
        log.info("_list_categories() started")
        
        if not self.browser:
            log.error("  Browser not available")
            return []
        
        try:
            # Note: self.browser IS the Playwright Page object
            
            # Find category links on the page
            categories = await self.browser.evaluate("""
                () => {
                    const links = document.querySelectorAll('a');
                    const categories = [];
                    const seen = new Set();
                    
                    // Known wiring diagram categories
                    const knownCategories = [
                        'AIR CONDITIONING', 'ANTI-LOCK BRAKES', 'ANTI-THEFT',
                        'BODY CONTROL MODULES', 'COMPUTER DATA LINES', 'COOLING FAN',
                        'CRUISE CONTROL', 'DEFOGGERS', 'ELECTRONIC POWER STEERING',
                        'ENGINE PERFORMANCE', 'EXTERIOR LIGHTS', 'GROUND DISTRIBUTION',
                        'HEADLIGHTS', 'HORN', 'INSTRUMENT CLUSTER', 'INTERIOR LIGHTS',
                        'NAVIGATION', 'POWER DISTRIBUTION', 'POWER DOOR LOCKS',
                        'POWER MIRRORS', 'POWER SEATS', 'POWER TOP/SUNROOF',
                        'POWER WINDOWS', 'RADIO', 'SHIFT INTERLOCK', 'STARTING/CHARGING',
                        'SUPPLEMENTAL RESTRAINTS', 'TRANSMISSION', 'TRUNK', 'WARNING SYSTEMS',
                        'WIPER/WASHER'
                    ];
                    
                    // Branch categories that need engine selection
                    const branchCategories = ['ENGINE PERFORMANCE', 'TRANSMISSION'];
                    
                    for (const link of links) {
                        const text = link.textContent?.trim().toUpperCase() || '';
                        if (!text || seen.has(text)) continue;
                        
                        // Skip non-category items
                        if (text.includes('USING MITCHELL') || text.includes('OEM ')) continue;
                        
                        // Check if this matches a known category
                        for (const cat of knownCategories) {
                            if (text.includes(cat) || cat === text) {
                                seen.add(text);
                                const isBranch = branchCategories.some(b => text.includes(b));
                                categories.push({
                                    name: text,
                                    type: isBranch ? 'branch' : 'leaf',
                                    requires_engine: isBranch
                                });
                                break;
                            }
                        }
                    }
                    
                    return { categories: categories, totalLinks: links.length };
                }
            """)
            
            if isinstance(categories, dict):
                log.info(f"  Found {len(categories.get('categories', []))} categories from {categories.get('totalLinks', 0)} links")
                for cat in categories.get('categories', [])[:5]:
                    log.debug(f"    - {cat.get('name')} ({cat.get('type')})")
                return categories.get('categories', [])
            
            log.info(f"  Found {len(categories)} categories")
            return categories or []
            
        except Exception as e:
            log.error(f"Exception in _list_categories: {e}")
            log.error(traceback.format_exc())
            return []
    
    async def _navigate_home(self) -> bool:
        """Navigate back to home page after viewing wiring diagrams."""
        log.info("_navigate_home() started")
        
        if not self.browser:
            return False
        
        try:
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            await self.browser.click(home_sel, timeout=5000)
            await random_delay(1000, 1500)
            log.info("  Navigated back to home")
            return True
        except Exception as e:
            log.warning(f"  Could not navigate home: {e}")
            return False
    
    async def _get_category_diagrams(
        self, 
        category: str, 
        vehicle: Vehicle,
        search_term: Optional[str] = None
    ) -> ToolResult:
        """Navigate to a category and capture its diagrams."""
        log.info(f"_get_category_diagrams() started")
        log.info(f"  category: {category}")
        log.info(f"  vehicle: {vehicle}")
        log.info(f"  search_term: {search_term}")
        
        if not self.browser:
            log.error("  Browser not available")
            return ToolResult(
                success=False,
                error="Browser not available",
                source=self.name
            )
        
        try:
            # Check if this is a branch category (needs engine selection)
            wiring_cfg = self._load_wiring_config()
            cat_info = wiring_cfg.get("system_wiring_categories", {}).get(category, {})
            is_branch = cat_info.get("type") == "branch"
            log.info(f"  Category type: {'branch' if is_branch else 'leaf'}")
            
            # Find and click the category
            log.info(f"  Step A: Clicking category '{category}'")
            clicked = await self._click_category(category)
            log.info(f"  Step A result: clicked={clicked}")
            
            if not clicked:
                log.error(f"  Category '{category}' not found in wiring diagrams")
                await self._navigate_home()
                return ToolResult(
                    success=False,
                    error=f"Category '{category}' not found in wiring diagrams",
                    source=self.name
                )
            
            await random_delay(1500, 2500)
            
            # If branch category, need to select engine variant
            if is_branch:
                engine_variant = self._get_engine_variant(vehicle)
                log.info(f"  Step B: Branch category - selecting engine variant: {engine_variant}")
                
                variant_clicked = await self._click_engine_variant(engine_variant)
                log.info(f"  Step B result: variant_clicked={variant_clicked}")
                
                if not variant_clicked:
                    # Try to get available variants
                    variants = await self._get_available_variants()
                    log.error(f"  Engine variant '{engine_variant}' not found. Available: {variants}")
                    await self._navigate_home()
                    return ToolResult(
                        success=False,
                        error=f"Engine variant '{engine_variant}' not found. Available: {variants}",
                        source=self.name,
                        data={"available_variants": variants}
                    )
                
                await random_delay(1500, 2500)
            
            # Wait for diagrams to load and capture them
            log.info("  Step C: Waiting for diagrams to load")
            await self._wait_for_diagrams_load()
            
            # Take screenshot for debugging
            try:
                screenshot_path = f"/tmp/wiring_diagrams_{datetime.now().strftime('%H%M%S')}.png"
                await self.browser.screenshot(path=screenshot_path)
                log.info(f"  Diagram screenshot saved: {screenshot_path}")
            except Exception as e:
                log.debug(f"  Could not take screenshot: {e}")
            
            # Capture all diagram images
            log.info("  Step D: Capturing diagram images")
            images = await self._capture_all_diagrams()
            log.info(f"  Step D result: captured {len(images)} images")
            
            # Get diagram titles/captions
            log.info("  Step E: Getting diagram info")
            diagram_info = await self._get_diagram_info()
            log.info(f"  Step E result: found {len(diagram_info)} diagram infos")
            
            log.info("  Step F: Navigating back home")
            await self._navigate_home()
            
            if not images:
                log.warning(f"  No diagram images found for '{category}'")
                return ToolResult(
                    success=False,
                    error=f"No diagram images found for '{category}'",
                    source=self.name,
                    data={"category": category, "diagrams_found": diagram_info}
                )
            
            log.info(f"  SUCCESS: Retrieved {len(images)} diagram(s) for {category}")
            return ToolResult(
                success=True,
                data={
                    "category": category,
                    "search_term": search_term,
                    "diagram_count": len(images),
                    "diagrams": diagram_info,
                    "message": f"Retrieved {len(images)} wiring diagram(s) for {category}. Analyze the images to answer the user's question."
                },
                source=self.name,
                images=images
            )
            
        except Exception as e:
            log.error(f"Exception in _get_category_diagrams: {e}")
            log.error(traceback.format_exc())
            # Try to take error screenshot
            try:
                if self.browser:
                    screenshot_path = f"/tmp/wiring_category_error_{datetime.now().strftime('%H%M%S')}.png"
                    await self.browser.screenshot(path=screenshot_path)
                    log.info(f"  Error screenshot saved: {screenshot_path}")
            except:
                pass
            await self.close_modal()
            return ToolResult(
                success=False,
                error=f"Error getting category diagrams: {str(e)}",
                source=self.name
            )
    
    async def _click_category(self, category: str) -> bool:
        """Click on a category link on the wiring diagrams page.
        
        Categories are links in the tree structure. Clicking a category
        expands it to show diagram links below.
        Uses Playwright locator for reliable clicking.
        """
        log.info(f"_click_category() started: {category}")
        
        if not self.browser:
            log.error("  Browser not available")
            return False
        
        try:
            # Take screenshot before click attempt
            try:
                screenshot_path = f"/tmp/wiring_before_cat_click_{datetime.now().strftime('%H%M%S')}.png"
                await self.browser.screenshot(path=screenshot_path)
                log.info(f"  Pre-click screenshot: {screenshot_path}")
            except:
                pass
            
            # Log all visible links in the modal containing key category words
            debug_links = await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return ['NO MODAL FOUND'];
                    const links = modal.querySelectorAll('a');
                    const relevant = [];
                    const keywords = ['STARTING', 'CHARGING', 'AIR', 'HEADLIGHT', 'ENGINE', 'POWER'];
                    for (const link of links) {
                        const text = link.textContent?.trim().toUpperCase() || '';
                        if (text && keywords.some(k => text.includes(k))) {
                            relevant.push(text.substring(0, 40));
                        }
                    }
                    return relevant.slice(0, 15);
                }
            """)
            log.info(f"  Relevant links in modal: {debug_links}")
            
            # Use Playwright locator INSIDE THE MODAL - try exact text match first
            locator = self.browser.locator(f'.modalDialogView a:text-is("{category}")')
            count = await locator.count()
            log.info(f"  Exact match in modal '{category}': {count} links")
            
            if count > 0:
                await locator.first.click()
                log.info(f"  Clicked exact match: {category}")
                await random_delay(1000, 1500)
                return True
            
            # Try has-text (partial match) inside modal
            locator = self.browser.locator(f'.modalDialogView a:has-text("{category}")')
            count = await locator.count()
            log.info(f"  Partial match in modal '{category}': {count} links")
            
            if count > 0:
                await locator.first.click()
                log.info(f"  Clicked partial match: {category}")
                await random_delay(1000, 1500)
                return True
            
            # Try JavaScript query inside modal with case-insensitive match
            category_upper = category.upper()
            clicked = await self.browser.evaluate(f"""
                () => {{
                    const target = '{category_upper}';
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return null;
                    const links = modal.querySelectorAll('a');
                    for (const link of links) {{
                        const text = link.textContent?.trim().toUpperCase() || '';
                        if (text === target || text.includes(target)) {{
                            link.click();
                            return text;
                        }}
                    }}
                    return null;
                }}
            """)
            
            if clicked:
                log.info(f"  Clicked via JS: {clicked}")
                await random_delay(1000, 1500)
                return True
            
            log.error(f"  Category '{category}' not found on page")
            # Take screenshot showing current state
            try:
                screenshot_path = f"/tmp/wiring_cat_not_found_{datetime.now().strftime('%H%M%S')}.png"
                await self.browser.screenshot(path=screenshot_path)
                log.info(f"  Category not found screenshot: {screenshot_path}")
            except:
                pass
            return False
            
        except Exception as e:
            log.error(f"Exception in _click_category: {e}")
            log.error(traceback.format_exc())
            return False
    
    def _get_engine_variant(self, vehicle: Vehicle) -> str:
        """Get the engine variant string for tree navigation."""
        # Format: "1.4L VIN B" or similar
        engine = vehicle.engine or ""
        
        # Try to match common patterns
        # Examples: "1.4L", "2.0L Turbo", "5.0L V8"
        engine_parts = engine.split()
        if engine_parts:
            displacement = engine_parts[0]  # e.g., "1.4L"
            # Add VIN if not present
            if "VIN" not in engine.upper():
                return displacement
            return engine
        
        return engine
    
    async def _click_engine_variant(self, variant: str) -> bool:
        """Click on an engine variant in the expanded tree."""
        if not self.browser:
            return False
        
        variant_lower = variant.lower()
        
        return await self.browser.evaluate(f"""
            () => {{
                const target = '{variant_lower}';
                const modal = document.querySelector('.modalDialogView');
                if (!modal) return false;
                
                // Look for child nodes (level 1) that match
                const nodes = modal.querySelectorAll('li.node[data-level="1"]');
                for (const node of nodes) {{
                    const link = node.querySelector('a');
                    if (link) {{
                        const text = link.textContent?.trim().toLowerCase() || '';
                        // Match by displacement (e.g., "1.4l")
                        if (text.includes(target) || target.includes(text.split(' ')[0])) {{
                            const showIcon = node.querySelector('.showContentIcon');
                            if (showIcon) {{
                                showIcon.click();
                                return true;
                            }}
                            link.click();
                            return true;
                        }}
                    }}
                }}
                
                // Fallback: click first available
                const firstChild = modal.querySelector('li.node[data-level="1"]');
                if (firstChild) {{
                    const showIcon = firstChild.querySelector('.showContentIcon');
                    if (showIcon) {{
                        showIcon.click();
                        return true;
                    }}
                    const link = firstChild.querySelector('a');
                    if (link) {{
                        link.click();
                        return true;
                    }}
                }}
                
                return false;
            }}
        """)
    
    async def _get_available_variants(self) -> List[str]:
        """Get list of available engine variants."""
        if not self.browser:
            return []
        
        try:
            return await self.browser.evaluate("""
                () => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return [];
                    
                    const variants = [];
                    const nodes = modal.querySelectorAll('li.node[data-level="1"]');
                    for (const node of nodes) {
                        const link = node.querySelector('a');
                        if (link) {
                            const text = link.textContent?.trim();
                            if (text) variants.push(text);
                        }
                    }
                    return variants;
                }
            """)
        except:
            return []
    
    async def _wait_for_diagrams_load(self) -> None:
        """Wait for diagram content to load on the page.
        
        Note: Wiring diagrams open on a PAGE, not a modal.
        After clicking a category, diagrams load in the main content area.
        """
        log.info("_wait_for_diagrams_load() started")
        
        if not self.browser:
            log.error("  Browser not available")
            return
        
        try:
            # Wait for SVG objects or image holders to appear on the page
            # These are in the main content area, not a modal
            log.debug("  Waiting for diagram selectors...")
            await self.browser.wait_for_selector(
                ".imageHolder, "
                "object.clsArticleSvg, "
                ".svgImageHolder, "
                "svg.wiring-diagram",
                timeout=10000
            )
            log.info("  Diagram elements found")
            # Give extra time for SVGs to render
            await random_delay(1500, 2500)
        except Exception as e:
            log.warning(f"  Timeout waiting for diagrams: {e}, continuing anyway")
            await random_delay(1000, 1500)
    
    async def _capture_all_diagrams(self) -> List[Dict[str, str]]:
        """Capture all diagram images from the page by extracting SVG content directly.
        
        Extracts the actual SVG data rather than taking screenshots to avoid
        whitespace issues and get cleaner images.
        """
        log.info("_capture_all_diagrams() started")
        
        if not self.browser:
            log.error("  Browser not available")
            return []
        
        images = []
        
        try:
            # Limit to first 5 diagrams to avoid huge responses
            max_diagrams = 5
            
            # Extract SVG data directly from the page using JavaScript
            svg_data = await self.browser.evaluate("""
                () => {
                    const results = [];
                    
                    // Find all SVG objects (wiring diagrams use <object> tags)
                    const svgObjects = document.querySelectorAll('object.clsArticleSvg');
                    
                    for (const obj of svgObjects) {
                        try {
                            // Get the caption from parent imageHolder
                            const holder = obj.closest('.imageHolder');
                            const captionEl = holder?.querySelector('.imageCaption');
                            const caption = captionEl?.textContent?.trim() || '';
                            
                            // Get the SVG content from the object's contentDocument
                            const svgDoc = obj.contentDocument;
                            if (svgDoc) {
                                const svgEl = svgDoc.querySelector('svg');
                                if (svgEl) {
                                    // Clone and serialize the SVG
                                    const clone = svgEl.cloneNode(true);
                                    
                                    // Ensure viewBox is set for proper sizing
                                    if (!clone.getAttribute('viewBox')) {
                                        const bbox = svgEl.getBBox?.();
                                        if (bbox) {
                                            clone.setAttribute('viewBox', `${bbox.x} ${bbox.y} ${bbox.width} ${bbox.height}`);
                                        }
                                    }
                                    
                                    // Add white background
                                    const rect = svgDoc.createElementNS('http://www.w3.org/2000/svg', 'rect');
                                    rect.setAttribute('width', '100%');
                                    rect.setAttribute('height', '100%');
                                    rect.setAttribute('fill', 'white');
                                    clone.insertBefore(rect, clone.firstChild);
                                    
                                    const serializer = new XMLSerializer();
                                    const svgString = serializer.serializeToString(clone);
                                    
                                    results.push({
                                        caption: caption,
                                        svg: svgString,
                                        type: 'svg'
                                    });
                                }
                            }
                            
                            // Also try to get the data URL if SVG content isn't accessible
                            if (results.length === 0 || !results[results.length - 1].svg) {
                                const dataUrl = obj.getAttribute('data');
                                if (dataUrl) {
                                    results.push({
                                        caption: caption,
                                        url: dataUrl,
                                        type: 'url'
                                    });
                                }
                            }
                        } catch (e) {
                            console.error('Error extracting SVG:', e);
                        }
                    }
                    
                    // If no SVG objects found, try img elements
                    if (results.length === 0) {
                        const images = document.querySelectorAll('.imageHolder img');
                        for (const img of images) {
                            const holder = img.closest('.imageHolder');
                            const captionEl = holder?.querySelector('.imageCaption');
                            const caption = captionEl?.textContent?.trim() || '';
                            
                            if (img.src) {
                                results.push({
                                    caption: caption,
                                    url: img.src,
                                    type: 'img'
                                });
                            }
                        }
                    }
                    
                    return results;
                }
            """)
            
            log.info(f"  Extracted {len(svg_data)} diagram data items")
            
            # Process extracted SVG data
            for i, item in enumerate(svg_data[:max_diagrams]):
                try:
                    caption = item.get('caption') or f"Wiring Diagram {i+1}"
                    
                    if item.get('type') == 'svg' and item.get('svg'):
                        # Convert SVG to PNG using canvas
                        svg_string = item['svg']
                        
                        # Use browser to convert SVG to PNG at larger size
                        png_base64 = await self.browser.evaluate("""
                            async (svgString) => {
                                return new Promise((resolve, reject) => {
                                    const canvas = document.createElement('canvas');
                                    const ctx = canvas.getContext('2d');
                                    const img = new Image();
                                    
                                    img.onload = () => {
                                        // Scale up for better resolution - minimum 1200px wide
                                        const minWidth = 1200;
                                        const scale = img.width < minWidth ? minWidth / img.width : 1;
                                        canvas.width = Math.max(img.width * scale, minWidth);
                                        canvas.height = img.height * scale || 900;
                                        
                                        // Fill white background
                                        ctx.fillStyle = 'white';
                                        ctx.fillRect(0, 0, canvas.width, canvas.height);
                                        
                                        // Draw the image scaled up
                                        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
                                        
                                        // Get as PNG base64
                                        const dataUrl = canvas.toDataURL('image/png');
                                        resolve(dataUrl.split(',')[1]); // Remove data:image/png;base64, prefix
                                    };
                                    
                                    img.onerror = (e) => {
                                        reject('Failed to load SVG: ' + e);
                                    };
                                    
                                    // Convert SVG to data URL
                                    const blob = new Blob([svgString], {type: 'image/svg+xml'});
                                    img.src = URL.createObjectURL(blob);
                                    
                                    // Timeout fallback
                                    setTimeout(() => reject('Timeout converting SVG'), 5000);
                                });
                            }
                        """, svg_string)
                        
                        if png_base64:
                            images.append({
                                "name": caption,
                                "base64": png_base64,
                                "mime_type": "image/png"
                            })
                            log.info(f"  Converted SVG diagram {i+1}: {caption[:50]} ({len(png_base64)} bytes)")
                        
                except Exception as e:
                    log.error(f"  Error processing diagram {i}: {e}")
                    log.error(traceback.format_exc())
            
            # Fallback: If SVG extraction failed, use element screenshots
            if not images:
                log.info("  SVG extraction failed, falling back to element screenshots...")
                holders = await self.browser.query_selector_all(".imageHolder.svgImageHolder")
                log.info(f"  Found {len(holders)} diagram holders")
                
                for i, holder in enumerate(holders[:max_diagrams]):
                    try:
                        caption_elem = await holder.query_selector(".imageCaption")
                        caption = ""
                        if caption_elem:
                            caption = await caption_elem.inner_text()
                            caption = caption.strip()
                        
                        # Find the SVG object inside and screenshot just that
                        svg_obj = await holder.query_selector("object.clsArticleSvg")
                        if svg_obj:
                            await svg_obj.scroll_into_view_if_needed()
                            await random_delay(200, 400)
                            screenshot_bytes = await svg_obj.screenshot()
                        else:
                            await holder.scroll_into_view_if_needed()
                            await random_delay(200, 400)
                            screenshot_bytes = await holder.screenshot()
                        
                        b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                        images.append({
                            "name": caption or f"Wiring Diagram {i+1}",
                            "base64": b64_data,
                            "mime_type": "image/png"
                        })
                        log.info(f"  Screenshot diagram {i+1}: {caption[:50] if caption else 'Unnamed'}")
                        
                    except Exception as e:
                        log.error(f"  Error capturing diagram {i}: {e}")
            
            log.info(f"  Total images captured: {len(images)}")
            return images
            
        except Exception as e:
            log.error(f"Exception in _capture_all_diagrams: {e}")
            log.error(traceback.format_exc())
            return images
    
    async def _get_diagram_info(self) -> List[Dict[str, str]]:
        """Get information about available diagrams on the page."""
        if not self.browser:
            return []
        
        try:
            return await self.browser.evaluate("""
                () => {
                    // Look in main page content, not modal
                    const diagrams = [];
                    const holders = document.querySelectorAll('.imageHolder');
                    
                    for (const holder of holders) {
                        const caption = holder.querySelector('.imageCaption');
                        const components = holder.getAttribute('components') || '';
                        
                        if (caption) {
                            diagrams.push({
                                title: caption.textContent?.trim() || 'Unknown',
                                components: components.split('|').filter(c => c).slice(0, 10)
                            });
                        }
                    }
                    
                    return diagrams;
                }
            """)
        except:
            return []
    
    async def _search_tree_for_term(self, search_term: str, vehicle: Vehicle) -> ToolResult:
        """Search the tree directly for a term when no semantic mapping exists."""
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser not available",
                source=self.name
            )
        
        try:
            search_lower = search_term.lower()
            
            # Search through all categories for matching components
            result = await self.browser.evaluate(f"""
                () => {{
                    const searchTerm = '{search_lower}';
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return {{ found: false }};
                    
                    // Check each node's components attribute
                    const holders = modal.querySelectorAll('.imageHolder[components]');
                    for (const holder of holders) {{
                        const components = holder.getAttribute('components')?.toLowerCase() || '';
                        if (components.includes(searchTerm)) {{
                            // Found a match - get the parent category
                            const parentNode = holder.closest('li.node');
                            if (parentNode) {{
                                const link = parentNode.querySelector('a');
                                return {{
                                    found: true,
                                    category: link?.textContent?.trim() || 'Unknown',
                                    matchedIn: 'components'
                                }};
                            }}
                        }}
                    }}
                    
                    // Check node text
                    const nodes = modal.querySelectorAll('li.node');
                    for (const node of nodes) {{
                        const text = node.textContent?.toLowerCase() || '';
                        if (text.includes(searchTerm)) {{
                            const link = node.querySelector('a');
                            return {{
                                found: true,
                                category: link?.textContent?.trim() || 'Unknown',
                                matchedIn: 'category_name'
                            }};
                        }}
                    }}
                    
                    return {{ found: false }};
                }}
            """)
            
            if result.get("found"):
                category = result.get("category")
                log.info(f"Found '{search_term}' in category: {category}")
                return await self._get_category_diagrams(category, vehicle, search_term)
            
            # No match found - return available categories
            categories = await self._list_categories()
            await self.close_modal()
            
            return ToolResult(
                success=False,
                error=f"Could not find diagrams for '{search_term}'",
                source=self.name,
                data={
                    "search_term": search_term,
                    "available_categories": categories,
                    "hint": "Try searching for a specific category or component"
                }
            )
            
        except Exception as e:
            await self.close_modal()
            return ToolResult(
                success=False,
                error=f"Error searching tree: {str(e)}",
                source=self.name
            )
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        if not data:
            return "No wiring diagram data found."
        
        lines = ["**Wiring Diagrams:**\n"]
        
        if "message" in data:
            lines.append(f"{data['message']}\n")
        
        if "category" in data:
            lines.append(f"**Category:** {data['category']}")
        
        if "search_term" in data and data["search_term"]:
            lines.append(f"**Search:** {data['search_term']}")
        
        if "diagram_count" in data:
            lines.append(f"**Diagrams retrieved:** {data['diagram_count']}")
        
        if "diagrams" in data:
            lines.append("\n**Diagram figures:**")
            for diag in data["diagrams"][:10]:
                lines.append(f"  • {diag.get('title', 'Unknown')}")
                if diag.get("components"):
                    comps = ", ".join(diag["components"][:5])
                    lines.append(f"    Components: {comps}")
        
        if "categories" in data:
            lines.append("\n**Available categories:**")
            for cat in data["categories"]:
                type_marker = "📁" if cat.get("type") == "branch" else "📄"
                lines.append(f"  {type_marker} {cat['name']}")
        
        if result.images:
            lines.append(f"\n*{len(result.images)} diagram image(s) attached for analysis*")
        
        return "\n".join(lines)
