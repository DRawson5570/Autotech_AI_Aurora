"""
DTC Info Tool - Retrieves diagnostic trouble code information.

Updated 2026-01-09: Fixed category navigation and table extraction.
DTC Index shows system categories as links. Click a category to see DTC table.
"""
import asyncio
import logging
import random
import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Set up logging
logger = logging.getLogger("dtc_tool")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler("/tmp/dtc_tool.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)


@dataclass
class DTCInfo:
    """Diagnostic Trouble Code information."""
    code: str
    description: str
    warning_type: str
    action: str
    system: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "code": self.code,
            "description": self.description,
            "warning_type": self.warning_type,
            "action": self.action,
            "system": self.system
        }


# Map DTC prefixes to likely system categories
DTC_CATEGORY_HINTS = {
    "C0": ["ANTILOCK", "BRAKE", "ABS", "TRACTION", "STABILITY"],
    "C1": ["ANTILOCK", "BRAKE", "ABS", "TRACTION", "STABILITY"],
    "B0": ["BODY", "INSTRUMENT", "AIRBAG", "SRS"],
    "B1": ["BODY", "INSTRUMENT", "AIRBAG", "SRS"],
    "B2": ["BODY", "INSTRUMENT", "CELLULAR", "ENTERTAINMENT"],
    "P0": ["ENGINE", "POWERTRAIN", "FUEL", "EMISSION"],
    "P1": ["ENGINE", "POWERTRAIN", "FUEL"],
    "P2": ["ENGINE", "POWERTRAIN", "FUEL"],
    "U0": ["NETWORK", "COMMUNICATION", "DATA"],
    "U1": ["NETWORK", "COMMUNICATION", "DATA"],
}


