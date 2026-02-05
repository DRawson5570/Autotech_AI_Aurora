"""
Reset Procedure Tool - Retrieves reset procedures (oil life, TPMS, etc.).
"""
import asyncio
import random
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay


# Common reset procedure categories
RESET_PROCEDURES = {
    "oil": ["oil life", "oil reset", "oil service"],
    "tpms": ["tpms", "tire pressure", "tire sensor", "tpms reset", "tpms relearn"],
    "maintenance": ["maintenance light", "service light", "maintenance reset"],
    "battery": ["battery reset", "bms", "battery management"],
    "brake": ["brake pad reset", "electronic parking brake"],
    "steering": ["steering angle", "steering sensor"],
    "abs": ["abs reset", "abs bleed"],
}


class ResetProcedureTool(MitchellTool):
    """
    Retrieves reset procedures for various vehicle systems.
    
    Access: Quick Access Panel > Reset Procedures (#resetProceduresAccess)
    
    Common procedures include:
    - Oil life monitor reset
    - TPMS sensor activation/relearn
    - Maintenance light reset
    - Battery management reset
    - Electronic parking brake service mode
    """
    
    name = "get_reset_procedure"
    description = "Get reset procedures for vehicle systems"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        procedure: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get reset procedures for the vehicle.
        
        Args:
            vehicle: Vehicle specification
            procedure: Type of procedure (e.g., "oil", "tpms")
            query: Alternative query string
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with reset procedures
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
                print(f"[ResetTool] Skipping vehicle selection (already selected)")
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
            reset_sel = self.get_selector("quick_access.reset_procedures") or "#resetProceduresAccess"
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
            
            # Step 3: Before clicking reset procedures
            await self.save_debug_screenshot("03_before_reset_click")
            
            # Click Reset Procedures quick access (use #quickLinkRegion prefix to avoid duplicate ID issue)
            selector = reset_sel
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3500)
            
            # Step 4: Reset modal open
            await self.save_debug_screenshot("04_reset_modal_open")
            
            # Extract reset procedures - this opens a tree structure
            procedures = await self._extract_procedures()
            
            # Step 5: After extraction
            await self.save_debug_screenshot("05_data_extracted")
            
            # Capture any images from the modal before closing
            images = await self.extract_images_from_modal()
            if images:
                print(f"[ResetTool] Captured {len(images)} images from modal")
            
            # Close the modal
            await self.close_modal()
            
            # Step 6: Final state
            await self.save_debug_screenshot("06_final_state")
            
            if not procedures:
                return ToolResult(
                    success=False,
                    error="Could not extract reset procedures",
                    source=self.name,
                    images=images if images else None
                )
            
            # Filter by procedure type if specified
            search_term = procedure or query
            if search_term:
                search_lower = search_term.lower()
                
                # Check if it matches a known category
                matched_keywords = []
                for category, keywords in RESET_PROCEDURES.items():
                    if search_lower in category or any(kw in search_lower for kw in keywords):
                        matched_keywords.extend(keywords)
                
                if matched_keywords:
                    # Filter using category keywords
                    procedures = [
                        p for p in procedures
                        if any(kw in p.get("name", "").lower() or kw in p.get("category", "").lower()
                               for kw in matched_keywords)
                    ]
                else:
                    # Direct search
                    procedures = [
                        p for p in procedures
                        if search_lower in p.get("name", "").lower()
                        or search_lower in p.get("category", "").lower()
                    ]
            
            return ToolResult(
                success=True,
                data=procedures,
                source=self.name,
                images=images if images else None,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving reset procedures: {str(e)}",
                source=self.name
            )
    
    async def _extract_procedures(self) -> List[Dict[str, str]]:
        """Extract reset procedures from the modal tree structure."""
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
                        treeNodes: document.querySelectorAll('li.usercontrol.node').length,
                        allLists: document.querySelectorAll('ul, ol').length,
                        iframes: document.querySelectorAll('iframe').length
                    };
                    return info;
                })()
            """)
            print(f"[ResetProcedure DEBUG] Page state: modal={debug_info.get('hasModal')}, treeNodes={debug_info.get('treeNodes')}, iframes={debug_info.get('iframes')}")
            if debug_info.get('treeNodes', 0) == 0:
                print(f"[ResetProcedure DEBUG] Modal HTML preview: {debug_info.get('modalHTML', 'N/A')[:500]}")
            
            result = await self.browser.evaluate("""
                (() => {
                    const procedures = [];
                    
                    // Reset Procedures uses a tree structure
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return procedures;
                    
                    // Get all tree nodes
                    const nodes = modal.querySelectorAll('li.usercontrol.node');
                    
                    for (const node of nodes) {
                        const level = node.getAttribute('data-level');
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.trim();
                        const isLeaf = node.classList.contains('leaf');
                        
                        if (text) {
                            procedures.push({
                                name: text,
                                level: level || '0',
                                is_procedure: isLeaf,
                                category: ''  // Will be filled based on parent
                            });
                        }
                    }
                    
                    // Set categories based on hierarchy
                    let currentCategory = '';
                    for (const proc of procedures) {
                        if (proc.level === '0') {
                            currentCategory = proc.name;
                        }
                        proc.category = currentCategory;
                    }
                    
                    return procedures;
                })()
            """)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error extracting procedures: {e}")
            return []
    
    async def get_procedure_details(
        self,
        vehicle: Vehicle,
        procedure_name: str
    ) -> ToolResult:
        """
        Get detailed steps for a specific reset procedure.
        
        Args:
            vehicle: Vehicle specification
            procedure_name: Name of the procedure to get details for
            
        Returns:
            ToolResult with procedure details
        """
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser controller not available",
                source=self.name
            )
        
        try:
            # Navigate to reset procedures
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
            reset_selector = self.get_selector("quick_access.reset_procedures") or "#resetProceduresAccess"
            selector = f"#quickLinkRegion {reset_selector}" if reset_selector.startswith("#") else reset_selector
            await self.browser.click(selector, timeout=10000)
            await asyncio.sleep(2)
            
            # Find and click the procedure node
            clicked = await self.browser.evaluate(f"""
                (() => {{
                    const target = '{procedure_name.lower()}';
                    const nodes = document.querySelectorAll('li.usercontrol.node');
                    
                    for (const node of nodes) {{
                        const text = node.querySelector('.nodeText, .text, span')?.textContent?.trim()?.toLowerCase();
                        if (text && text.includes(target)) {{
                            const showIcon = node.querySelector('.showContentIcon');
                            if (showIcon) {{
                                showIcon.click();
                                return true;
                            }}
                        }}
                    }}
                    return false;
                }})()
            """)
            
            if not clicked:
                await self.close_modal()
                return ToolResult(
                    success=False,
                    error=f"Procedure '{procedure_name}' not found",
                    source=self.name
                )
            
            await asyncio.sleep(2)
            
            # Extract procedure content
            content = await self.browser.evaluate("""
                (() => {
                    const modal = document.querySelector('.modalDialogView:last-child');
                    if (!modal) return '';
                    
                    const content = modal.querySelector('.content');
                    return content ? content.innerText : '';
                })()
            """)
            
            # Capture any images from the procedure modal
            images = await self.extract_images_from_modal()
            if images:
                print(f"[ResetTool] Captured {len(images)} images from procedure detail")
            
            await self.close_modal()
            
            return ToolResult(
                success=True,
                data={
                    "procedure": procedure_name,
                    "steps": content
                },
                source=self.name,
                images=images if images else None,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Error getting procedure details: {str(e)}",
                source=self.name
            )
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        data = result.data
        
        # Check if this is detailed procedure result
        if isinstance(data, dict) and "steps" in data:
            return f"**{data.get('procedure', 'Reset Procedure')}**\n\n{data.get('steps', '')}"
        
        # List of procedures
        if not data:
            return "No reset procedures found for the specified criteria."
        
        lines = ["**Reset Procedures:**\n"]
        
        current_category = ""
        for proc in data:
            if proc.get("category") != current_category:
                current_category = proc.get("category", "")
                if current_category:
                    lines.append(f"\n**{current_category}**")
            
            if proc.get("is_procedure"):
                lines.append(f"  - {proc.get('name', '')}")
        
        return "\n".join(lines)
