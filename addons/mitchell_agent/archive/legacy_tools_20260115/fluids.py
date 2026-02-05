"""
Fluid Capacities Tool - Retrieves fluid specs from ShopKeyPro.
"""
import asyncio
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from .base import MitchellTool, ToolResult, Vehicle, random_delay


@dataclass
class FluidSpec:
    """A single fluid specification."""
    fluid_type: str
    application: str
    variant: str
    standard_capacity: str
    metric_capacity: str
    fluid_spec: str
    note: str = ""
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "fluid_type": self.fluid_type,
            "application": self.application,
            "variant": self.variant,
            "standard": self.standard_capacity,
            "metric": self.metric_capacity,
            "spec": self.fluid_spec,
            "note": self.note
        }


class FluidCapacitiesTool(MitchellTool):
    """
    Retrieves fluid capacities and specifications.
    
    Access: Quick Access Panel > Fluid Capacities (#fluidsQuickAccess)
    
    Returns oil, coolant, transmission, differential, brake fluid specs
    with capacities in both standard and metric units.
    """
    
    name = "get_fluid_capacities"
    description = "Get fluid capacities and specifications (oil, coolant, trans, diff, brake)"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        fluid_type: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Get fluid capacities for the vehicle.
        
        Args:
            vehicle: Vehicle specification
            fluid_type: Optional filter (e.g., "Engine Oil", "Coolant")
            **kwargs: May include debug_screenshots=True
            
        Returns:
            ToolResult with list of FluidSpec data
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
                print(f"[FluidsTool] Skipping vehicle selection (already selected)")
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
            fluid_sel = self.get_selector("quick_access.fluid_capacities") or "#fluidsQuickAccess"
            home_sel = self.get_selector("module_selector.home") or "li.home a"
            
            # Quick Access panel is on the HOME view, not inside any module
            # First check if quick access is already visible
            quick_access_visible = False
            try:
                qa_elem = await self.browser.query_selector("#quickLinkRegion")
                if qa_elem and await qa_elem.is_visible():
                    quick_access_visible = True
                    print("[FluidsTool] Quick access panel already visible")
            except:
                pass
            
            if not quick_access_visible:
                # Navigate to Home to get the quick access panel
                print("[FluidsTool] Navigating to Home for quick access panel...")
                try:
                    await self.browser.click(home_sel, timeout=5000)
                    await random_delay(1500, 2500)
                except Exception as e:
                    print(f"[FluidsTool] Could not click Home: {e}")
                    # Try clicking the logo/brand as fallback
                    try:
                        await self.browser.click("a.brand, .logo a, text=ShopKeyPro", timeout=3000)
                        await random_delay(1500, 2500)
                    except:
                        pass
            
            # Step 3: On home page
            await self.save_debug_screenshot("03_home_page")
            
            # Wait for quick access panel to be visible
            try:
                await self.browser.wait_for_selector("#quickLinkRegion", timeout=8000)
                print("[FluidsTool] Quick access panel now visible")
            except:
                print("[FluidsTool] Quick access panel not visible after navigation")
                await random_delay(1000, 2000)
            
            # Close any existing modal
            await self.close_modal()
            
            # Remove any modal mask
            await self.browser.evaluate(
                "document.querySelector('.modal_mask')?.remove()"
            )
            
            # Step 4: Before clicking fluids
            await self.save_debug_screenshot("04_before_fluids_click")
            
            # Use click_quick_access helper which shows the panel first
            print(f"[FluidsTool] Clicking quick access: {fluid_sel}")
            clicked = await self.click_quick_access(fluid_sel)
            if not clicked:
                await self.save_debug_screenshot("04_fluids_click_failed")
                return ToolResult(
                    success=False,
                    error="Could not open Fluid Capacities panel",
                    source=self.name
                )
            await random_delay(2000, 3500)
            
            # Step 5: Fluids modal open
            await self.save_debug_screenshot("05_fluids_modal_open")
            
            # Extract table data
            table_data = await self._extract_fluid_table()
            
            # Step 6: After data extraction
            await self.save_debug_screenshot("06_data_extracted")
            
            if not table_data:
                return ToolResult(
                    success=False,
                    error="Could not extract fluid data from table",
                    source=self.name
                )
            
            # Filter by fluid type if specified
            if fluid_type:
                fluid_type_lower = fluid_type.lower()
                table_data = [
                    row for row in table_data
                    if fluid_type_lower in row.get("fluid_type", "").lower()
                ]
            
            # Capture any images from the modal before closing
            images = await self.extract_images_from_modal()
            if images:
                print(f"[FluidsTool] Captured {len(images)} images from modal")
            
            # Close the modal
            await self.close_modal()
            
            # Step 7: Final state
            await self.save_debug_screenshot("07_final_state")
            
            return ToolResult(
                success=True,
                data=table_data,
                source=self.name,
                images=images if images else None,
                auto_selected_options=self.get_auto_selected_options() or None
            )
            
        except Exception as e:
            await self.save_debug_screenshot("error_state")
            return ToolResult(
                success=False,
                error=f"Error retrieving fluid capacities: {str(e)}",
                source=self.name
            )
    
    async def _extract_fluid_table(self) -> List[Dict[str, str]]:
        """Extract fluid data from the modal table."""
        if not self.browser:
            return []
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const table = document.querySelector('.modalDialogView table');
                    if (!table) return [];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    if (rows.length < 2) return [];
                    
                    const data = [];
                    for (let i = 1; i < rows.length; i++) {
                        const cells = Array.from(rows[i].querySelectorAll('td'));
                        if (cells.length >= 6) {
                            data.push({
                                fluid_type: cells[0]?.textContent?.trim() || '',
                                application: cells[1]?.textContent?.trim() || '',
                                variant: cells[2]?.textContent?.trim() || '',
                                standard: cells[3]?.textContent?.trim() || '',
                                metric: cells[4]?.textContent?.trim() || '',
                                spec: cells[5]?.textContent?.trim() || '',
                                note: cells[6]?.textContent?.trim() || ''
                            });
                        }
                    }
                    return data;
                })()
            """)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error extracting fluid table: {e}")
            return []
    
    def format_response(self, result: ToolResult) -> str:
        """Format the result for display."""
        if not result.success:
            return f"Error: {result.error}"
        
        lines = ["**Fluid Capacities:**\n"]
        
        for fluid in result.data:
            lines.append(f"**{fluid['fluid_type']}** ({fluid['application']} {fluid['variant']})")
            lines.append(f"  - Capacity: {fluid['standard']} / {fluid['metric']}")
            lines.append(f"  - Specification: {fluid['spec']}")
            if fluid.get('note'):
                lines.append(f"  - Note: {fluid['note']}")
            lines.append("")
        
        return "\n".join(lines)
