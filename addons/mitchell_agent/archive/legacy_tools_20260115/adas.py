"""
ADAS Calibration Tool - Retrieves ADAS calibration requirements.

Updated 2026-01-09: Added drill-down support for component details.
Clicking a component link goes to OneView Cards page, then click a card
(Specifications, Remove & Replace, etc.) to get detailed info.
"""
import asyncio
import logging
import random
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Set up logging
logger = logging.getLogger("adas_tool")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler("/tmp/adas_tool.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)


# Common ADAS components
ADAS_COMPONENTS = {
    "camera": ["front camera", "rear camera", "windshield camera", "camera calibration"],
    "radar": ["front radar", "radar sensor", "adaptive cruise", "collision warning"],
    "sensor": ["blind spot", "lane departure", "parking sensor", "ultrasonic"],
    "lidar": ["lidar", "laser sensor"],
    "all": []  # Returns everything
}

# Mapping from user intent to card class names
INFO_TYPE_MAPPING = {
    # Specifications
    "specs": "cardSpecifications",
    "specifications": "cardSpecifications",
    "torque": "cardSpecifications",
    "spec": "cardSpecifications",
    
    # Remove & Replace
    "remove": "cardRemoveReplace",
    "replace": "cardRemoveReplace",
    "r&r": "cardRemoveReplace",
    "removal": "cardRemoveReplace",
    "replacement": "cardRemoveReplace",
    "how to": "cardRemoveReplace",
    "procedure": "cardRemoveReplace",
    
    # Wiring Diagrams
    "wiring": "cardWiringDiagrams",
    "diagram": "cardWiringDiagrams",
    "circuit": "cardWiringDiagrams",
    "electrical": "cardWiringDiagrams",
    
    # Component Location
    "location": "cardComponentLocation",
    "where": "cardComponentLocation",
    "locate": "cardComponentLocation",
    
    # Component Connector
    "connector": "cardComponentConnector",
    "pinout": "cardComponentConnector",
    "pin-out": "cardComponentConnector",
    "pins": "cardComponentConnector",
    
    # Technical Bulletins
    "tsb": "cardTechnicalBulletins",
    "bulletin": "cardTechnicalBulletins",
    "recall": "cardTechnicalBulletins",
    "campaign": "cardTechnicalBulletins",
    
    # Component Operation
    "operation": "cardComponentOperation",
    "description": "cardComponentOperation",
    "how it works": "cardComponentOperation",
    
    # OEM Testing
    "testing": "cardOEMTesting",
    "test": "cardOEMTesting",
    "diagnostic": "cardOEMTesting",
    
    # After Repair Info
    "after repair": "cardAfterRepairInfo",
    "validation": "cardAfterRepairInfo",
    "verify": "cardAfterRepairInfo",
}


class ADASCalibrationTool(MitchellTool):
    """
    Retrieves ADAS (Advanced Driver Assistance Systems) calibration requirements.
    
    Access: Quick Access Panel > Driver Assist ADAS (#adasAccess)
    
    Returns calibration requirements including:
    - Component: Camera, radar, sensor type
    - Jobs Requiring Calibration: What triggers calibration need
    - Special Tools: Required equipment
    - Scan Tool: Scan tool requirements
    
    Can also drill down into specific components to get:
    - Specifications (torque specs, etc.)
    - Remove & Replace procedures
    - Wiring diagrams
    - Component location
    - And more via OneView Cards
    """
    
    name = "get_adas_calibration"
    description = "Get ADAS calibration requirements for vehicle components"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        component: Optional[str] = None,
        query: Optional[str] = None,
        info_type: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get ADAS calibration information.
        
        Args:
            vehicle: Vehicle specification
            component: Component to get calibration info for (e.g., "camera", "radar", "anti-lock brake")
            query: Alternative query string
            info_type: Type of info to drill down to (e.g., "specs", "remove", "wiring", "location")
                      If provided with component, will click into that component and get detailed info.
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with ADAS calibration data or detailed component info
        """
        # Enable debug screenshots if requested
        if kwargs.get('debug_screenshots'):
            self.debug_screenshots = True
            self._screenshot_counter = 0
        
        logger.info(f"ADAS tool called: component={component}, info_type={info_type}, query={query}")
        
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
                print(f"[ADASTool] Skipping vehicle selection (already selected)")
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
            
            # Get selectors from config
            adas_sel = self.get_selector("quick_access.adas") or "#adasAccess"
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            
            # Quick Access panel is on the HOME view, not inside any module
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
            
            # Step 3: Before clicking ADAS
            await self.save_debug_screenshot("03_before_adas_click")
            
            # Click ADAS quick access (use #quickLinkRegion prefix to avoid duplicate ID issue)
            selector = adas_sel
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3500)
            
            # Step 4: ADAS modal open
            await self.save_debug_screenshot("04_adas_modal_open")
            
            # Extract ADAS calibration data
            adas_data = await self._extract_adas_data()
            
            # Step 5: After data extraction
            await self.save_debug_screenshot("05_data_extracted")
            
            # Capture any images from the ADAS modal before closing
            images = await self.extract_images_from_modal()
            if images:
                logger.info(f"Captured {len(images)} images from ADAS modal")
            
            if not adas_data:
                await self.close_modal()
                return ToolResult(
                    success=False,
                    error="Could not extract ADAS calibration data",
                    source=self.name,
                    images=images if images else None
                )
            
            # Filter by component if specified
            search_term = component or query
            filtered_data = adas_data
            if search_term:
                search_lower = search_term.lower()
                
                # Check if it matches a known component category
                matched_keywords = []
                for comp_type, keywords in ADAS_COMPONENTS.items():
                    if search_lower in comp_type or any(kw in search_lower for kw in keywords):
                        matched_keywords.extend(keywords)
                        matched_keywords.append(comp_type)
                
                if matched_keywords:
                    filtered_data = [
                        item for item in adas_data
                        if any(kw in item.get("component", "").lower() for kw in matched_keywords)
                        or search_lower in item.get("component", "").lower()
                    ]
                else:
                    filtered_data = [
                        item for item in adas_data
                        if search_lower in item.get("component", "").lower()
                        or search_lower in item.get("jobs", "").lower()
                    ]
            
            # If info_type specified and we have a component match, drill down
            if info_type and filtered_data and search_term:
                logger.info(f"Drilling down: info_type={info_type}, component matches={len(filtered_data)}")
                
                # Find the card class for this info_type
                card_class = self._get_card_class(info_type)
                if card_class:
                    # Click the first matching component in the table
                    component_name = filtered_data[0].get("component", "")
                    logger.info(f"Clicking component: {component_name}")
                    
                    # Click the component link to go to OneView Cards
                    drill_result = await self._drill_into_component(component_name, card_class)
                    
                    if drill_result:
                        # Close modal if still open
                        await self.close_modal()
                        
                        return ToolResult(
                            success=True,
                            data=drill_result,
                            source=self.name,
                            images=drill_result.get("images", []) or images,
                            auto_selected_options=self.get_auto_selected_options() or None
                        )
                    else:
                        logger.warning("Drill-down failed, returning table data")
            
            # Close the modal
            await self.close_modal()
            
            # Step 6: Final state
            await self.save_debug_screenshot("06_final_state")
            
            return ToolResult(
                success=True,
                data=filtered_data,
                source=self.name,
                images=images if images else None,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving ADAS calibration data: {str(e)}",
                source=self.name
            )
    
    async def _extract_adas_data(self) -> List[Dict[str, str]]:
        """Extract ADAS calibration data from the modal table."""
        if not self.browser:
            return []
        
        try:
            # First, capture page state for debugging
            debug_info = await self.browser.evaluate("""
                (() => {
                    const info = {
                        url: window.location.href,
                        hasModal: !!document.querySelector('.modalDialogView'),
                        modalHTML: document.querySelector('.modalDialogView')?.innerHTML?.substring(0, 2000) || 'NO MODAL',
                        mainContent: document.querySelector('#mainContent, .mainContent, [class*="content"]')?.innerHTML?.substring(0, 2000) || 'NO MAIN',
                        tables: document.querySelectorAll('table').length,
                        modalTables: document.querySelectorAll('.modalDialogView table').length,
                        treeNodes: document.querySelectorAll('li.usercontrol.node').length,
                        iframes: document.querySelectorAll('iframe').length
                    };
                    return info;
                })()
            """)
            print(f"[ADAS DEBUG] Page state: modal={debug_info.get('hasModal')}, tables={debug_info.get('tables')}, modalTables={debug_info.get('modalTables')}, iframes={debug_info.get('iframes')}")
            if debug_info.get('modalTables', 0) == 0 and debug_info.get('treeNodes', 0) == 0:
                print(f"[ADAS DEBUG] Modal HTML preview: {debug_info.get('modalHTML', 'N/A')[:500]}")
            
            result = await self.browser.evaluate("""
                (() => {
                    const data = [];
                    
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return data;
                    
                    // ADAS data is typically in a table format
                    // Columns: Component | Jobs Requiring Calibration | Special Tools | Scan Tool
                    const tables = modal.querySelectorAll('table');
                    
                    for (const table of tables) {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        
                        // Skip header row
                        for (let i = 1; i < rows.length; i++) {
                            const cells = Array.from(rows[i].querySelectorAll('td'));
                            
                            if (cells.length >= 4) {
                                data.push({
                                    component: cells[0]?.textContent?.trim() || '',
                                    jobs: cells[1]?.textContent?.trim() || '',
                                    special_tools: cells[2]?.textContent?.trim() || '',
                                    scan_tool: cells[3]?.textContent?.trim() || ''
                                });
                            } else if (cells.length >= 2) {
                                // Some tables may have fewer columns
                                data.push({
                                    component: cells[0]?.textContent?.trim() || '',
                                    jobs: cells[1]?.textContent?.trim() || '',
                                    special_tools: cells[2]?.textContent?.trim() || '',
                                    scan_tool: ''
                                });
                            }
                        }
                    }
                    
                    // Also check for tree structure
                    if (data.length === 0) {
                        const nodes = modal.querySelectorAll('li.usercontrol.node');
                        for (const node of nodes) {
                            const text = node.querySelector('.nodeText, .text, span')?.textContent?.trim();
                            if (text) {
                                data.push({
                                    component: text,
                                    jobs: '',
                                    special_tools: '',
                                    scan_tool: ''
                                });
                            }
                        }
                    }
                    
                    return data;
                })()
            """)
            return result if isinstance(result, list) else []
        except Exception as e:
            logger.error(f"Error extracting ADAS data: {e}")
            return []
    
    def _get_card_class(self, info_type: str) -> Optional[str]:
        """Get the card CSS class for an info_type."""
        info_lower = info_type.lower()
        
        # Direct match
        if info_lower in INFO_TYPE_MAPPING:
            return INFO_TYPE_MAPPING[info_lower]
        
        # Partial match
        for key, card_class in INFO_TYPE_MAPPING.items():
            if key in info_lower or info_lower in key:
                return card_class
        
        return None
    
    async def _drill_into_component(self, component_name: str, card_class: str) -> Optional[Dict[str, Any]]:
        """
        Click a component in the ADAS table, then click a specific card to get details.
        
        Args:
            component_name: Name of the component to click
            card_class: CSS class of the card to click (e.g., "cardSpecifications")
            
        Returns:
            Dict with extracted content, or None on failure
        """
        if not self.browser:
            return None
        
        try:
            logger.info(f"Drilling into component: {component_name}, card: {card_class}")
            
            # Click the component link in the modal table
            # Links use data-bindto="name" attribute
            click_result = await self.browser.evaluate(f"""
                (() => {{
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return {{ success: false, error: 'No modal' }};
                    
                    const links = modal.querySelectorAll('table td a');
                    for (const link of links) {{
                        if (link.textContent?.trim().toLowerCase() === '{component_name.lower()}') {{
                            link.click();
                            return {{ success: true, clicked: link.textContent?.trim() }};
                        }}
                    }}
                    
                    // Partial match
                    for (const link of links) {{
                        if (link.textContent?.trim().toLowerCase().includes('{component_name.lower().split()[0]}')) {{
                            link.click();
                            return {{ success: true, clicked: link.textContent?.trim() }};
                        }}
                    }}
                    
                    return {{ success: false, error: 'Component not found' }};
                }})()
            """)
            
            logger.info(f"Component click result: {click_result}")
            
            if not click_result.get("success"):
                return None
            
            # Wait for navigation to OneView Cards page
            await random_delay(2000, 3000)
            await self.save_debug_screenshot("07_oneview_cards")
            
            # Verify we're on the cards page (modal should be closed)
            on_cards_page = await self.browser.evaluate("""
                (() => {
                    const cards = document.querySelectorAll('.card');
                    const modal = document.querySelector('.modalDialogView');
                    return {
                        cards_count: cards.length,
                        modal_visible: modal && modal.offsetParent !== null,
                        url: window.location.href
                    };
                })()
            """)
            
            logger.info(f"Cards page check: {on_cards_page}")
            
            if on_cards_page.get("cards_count", 0) < 3:
                logger.warning("Not enough cards found, may not be on OneView page")
                return None
            
            # Click the specific card
            card_selector = f".card.{card_class}"
            logger.info(f"Clicking card: {card_selector}")
            
            try:
                await self.browser.click(card_selector, timeout=5000)
            except Exception as e:
                logger.error(f"Failed to click card {card_selector}: {e}")
                return None
            
            await random_delay(2000, 3000)
            await self.save_debug_screenshot("08_card_content")
            
            # Extract content from the result page
            content = await self._extract_card_content()
            
            return content
            
        except Exception as e:
            logger.error(f"Error in drill-down: {e}")
            return None
    
    async def _extract_card_content(self) -> Dict[str, Any]:
        """Extract content from the page after clicking a card."""
        if not self.browser:
            return {}
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const content = {
                        title: '',
                        sections: [],
                        tables: [],
                        text_content: ''
                    };
                    
                    // Helper to clean text (remove JS artifacts)
                    function cleanText(text) {
                        if (!text) return '';
                        // Remove script content patterns
                        text = text.replace(/\\$\\(document\\)[\\s\\S]*?\\}\\);/g, '');
                        text = text.replace(/\\$\\([^)]+\\)[\\s\\S]*?;/g, '');
                        text = text.replace(/function\\s*\\([^)]*\\)\\s*\\{[\\s\\S]*?\\}/g, '');
                        text = text.replace(/window\\.[A-Za-z]+/g, '');
                        text = text.replace(/setTimeout\\s*\\([\\s\\S]*?\\);/g, '');
                        text = text.replace(/if\\s*\\([^)]+\\)\\s*\\{[^}]*\\}/g, '');
                        // Remove common JS patterns
                        text = text.replace(/var\\s+[a-zA-Z_$][a-zA-Z0-9_$]*\\s*=/g, '');
                        text = text.replace(/\\._is[A-Z][a-zA-Z]+\\(/g, '');
                        text = text.replace(/opener\\.[A-Za-z]+/g, '');
                        // Clean up whitespace
                        text = text.replace(/\\s+/g, ' ').trim();
                        return text;
                    }
                    
                    // Helper to check if text looks like JS code
                    function isJavaScript(text) {
                        if (!text) return false;
                        const jsPatterns = [
                            /\\$\\(document\\)/,
                            /\\$\\(function/,
                            /setTimeout/,
                            /window\\.PD/,
                            /opener\\./,
                            /function\\s*\\(/,
                            /\\.ready\\s*\\(/,
                            /GraphicsManagerModule/
                        ];
                        return jsPatterns.some(p => p.test(text));
                    }
                    
                    // Get page title/header
                    const header = document.querySelector('.modalDialogView h1, .modalDialogView .header, #pageTitle, .dialogHeader');
                    if (header && !isJavaScript(header.textContent)) {
                        content.title = cleanText(header.textContent);
                    }
                    
                    // Check if in a modal or main page
                    const container = document.querySelector('.modalDialogView') || document.querySelector('#mainContent, .content');
                    if (!container) return content;
                    
                    // Extract tables (most important for specs)
                    const seenTables = new Set();
                    container.querySelectorAll('table').forEach(table => {
                        const tableData = { headers: [], rows: [] };
                        
                        // Get headers from thead or first row with th
                        const headerRow = table.querySelector('thead tr, tr:has(th)');
                        if (headerRow) {
                            headerRow.querySelectorAll('th').forEach(th => {
                                const text = cleanText(th.textContent);
                                if (text && !isJavaScript(text)) {
                                    tableData.headers.push(text);
                                }
                            });
                        }
                        
                        // Get data rows from tbody or all tr with td
                        const rows = table.querySelectorAll('tbody tr, tr:has(td)');
                        rows.forEach((tr) => {
                            const row = [];
                            tr.querySelectorAll('td').forEach(cell => {
                                const text = cleanText(cell.textContent);
                                if (!isJavaScript(text)) {
                                    row.push(text);
                                }
                            });
                            // Only add non-empty rows with actual data
                            if (row.length > 0 && row.some(c => c.length > 0)) {
                                // Deduplicate by row signature
                                const sig = row.join('|');
                                if (!seenTables.has(sig)) {
                                    seenTables.add(sig);
                                    tableData.rows.push(row);
                                }
                            }
                        });
                        
                        if (tableData.rows.length > 0) {
                            content.tables.push(tableData);
                        }
                    });
                    
                    // Extract sections with headers (but skip script-like content)
                    const seenSections = new Set();
                    container.querySelectorAll('h1, h2, h3, h4, .sectionHeader').forEach(h => {
                        // Skip if it's inside a script or has JS content
                        if (h.closest('script') || h.closest('noscript')) return;
                        
                        const titleText = cleanText(h.textContent);
                        if (!titleText || isJavaScript(titleText) || seenSections.has(titleText)) return;
                        
                        seenSections.add(titleText);
                        
                        const section = {
                            title: titleText,
                            content: ''
                        };
                        
                        // Get following sibling content (skip scripts)
                        let sibling = h.nextElementSibling;
                        while (sibling && !sibling.matches('h1, h2, h3, h4, .sectionHeader')) {
                            if (sibling.tagName !== 'SCRIPT' && sibling.tagName !== 'STYLE') {
                                const sibText = cleanText(sibling.textContent);
                                if (sibText && !isJavaScript(sibText)) {
                                    section.content += sibText + ' ';
                                }
                            }
                            sibling = sibling.nextElementSibling;
                        }
                        
                        section.content = section.content.trim();
                        if (section.title) content.sections.push(section);
                    });
                    
                    // Get full text content only if no structured data, and clean it
                    if (content.tables.length === 0 && content.sections.length === 0) {
                        // Clone container and remove script/style elements
                        const clone = container.cloneNode(true);
                        clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
                        const rawText = clone.textContent || '';
                        content.text_content = cleanText(rawText).substring(0, 5000);
                    }
                    
                    return content;
                })()
            """)
            
            # Also capture images
            images = await self.extract_images_from_modal()
            if images:
                result["images"] = images
            
            logger.info(f"Extracted content: title={result.get('title')}, tables={len(result.get('tables', []))}, sections={len(result.get('sections', []))}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting card content: {e}")
            return {}
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        
        if not data:
            return "No ADAS calibration information found for the specified criteria."
        
        lines = ["**ADAS Calibration Requirements:**\n"]
        
        for item in data:
            lines.append(f"**{item.get('component', 'Component')}**")
            
            if item.get('jobs'):
                lines.append(f"  Jobs Requiring Calibration:")
                # Split jobs by common delimiters
                jobs = item['jobs'].replace(';', '\n').replace(',', '\n')
                for job in jobs.split('\n'):
                    job = job.strip()
                    if job:
                        lines.append(f"    - {job}")
            
            if item.get('special_tools'):
                lines.append(f"  Special Tools: {item['special_tools']}")
            
            if item.get('scan_tool'):
                lines.append(f"  Scan Tool: {item['scan_tool']}")
            
            lines.append("")
        
        return "\n".join(lines)
