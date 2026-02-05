"""
Torque Specs Tool - Retrieves torque specifications.
"""
import asyncio
import random
from typing import Dict, List, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay


class TorqueSpecsTool(MitchellTool):
    """
    Retrieves torque specifications from Common Specs.
    
    Access: Quick Access Panel > Common Specs (#commonSpecsAccess)
    
    Returns torque values for various components including
    wheel lug nuts, brake calipers, suspension components, etc.
    """
    
    name = "get_torque_specs"
    description = "Get torque specifications for vehicle components"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        component: Optional[str] = None,
        query: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get torque specifications for the vehicle.
        
        Args:
            vehicle: Vehicle specification
            component: Optional component filter (e.g., "wheel", "caliper")
            query: Alternative query string
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with torque specifications
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
                print(f"[TorqueTool] Skipping vehicle selection (already selected)")
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
            specs_selector = self.get_selector("quick_access.common_specs") or "#commonSpecsAccess"
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
            
            # Step 3: Before clicking torque specs
            await self.save_debug_screenshot("03_before_torque_click")
            
            # Click Common Specs quick access (use #quickLinkRegion prefix)
            selector = specs_selector
            if selector.startswith("#") and not selector.startswith("#quickLinkRegion"):
                selector = f"#quickLinkRegion {selector}"
            await random_delay(400, 800)
            await self.browser.click(selector, timeout=10000)
            await random_delay(2000, 3500)
            
            # Step 4: Torque modal open
            await self.save_debug_screenshot("04_torque_modal_open")
            
            # Extract torque specs
            specs = await self._extract_torque_specs()
            
            # Step 5: After extraction
            await self.save_debug_screenshot("05_data_extracted")
            
            # Close the modal
            await self.close_modal()
            
            # Step 6: Final state
            await self.save_debug_screenshot("06_final_state")
            
            if not specs:
                return ToolResult(
                    success=False,
                    error="Could not extract torque specifications",
                    source=self.name
                )
            
            # Filter by component if specified
            search_term = component or query
            if search_term:
                search_lower = search_term.lower()
                specs = [
                    s for s in specs
                    if search_lower in s.get("component", "").lower()
                    or search_lower in s.get("application", "").lower()
                ]
            
            return ToolResult(
                success=True,
                data=specs,
                source=self.name,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving torque specs: {str(e)}",
                source=self.name
            )
    
    async def _extract_torque_specs(self) -> List[Dict[str, str]]:
        """Extract torque specifications from the modal."""
        if not self.browser:
            return []
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const specs = [];
                    
                    // Look for torque-related tables
                    const tables = document.querySelectorAll('.modalDialogView table');
                    
                    for (const table of tables) {
                        const rows = Array.from(table.querySelectorAll('tr'));
                        
                        for (const row of rows) {
                            const cells = Array.from(row.querySelectorAll('td, th'));
                            const text = row.textContent.toLowerCase();
                            
                            // Look for torque values (ft-lb, nm, etc.)
                            if (text.includes('ft') || text.includes('nm') || text.includes('torque')) {
                                if (cells.length >= 2) {
                                    specs.push({
                                        component: cells[0]?.textContent?.trim() || '',
                                        application: cells[1]?.textContent?.trim() || '',
                                        torque_standard: cells[2]?.textContent?.trim() || '',
                                        torque_metric: cells[3]?.textContent?.trim() || '',
                                        note: cells[4]?.textContent?.trim() || ''
                                    });
                                }
                            }
                        }
                    }
                    
                    // Also look for text-based torque specs
                    const content = document.querySelector('.modalDialogView .content');
                    if (content) {
                        const text = content.textContent;
                        const torquePattern = /(\\d+)\\s*(ft-lb|ft\\.lb|nm|n\\.m)/gi;
                        // Additional parsing could be done here
                    }
                    
                    return specs;
                })()
            """)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error extracting torque specs: {e}")
            return []
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        if not result.data:
            return "No torque specifications found for the specified criteria."
        
        lines = ["**Torque Specifications:**\n"]
        
        for spec in result.data:
            lines.append(f"**{spec.get('component', 'Component')}**")
            if spec.get('application'):
                lines.append(f"  Application: {spec['application']}")
            if spec.get('torque_standard') or spec.get('torque_metric'):
                torque = f"{spec.get('torque_standard', '')} / {spec.get('torque_metric', '')}".strip(' /')
                lines.append(f"  Torque: {torque}")
            if spec.get('note'):
                lines.append(f"  Note: {spec['note']}")
            lines.append("")
        
        return "\n".join(lines)
