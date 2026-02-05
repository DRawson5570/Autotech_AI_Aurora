"""
Vehicle Selector
================
Handles vehicle selection UI in ShopKeyPro.
"""

import asyncio
import logging
from typing import Optional, Dict, List, Any

from playwright.async_api import Page

log = logging.getLogger(__name__)


class VehicleSelector:
    """
    Handles vehicle selection in ShopKeyPro.
    
    Usage:
        selector = VehicleSelector(page)
        result = await selector.select_vehicle(
            year=2018,
            make="Ford",
            model="F-150",
            engine="5.0L"
        )
    """
    
    def __init__(self, page: Page):
        """
        Initialize vehicle selector.
        
        Args:
            page: Playwright Page instance
        """
        self.page = page
    
    async def open_vehicle_selector(self) -> bool:
        """
        Open the vehicle selector panel.
        
        Returns:
            True if opened successfully
        """
        try:
            button_sel = "#vehicleSelectorButton"
            await self.page.locator(button_sel).click()
            await asyncio.sleep(0.5)
            
            # Wait for selector to appear
            panel_sel = ".vehicleSelectorPanel, #vehicleSelector"
            await self.page.locator(panel_sel).wait_for(timeout=5000, state="visible")
            
            log.info("Vehicle selector opened")
            return True
        except Exception as e:
            log.error(f"Failed to open vehicle selector: {e}")
            return False
    
    async def select_vehicle(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        body_style: Optional[str] = None,
        drive_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Select a vehicle in ShopKeyPro.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification (optional)
            submodel: Submodel/trim (optional)
            body_style: Body style (optional)
            drive_type: Drive type (optional)
            
        Returns:
            Result dict with success status and any auto-selected options
        """
        result = {
            "success": False,
            "auto_selected": {},
            "error": None,
        }
        
        try:
            # Open selector if not already open
            if not await self._is_selector_open():
                if not await self.open_vehicle_selector():
                    result["error"] = "Could not open vehicle selector"
                    return result
            
            # Select year
            if not await self._select_tab_value("year", str(year)):
                result["error"] = f"Could not select year: {year}"
                return result
            
            # Select make
            if not await self._select_tab_value("make", make):
                result["error"] = f"Could not select make: {make}"
                return result
            
            # Select model
            if not await self._select_tab_value("model", model):
                result["error"] = f"Could not select model: {model}"
                return result
            
            # Select engine if provided
            if engine:
                await self._select_tab_value("engine", engine)
            
            # Handle optional fields (may need auto-selection)
            options_result = await self._handle_options(
                submodel=submodel,
                body_style=body_style,
                drive_type=drive_type,
            )
            
            if options_result.get("error"):
                result["error"] = options_result["error"]
                return result
            
            result["auto_selected"] = options_result.get("auto_selected", {})
            
            # Apply vehicle selection
            await self._apply_selection()
            
            result["success"] = True
            log.info(f"Vehicle selected: {year} {make} {model}")
            return result
            
        except Exception as e:
            log.error(f"Vehicle selection failed: {e}")
            result["error"] = str(e)
            return result
    
    async def _is_selector_open(self) -> bool:
        """Check if vehicle selector panel is open."""
        try:
            panel = self.page.locator(".vehicleSelectorPanel, #vehicleSelector")
            return await panel.is_visible(timeout=1000)
        except Exception:
            return False
    
    async def _select_tab_value(self, tab_name: str, value: str) -> bool:
        """
        Select a value in a vehicle selector tab.
        
        Args:
            tab_name: Tab name (year, make, model, engine)
            value: Value to select
            
        Returns:
            True if selection successful
        """
        try:
            # Click the tab
            tab_sel = f"li.{tab_name}, li[data-tab='{tab_name}']"
            await self.page.locator(tab_sel).click()
            await asyncio.sleep(0.3)
            
            # Find and click the value
            value_sel = f"li.qualifier:has-text('{value}')"
            value_loc = self.page.locator(value_sel).first
            
            if await value_loc.is_visible(timeout=3000):
                await value_loc.click()
                await asyncio.sleep(0.5)
                log.debug(f"Selected {tab_name}: {value}")
                return True
            else:
                log.warning(f"Value not found in {tab_name}: {value}")
                return False
                
        except Exception as e:
            log.error(f"Error selecting {tab_name}={value}: {e}")
            return False
    
    async def _handle_options(
        self,
        submodel: Optional[str] = None,
        body_style: Optional[str] = None,
        drive_type: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle optional vehicle options.
        
        Auto-selects first available if not specified.
        """
        result = {
            "auto_selected": {},
            "error": None,
        }
        
        # Check if options tab is visible
        options_tab = self.page.locator("li.Options, li[data-tab='options']")
        
        try:
            if not await options_tab.is_visible(timeout=2000):
                return result  # No options needed
        except Exception:
            return result
        
        await options_tab.click()
        await asyncio.sleep(0.5)
        
        # Handle each option type
        option_groups = await self._get_option_groups()
        
        for group_name, values in option_groups.items():
            if not values:
                continue
            
            # Determine desired value
            provided_value = None
            if group_name.lower() == "submodel" and submodel:
                provided_value = submodel
            elif group_name.lower() in ("body style", "body_style") and body_style:
                provided_value = body_style
            elif group_name.lower() in ("drive type", "drive_type") and drive_type:
                provided_value = drive_type
            
            if provided_value:
                # Try to select the provided value
                selected = await self._select_option(group_name, provided_value)
                if not selected:
                    # Try first option as fallback
                    first_value = values[0]
                    await self._select_option(group_name, first_value)
                    result["auto_selected"][group_name.lower().replace(" ", "_")] = first_value
            else:
                # Auto-select first available
                first_value = values[0]
                await self._select_option(group_name, first_value)
                result["auto_selected"][group_name.lower().replace(" ", "_")] = first_value
        
        return result
    
    async def _get_option_groups(self) -> Dict[str, List[str]]:
        """Get available option groups and their values."""
        groups = {}
        
        try:
            group_elements = await self.page.locator("div.optionGroup").all()
            
            for group in group_elements:
                # Get group name from header
                header = await group.locator(".optionGroupHeader, h4, h5").text_content()
                if not header:
                    continue
                
                # Get values
                values = []
                value_locs = await group.locator("li.qualifier, li.option").all()
                for val_loc in value_locs:
                    text = await val_loc.text_content()
                    if text:
                        values.append(text.strip())
                
                groups[header.strip()] = values
                
        except Exception as e:
            log.warning(f"Error getting option groups: {e}")
        
        return groups
    
    async def _select_option(self, group_name: str, value: str) -> bool:
        """Select an option value within a group."""
        try:
            selector = f"div.optionGroup:has-text('{group_name}') li:has-text('{value}')"
            loc = self.page.locator(selector).first
            
            if await loc.is_visible(timeout=2000):
                await loc.click()
                await asyncio.sleep(0.3)
                return True
        except Exception:
            pass
        return False
    
    async def _apply_selection(self):
        """Apply the vehicle selection."""
        try:
            # Look for apply/go button
            apply_selectors = [
                "#vehicleSelectorApplyButton",
                "button:has-text('Go')",
                "button:has-text('Apply')",
                "input[value='Go']",
            ]
            
            for sel in apply_selectors:
                loc = self.page.locator(sel).first
                try:
                    if await loc.is_visible(timeout=1000):
                        await loc.click()
                        await asyncio.sleep(1)
                        log.info("Vehicle selection applied")
                        return
                except Exception:
                    continue
            
            log.warning("Could not find apply button")
            
        except Exception as e:
            log.error(f"Error applying selection: {e}")
    
    async def get_current_vehicle(self) -> Optional[Dict[str, str]]:
        """
        Get the currently selected vehicle.
        
        Returns:
            Dict with year, make, model, engine or None
        """
        try:
            # The vehicle info is often displayed in a header or breadcrumb
            vehicle_display = self.page.locator("#vehicleDisplayText, .vehicleInfo").first
            text = await vehicle_display.text_content()
            
            if text:
                # Parse vehicle string (e.g., "2018 Ford F-150 5.0L")
                parts = text.strip().split()
                if len(parts) >= 3:
                    return {
                        "year": parts[0],
                        "make": parts[1],
                        "model": " ".join(parts[2:-1]) if len(parts) > 3 else parts[2],
                        "engine": parts[-1] if len(parts) > 3 else None,
                    }
        except Exception:
            pass
        
        return None