class DTCInfoTool(MitchellTool):
    """
    Retrieves DTC (Diagnostic Trouble Code) information.
    
    Access: Quick Access Panel > DTC Index (#dtcIndexAccess)
    
    Navigates the DTC tree by system and engine type to find
    specific code information including description and recommended action.
    """
    
    name = "get_dtc_info"
    description = "Get diagnostic trouble code (DTC) information and recommended actions"
    tier = 1
    
    # Map DTC prefixes to systems
    DTC_SYSTEM_MAP = {
        "P0": "Powertrain - Generic",
        "P1": "Powertrain - Manufacturer",
        "P2": "Powertrain - Generic",
        "P3": "Powertrain - Generic/Manufacturer",
        "B0": "Body - Generic",
        "B1": "Body - Manufacturer",
        "B2": "Body - Manufacturer",
        "B3": "Body - Generic",
        "C0": "Chassis - Generic",
        "C1": "Chassis - Manufacturer",
        "C2": "Chassis - Manufacturer",
        "C3": "Chassis - Generic",
        "U0": "Network - Generic",
        "U1": "Network - Manufacturer",
        "U2": "Network - Manufacturer",
        "U3": "Network - Generic"
    }
    
    async def execute(
        self,
        vehicle: Vehicle,
        dtc_code: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get DTC information for the vehicle.
        
        Args:
            vehicle: Vehicle specification
            dtc_code: Specific DTC code (e.g., "P0300")
            query: Alternative query string containing DTC
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with DTC information
        """
        # Enable debug screenshots if requested
        if kwargs.get('debug_screenshots'):
            self.debug_screenshots = True
            self._screenshot_counter = 0
        
        # Extract DTC from query if not provided directly
        if not dtc_code and query:
            dtc_code = self._extract_dtc_from_query(query)
        
        if not dtc_code:
            return ToolResult(
                success=False,
                error="No DTC code provided. Please specify a code like P0300.",
                source=self.name
            )
        
        # Normalize DTC code
        dtc_code = dtc_code.upper().strip()
        
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
                print(f"[DTCTool] Skipping vehicle selection (already selected)")
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
            dtc_sel = self.get_selector("quick_access.dtc_index") or "#dtcIndexAccess"
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
            
            # Step 3: Before clicking DTC index
            await self.save_debug_screenshot("03_before_dtc_click")
            
            # Click DTC Index quick access (use #quickLinkRegion prefix to avoid duplicate ID issue)
            selector = dtc_sel
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3500)
            
            # Step 4: DTC modal open
            await self.save_debug_screenshot("04_dtc_modal_open")
            
            # Navigate to engine-specific DTCs and search for the code
            dtc_data = await self._find_dtc_in_tree(dtc_code, vehicle.engine)
            
            # Step 5: After DTC search
            await self.save_debug_screenshot("05_after_dtc_search")
            
            if not dtc_data:
                # Try searching all DTC tables
                dtc_data = await self._search_all_dtc_tables(dtc_code)
                await self.save_debug_screenshot("05b_after_dtc_search_all")
            
            # Capture any images from the modal before closing
            images = await self.extract_images_from_modal()
            if images:
                print(f"[DTCTool] Captured {len(images)} images from modal")
            
            # Close the modal
            await self.close_modal()
            
            # Step 6: Final state
            await self.save_debug_screenshot("06_final_state")
            
            if dtc_data:
                return ToolResult(
                    success=True,
                    data=dtc_data,
                    source=self.name,
                    images=images if images else None,
                    auto_selected_options=self.get_auto_selected_options() or None
                )
            else:
                # Return with system info even if specific DTC not found
                system = self._get_dtc_system(dtc_code)
                return ToolResult(
                    success=True,
                    data={
                        "code": dtc_code,
                        "system": system,
                        "description": f"DTC {dtc_code} - {system}",
                        "warning_type": "Unknown",
                        "action": f"Use 1Search for detailed diagnostics on {dtc_code}",
                        "note": "Specific DTC data not found in index. Try search_mitchell for more info."
                    },
                    source=self.name,
                    images=images if images else None,
                    auto_selected_options=self.get_auto_selected_options() or None
                )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving DTC info: {str(e)}",
                source=self.name
            )
    
    def _extract_dtc_from_query(self, query: str) -> Optional[str]:
        """Extract DTC code from a query string."""
        # Pattern matches P0300, B1234, C0123, U0100, etc.
        pattern = r'\b([PBCU][0-3][0-9]{3})\b'
        match = re.search(pattern, query.upper())
        return match.group(1) if match else None
    
    def _get_dtc_system(self, dtc_code: str) -> str:
        """Get the system category for a DTC code."""
        prefix = dtc_code[:2].upper()
        return self.DTC_SYSTEM_MAP.get(prefix, "Unknown System")
    
    async def _find_dtc_in_tree(
        self,
        dtc_code: str,
        engine: str
    ) -> Optional[Dict[str, str]]:
        """Search for DTC code - click all showContentIcons to expand, then search."""
        if not self.browser:
            return None
        
        try:
            logger.info(f"Finding DTC {dtc_code}")
            
            # Click all .showContentIcon elements to expand all categories
            expand_result = await self.browser.evaluate("""
                (() => {
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return { modal: false };
                    
                    const showIcons = modal.querySelectorAll('.showContentIcon');
                    showIcons.forEach(icon => icon.click());
                    
                    return {
                        modal: true,
                        clicked: showIcons.length
                    };
                })()
            """)
            
            logger.info(f"Clicked {expand_result.get('clicked', 0)} showContentIcons")
            
            # Wait for content to expand
            await random_delay(1500, 2000)
            
            # Now search all tables
            return await self._find_dtc_in_table(dtc_code)
            
        except Exception as e:
            logger.error(f"Error finding DTC: {e}")
            return None
    
    async def _search_all_dtc_tables(self, dtc_code: str) -> Optional[Dict[str, str]]:
        """Search all tables for the DTC code - same as _find_dtc_in_table since categories are expanded."""
        return await self._find_dtc_in_table(dtc_code)
    
    async def _find_dtc_in_table(self, dtc_code: str) -> Optional[Dict[str, str]]:
        """Find a DTC in the currently displayed tables."""
        if not self.browser:
            return None
        
        try:
            # First, debug what we can see
            debug_info = await self.browser.evaluate("""
                (() => {
                    const modal = document.querySelector('.modalDialogView');
                    const dtcLinks = document.querySelectorAll('a.clsExtHyperlink');
                    const allLinks = document.querySelectorAll('.modalDialogView a');
                    const tables = document.querySelectorAll('.modalDialogView table');
                    
                    // Get first few DTC links
                    const dtcSamples = [];
                    dtcLinks.forEach((a, i) => {
                        if (i < 10) dtcSamples.push(a.textContent?.trim());
                    });
                    
                    return {
                        modalFound: !!modal,
                        modalVisible: modal ? modal.offsetParent !== null : false,
                        dtcLinksCount: dtcLinks.length,
                        allLinksCount: allLinks.length,
                        tablesCount: tables.length,
                        dtcSamples: dtcSamples,
                        url: window.location.href
                    };
                })()
            """)
            logger.info(f"Debug info: {debug_info}")
            
            # The DTC page shows DTCs as a.clsExtHyperlink links in tables
            # Format: <td><a class="clsExtHyperlink">DTC C0110</a></td><td>Description</td>
            js_code = """
                (() => {
                    const targetDTC = '""" + dtc_code + """';
                    
                    // Helper to clean text
                    function cleanText(text) {
                        if (!text) return '';
                        text = text.replace(/\\$\\(document\\)[\\s\\S]*?\\}\\);/g, '');
                        text = text.replace(/\\s+/g, ' ').trim();
                        return text;
                    }
                    
                    const modal = document.querySelector('.modalDialogView');
                    const container = modal || document.body;
                    
                    // Find all DTC links (a.clsExtHyperlink)
                    const dtcLinks = container.querySelectorAll('a.clsExtHyperlink');
                    
                    for (const link of dtcLinks) {
                        const linkText = cleanText(link.textContent).toUpperCase();
                        
                        // Check if this link contains our DTC code
                        if (linkText.includes(targetDTC)) {
                            // Get the parent row to find the description
                            const row = link.closest('tr');
                            if (row) {
                                const cells = row.querySelectorAll('td');
                                if (cells.length >= 2) {
                                    return {
                                        code: targetDTC,
                                        description: cleanText(cells[1]?.textContent) || '',
                                        warning_type: cells.length > 2 ? cleanText(cells[2]?.textContent) : '',
                                        action: cells.length > 3 ? cleanText(cells[3]?.textContent) : ''
                                    };
                                }
                            }
                        }
                    }
                    
                    // Fallback: search all table rows
                    const tables = container.querySelectorAll('table');
                    for (const table of tables) {
                        const rows = table.querySelectorAll('tr');
                        for (const row of rows) {
                            const cells = row.querySelectorAll('td');
                            if (cells.length >= 2) {
                                const cellText = cleanText(cells[0]?.textContent).toUpperCase();
                                if (cellText.includes(targetDTC)) {
                                    return {
                                        code: targetDTC,
                                        description: cleanText(cells[1]?.textContent) || '',
                                        warning_type: cells.length > 2 ? cleanText(cells[2]?.textContent) : '',
                                        action: cells.length > 3 ? cleanText(cells[3]?.textContent) : ''
                                    };
                                }
                            }
                        }
                    }
                    
                    return null;
                })()
            """
            
            result = await self.browser.evaluate(js_code)
            
            if result:
                logger.info(f"Found DTC: {result}")
            else:
                logger.info(f"DTC {dtc_code} not found in tables")
                
            return result
        except Exception as e:
            logger.error(f"Error finding DTC in table: {e}")
            return None
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        lines = [
            f"**DTC: {data['code']}**",
            f"**Description:** {data['description']}",
            f"**Warning Type:** {data.get('warning_type', 'N/A')}",
            f"**Recommended Action:** {data.get('action', 'N/A')}"
        ]
        
        if data.get('system'):
            lines.insert(1, f"**System:** {data['system']}")
        
        if data.get('note'):
            lines.append(f"\n*Note: {data['note']}*")
        
        return "\n".join(lines)
