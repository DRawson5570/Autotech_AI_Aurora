"""
VIN/Plate Lookup Tool - Decode vehicle from VIN or license plate.

Updated 2026-01-09: Initial implementation.
Access: Vehicle Selector > VIN or Plate accordion

Flow:
1. Click vehicle selector to open accordion
2. Click "VIN or Plate" accordion header
3. Enter VIN or Plate+State
4. Click appropriate Lookup button
5. If successful, click "Use This Vehicle"
6. Extract decoded vehicle info from header
"""
import asyncio
import logging
import re
from typing import Dict, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle, random_delay

# Set up logging
logger = logging.getLogger("vin_plate_lookup_tool")
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    fh = logging.FileHandler("/tmp/vin_plate_lookup_tool.log")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
    logger.addHandler(fh)


# US State codes for validation
US_STATE_CODES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU"
}


def parse_input(raw_input: str) -> Dict[str, Optional[str]]:
    """
    Parse raw input to extract VIN or plate+state.
    
    Examples:
    - "1G1PC5SB8E7123456" -> {"vin": "1G1PC5SB8E7123456"}
    - "4mzh83 mi" -> {"plate": "4MZH83", "state": "MI"}
    - "4MZ H83, MI" -> {"plate": "4MZH83", "state": "MI"}
    - "ABC-1234 OH" -> {"plate": "ABC1234", "state": "OH"}
    """
    text = raw_input.strip().upper()
    
    # Remove common separators and normalize
    # VINs are exactly 17 alphanumeric characters (no I, O, Q)
    vin_pattern = r'^[A-HJ-NPR-Z0-9]{17}$'
    
    # Try to extract VIN (17 chars)
    clean_text = re.sub(r'[\s\-]', '', text)
    if re.match(vin_pattern, clean_text):
        return {"vin": clean_text, "plate": None, "state": None}
    
    # Try to extract plate + state
    # Pattern: plate chars followed by optional separator and 2-letter state
    # Plates can have letters, numbers, spaces, hyphens
    
    # Look for 2-letter state code at the end
    parts = re.split(r'[\s,]+', text)
    if len(parts) >= 2:
        potential_state = parts[-1].strip()
        if potential_state in US_STATE_CODES:
            # Everything before is the plate
            plate_parts = parts[:-1]
            plate = re.sub(r'[\s\-]', '', ''.join(plate_parts))
            return {"vin": None, "plate": plate, "state": potential_state}
    
    # If we can't parse, assume it might be just a VIN that doesn't validate
    # Let the portal handle validation
    if len(clean_text) == 17:
        return {"vin": clean_text, "plate": None, "state": None}
    
    # Last resort - treat as plate without state
    return {"vin": None, "plate": clean_text, "state": None}


class VINPlateLookupTool(MitchellTool):
    """
    Look up vehicle by VIN or license plate.
    
    Access: Vehicle Selector > VIN or Plate accordion
    
    Returns decoded vehicle info:
    - year, make, model, engine
    - full VIN (if plate lookup succeeded)
    """
    
    name = "lookup_vehicle"
    description = "Look up vehicle by VIN or license plate to decode year, make, model, engine"
    tier = 1
    
    def __init__(self, browser_controller=None):
        super().__init__(browser_controller)
        # Import selectors module - no longer loaded from JSON
        from .. import selectors as SEL
        self._vp_config = SEL.VIN_PLATE_LOOKUP
    
    async def execute(
        self,
        vehicle: Vehicle,  # Not used for lookup, but required by interface
        vin: Optional[str] = None,
        plate: Optional[str] = None,
        state: Optional[str] = None,
        raw_input: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        """
        Look up vehicle by VIN or plate.
        
        Args:
            vehicle: Not used (required by interface)
            vin: 17-character VIN
            plate: License plate number
            state: 2-letter state code (required if using plate)
            raw_input: Raw OCR text like "4mzh83 mi" - will be parsed
            
        Returns:
            ToolResult with decoded vehicle info
        """
        logger.info(f"VIN/Plate lookup: vin={vin}, plate={plate}, state={state}, raw={raw_input}")
        
        # Parse raw input if provided
        if raw_input:
            parsed = parse_input(raw_input)
            vin = parsed.get("vin") or vin
            plate = parsed.get("plate") or plate
            state = parsed.get("state") or state
            logger.info(f"Parsed raw input: vin={vin}, plate={plate}, state={state}")
        
        # Validate inputs
        if not vin and not plate:
            return ToolResult(
                success=False,
                error="Either VIN or plate must be provided",
                source=self.name
            )
        
        if plate and not state:
            return ToolResult(
                success=False,
                error="State code is required for plate lookup (e.g., 'MI', 'OH', 'CA')",
                source=self.name
            )
        
        # Ensure browser is available
        if not self.browser:
            return ToolResult(
                success=False,
                error="Browser not initialized",
                source=self.name
            )
        
        try:
            # self.browser IS the Page object (set by registry.set_browser)
            page = self.browser
            # self._vp_config already contains selectors from __init__
            selectors = self._vp_config
            logger.info(f"Using selectors: {list(selectors.keys())}")
            
            # Step 1: Open vehicle selector
            logger.info("Opening vehicle selector")
            await self._open_vehicle_selector(page, selectors)
            
            # Step 2: Click "VIN or Plate" accordion
            logger.info("Clicking VIN or Plate accordion")
            await self._open_vin_plate_accordion(page, selectors)
            
            # Step 3: Perform lookup
            if vin:
                result = await self._lookup_by_vin(page, selectors, vin)
            else:
                result = await self._lookup_by_plate(page, selectors, plate, state)
            
            if not result.get("success"):
                return ToolResult(
                    success=False,
                    error=result.get("error", "Lookup failed"),
                    source=self.name
                )
            
            # Step 4: Extract VIN from input BEFORE closing the panel
            # The VIN input shows the decoded VIN after plate lookup
            decoded_vin = None
            try:
                vin_input = page.locator("input#Vin, input.vin").first
                if await vin_input.count() > 0:
                    decoded_vin = await vin_input.input_value()
                    if decoded_vin and len(decoded_vin) == 17:
                        logger.info(f"Captured VIN from input: {decoded_vin}")
                    else:
                        decoded_vin = None
            except Exception as e:
                logger.debug(f"Could not capture VIN: {e}")
            
            # Also try to get vehicle text from accordion header
            # Format: "VIN or Plate    2014 Chevrolet Cruze 1.4L LT"
            vehicle_text_from_header = None
            try:
                header = page.locator(".header:has(h1:has-text('VIN or Plate'))").first
                if await header.count() > 0:
                    header_text = await header.inner_text()
                    # Extract vehicle info after "VIN or Plate"
                    if "VIN or Plate" in header_text:
                        parts = header_text.split("VIN or Plate")
                        if len(parts) > 1:
                            vehicle_text_from_header = parts[1].strip()
                            logger.info(f"Captured vehicle from header: {vehicle_text_from_header}")
            except Exception as e:
                logger.debug(f"Could not capture header text: {e}")
            
            # Step 5: Click "Use This Vehicle" button
            logger.info("Clicking Use This Vehicle")
            await self._click_use_this_vehicle(page, selectors)
            
            # Step 6: Extract/parse vehicle info
            vehicle_info = await self._extract_vehicle_info(page, selectors, decoded_vin, vehicle_text_from_header)
            logger.info(f"Decoded vehicle: {vehicle_info}")
            
            return ToolResult(
                success=True,
                data=vehicle_info,
                source=self.name
            )
            
        except Exception as e:
            logger.exception(f"VIN/Plate lookup failed: {e}")
            # Take debug screenshot
            try:
                await self.browser.screenshot(path="/tmp/vin_plate_error.png")
            except:
                pass
            return ToolResult(
                success=False,
                error=str(e),
                source=self.name
            )
    
    async def _open_vehicle_selector(self, page, selectors: Dict) -> None:
        """Open the vehicle selector dropdown."""
        vehicle_selector_btn = selectors.get("vehicle_selector_button", "#vehicleSelectorButton")
        
        # Check if already open (has 'active' class)
        selector_container = await page.query_selector("#vehicleSelector")
        if selector_container:
            class_attr = await selector_container.get_attribute("class")
            if class_attr and "active" in class_attr:
                logger.info("Vehicle selector already open")
                return
        
        # Click to open
        btn = page.locator(vehicle_selector_btn)
        if await btn.count() > 0:
            await btn.click()
            await random_delay(500, 1000)
    
    async def _open_vin_plate_accordion(self, page, selectors: Dict) -> None:
        """Click the VIN or Plate accordion header to expand it."""
        # Use the correct selector from config
        accordion_header = selectors.get("vin_plate_header", "div.header:has(h1:has-text('VIN or Plate'))")
        
        logger.info(f"Looking for VIN or Plate header: {accordion_header}")
        
        # First try the configured selector
        header = page.locator(accordion_header)
        if await header.count() > 0:
            await header.click()
            await random_delay(500, 1000)
            logger.info("Clicked VIN or Plate accordion")
            return
        
        # Try xpath selector (more reliable)
        try:
            header_xpath = "//div[@class='header']/h1[contains(text(),'VIN or Plate')]/.."
            header = page.locator(f"xpath={header_xpath}")
            if await header.count() > 0:
                await header.click()
                await random_delay(500, 1000)
                logger.info("Clicked VIN or Plate accordion (xpath)")
                return
        except Exception as e:
            logger.debug(f"XPath selector failed: {e}")
        
        # Try text-based selector
        header = page.locator("div.header >> text=VIN or Plate")
        if await header.count() > 0:
            # Click the parent div.header
            await header.locator("..").click()
            await random_delay(500, 1000)
            logger.info("Clicked VIN or Plate accordion (text-based)")
            return
        
        raise Exception("Could not find VIN or Plate accordion header")
    
    async def _lookup_by_vin(self, page, selectors: Dict, vin: str) -> Dict:
        """Enter VIN and perform lookup."""
        logger.info(f"Looking up VIN: {vin}")
        
        # Use correct selectors from config
        vin_input = selectors.get("vin_input", "input#Vin")
        vin_lookup_btn = selectors.get("vin_lookup_button", "input.button.decodeButton.grey")
        
        # Wait for the input to be visible
        logger.info(f"Waiting for VIN input: {vin_input}")
        await page.wait_for_selector(vin_input, timeout=5000)
        
        # Enter VIN
        input_el = page.locator(vin_input).first
        await input_el.fill(vin)
        await random_delay(300, 500)
        logger.info(f"Entered VIN: {vin}")
        
        # Click the VIN Lookup button (grey one, first decodeButton)
        lookup_btn = page.locator(vin_lookup_btn)
        if await lookup_btn.count() > 0:
            await lookup_btn.first.click()
            logger.info("Clicked VIN Lookup button")
        else:
            # Fallback: find first Lookup button near VIN input
            lookup_btn = page.locator("input.decodeButton").first
            await lookup_btn.click()
            logger.info("Clicked first decodeButton (fallback)")
        
        await random_delay(1500, 2500)
        
        # Check for errors
        error_msg = await self._check_for_errors(page, selectors)
        if error_msg:
            return {"success": False, "error": error_msg}
        
        return {"success": True}
    
    async def _lookup_by_plate(self, page, selectors: Dict, plate: str, state: str) -> Dict:
        """Enter plate and state, perform lookup."""
        # Sanitize plate - remove spaces and dashes (e.g., "AUE 709" -> "AUE709")
        plate = plate.replace(" ", "").replace("-", "").upper()
        logger.info(f"Looking up plate: {plate}, state: {state}")
        
        # Use correct selectors from config
        plate_input = selectors.get("plate_input", "input#plate")
        state_input = selectors.get("state_input", "input#stateInput")
        plate_lookup_btn = selectors.get("plate_lookup_button", "input.button.decodeButton.blue")
        
        # Wait for inputs to be visible
        logger.info(f"Waiting for plate input: {plate_input}")
        await page.wait_for_selector(plate_input, timeout=5000)
        
        # Enter plate
        plate_el = page.locator(plate_input).first
        await plate_el.fill(plate)
        await random_delay(300, 500)
        logger.info(f"Entered plate: {plate}")
        
        # Select state from the hidden <select> element inside .customSelect
        # The text input #stateInput is just for display - the real selection is a <select>
        state_select = ".customSelect select"
        select_el = page.locator(state_select)
        if await select_el.count() > 0:
            await select_el.select_option(state)
            await random_delay(300, 500)
            logger.info(f"Selected state: {state}")
        else:
            # Fallback: try the text input
            logger.warning(f"State select not found, trying text input: {state_input}")
            state_el = page.locator(state_input).first
            if await state_el.count() > 0:
                await state_el.fill(state)
                await random_delay(300, 500)
                logger.info(f"Entered state via text input: {state}")
        
        # Take screenshot before clicking lookup
        await page.screenshot(path="/tmp/vin_plate_before_lookup.png")
        logger.info("Screenshot saved: /tmp/vin_plate_before_lookup.png")
        
        # Click the Plate Lookup button (blue one, not grey)
        logger.info(f"Looking for plate lookup button: {plate_lookup_btn}")
        lookup_btn = page.locator(plate_lookup_btn)
        btn_count = await lookup_btn.count()
        logger.info(f"Found {btn_count} buttons matching {plate_lookup_btn}")
        
        if btn_count > 0:
            # Check button classes for debugging
            btn_class = await lookup_btn.first.get_attribute("class")
            logger.info(f"Button classes: {btn_class}")
            await lookup_btn.first.click()
            logger.info("Clicked Plate Lookup button")
        else:
            # Fallback: try different selectors
            logger.info("Primary selector failed, trying fallbacks...")
            
            # Try .blue without .button
            lookup_btn = page.locator("input.decodeButton.blue")
            if await lookup_btn.count() > 0:
                await lookup_btn.first.click()
                logger.info("Clicked blue decodeButton (fallback 1)")
            else:
                # Try second decodeButton
                all_lookup_btns = page.locator("input.decodeButton")
                count = await all_lookup_btns.count()
                logger.info(f"Found {count} total decodeButtons")
                if count >= 2:
                    await all_lookup_btns.nth(1).click()
                    logger.info("Clicked second decodeButton (fallback 2)")
                elif count == 1:
                    await all_lookup_btns.first.click()
                    logger.info("Clicked only decodeButton (fallback 3)")
                else:
                    raise Exception("Could not find plate Lookup button")
        
        await random_delay(1500, 2500)
        
        # Check for errors
        error_msg = await self._check_for_errors(page, selectors)
        if error_msg:
            return {"success": False, "error": error_msg}
        
        return {"success": True}
    
    async def _check_for_errors(self, page, selectors: Dict) -> Optional[str]:
        """Check for error messages after lookup."""
        error_selector = selectors.get("error_message", ".error, .errorMessage, .alert-danger")
        
        error_el = page.locator(error_selector)
        if await error_el.count() > 0:
            error_text = await error_el.first.inner_text()
            if error_text.strip():
                return error_text.strip()
        
        # Check for "not found" type messages
        not_found = page.locator("text=/not found|no vehicle|invalid|no results/i")
        if await not_found.count() > 0:
            return "Vehicle not found for this VIN/plate"
        
        return None
    
    async def _click_use_this_vehicle(self, page, selectors: Dict) -> None:
        """Click the Use This Vehicle button to confirm selection."""
        use_btn = selectors.get("use_vehicle_button", "input[value='Use This Vehicle'], button:has-text('Use This Vehicle')")
        
        btn = page.locator(use_btn)
        if await btn.count() > 0:
            # Wait for it to be enabled
            await page.wait_for_selector(f"{use_btn}:not([disabled])", timeout=5000)
            await btn.click()
            await random_delay(500, 1000)
            logger.info("Clicked Use This Vehicle")
        else:
            logger.warning("Use This Vehicle button not found - vehicle may already be selected")
    
    async def _extract_vehicle_info(
        self, 
        page, 
        selectors: Dict,
        pre_captured_vin: Optional[str] = None,
        pre_captured_vehicle_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract decoded vehicle info from the page header.
        
        Args:
            page: Playwright page
            selectors: Selector config
            pre_captured_vin: VIN captured before clicking "Use This Vehicle"
            pre_captured_vehicle_text: Vehicle text from accordion header
        """
        # Use pre-captured values first (most reliable)
        vehicle_text = pre_captured_vehicle_text or ""
        vin_value = pre_captured_vin or ""
        
        logger.info(f"Starting extraction with pre-captured VIN={vin_value}, vehicle_text={vehicle_text}")
        
        # If we don't have VIN yet, try to get it from input (panel might still be visible)
        if not vin_value:
            try:
                vin_input = page.locator("input#Vin, input.vin").first
                if await vin_input.count() > 0:
                    vin_value = await vin_input.input_value()
                    if vin_value and len(vin_value) == 17:
                        logger.info(f"Extracted VIN from input: {vin_value}")
                    else:
                        vin_value = ""
            except Exception as e:
                logger.debug(f"Could not get VIN from input: {e}")
        
        # Wait for page to update after clicking Use This Vehicle
        await random_delay(500, 1000)
        
        # Try to get vehicle text from header bar (most reliable after selection)
        # The header shows: "Change Vehicle | 2014 Chevrolet Cruze 1.4L LT"
        # If we already have vehicle text from pre-capture, use it
        # Otherwise try to find it from the page
        if not vehicle_text:
            selectors_to_try = [
                # Header bar with vehicle info (after Change Vehicle button)
                ".vehicleHeader span, .vehicleHeader div",
                "#vehicleInfo, .vehicle-info",
                # The URL contains vehicle info - extract from page title or breadcrumb
                ".breadcrumb",
                # Accordion header that shows vehicle after decode
                ".header:has(h1:has-text('VIN or Plate')) span",
                "div.header h1 + span",
            ]
            
            for selector in selectors_to_try:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        text = await el.inner_text()
                        text = text.strip()
                        # Skip if it's just "Change Vehicle" or empty
                        if text and len(text) > 10 and "Change Vehicle" not in text:
                            # Check if it looks like a vehicle (has a year)
                            if re.search(r'\d{4}\s+\w+', text):
                                vehicle_text = text
                                logger.info(f"Found vehicle text from {selector}: {vehicle_text}")
                                break
                except Exception as e:
                    logger.debug(f"Selector {selector} failed: {e}")
                    continue
        
        # If still no vehicle text, try the URL (it contains vehicle info)
        if not vehicle_text:
            try:
                url = page.url
                # URL format: .../Index#2014|Chevrolet|Cruze|1.4%20B|LT|...
                if "#" in url:
                    hash_part = url.split("#")[1]
                    parts = hash_part.split("|")
                    if len(parts) >= 3:
                        year = parts[0] if parts[0].isdigit() and len(parts[0]) == 4 else None
                        make = parts[1] if len(parts) > 1 else None
                        model = parts[2] if len(parts) > 2 else None
                        if year and make:
                            # URL decode
                            import urllib.parse
                            vehicle_text = f"{year} {urllib.parse.unquote(make)} {urllib.parse.unquote(model) if model else ''}"
                            logger.info(f"Extracted vehicle from URL: {vehicle_text}")
            except Exception as e:
                logger.debug(f"URL extraction failed: {e}")
        
        logger.info(f"Vehicle display text: {vehicle_text}")
        
        # Parse the vehicle text
        # Expected format: "2014 Chevrolet Cruze 1.4L" or "2014 Chevrolet Cruze 1.4L LT"
        result = {
            "year": None,
            "make": None,
            "model": None,
            "engine": None,
            "submodel": None,
            "vin": vin_value.upper() if vin_value and len(vin_value) == 17 else None
        }
        
        if vehicle_text:
            # Handle both formats:
            # 1. With spaces: "2014 Chevrolet Cruze 1.4L LT"
            # 2. Without spaces (from accordion): "2014ChevroletCruze1.4LLT"
            
            # First, try to add spaces if text looks concatenated (has year followed by uppercase)
            # Pattern: 2014ChevroletCruze1.4LLT -> 2014 Chevrolet Cruze 1.4L LT
            if re.match(r'^\d{4}[A-Z]', vehicle_text):
                # Insert space after year
                vehicle_text = re.sub(r'^(\d{4})([A-Z])', r'\1 \2', vehicle_text)
                # Insert spaces before uppercase letters (but not consecutive ones)
                vehicle_text = re.sub(r'([a-z])([A-Z])', r'\1 \2', vehicle_text)
                # Insert space before engine spec like "1.4L"
                vehicle_text = re.sub(r'([A-Za-z])(\d+\.\d+L)', r'\1 \2', vehicle_text)
                # Insert space after engine spec 
                vehicle_text = re.sub(r'(\d+\.\d+L)([A-Z])', r'\1 \2', vehicle_text)
                logger.info(f"Normalized vehicle text: {vehicle_text}")
            
            # Now parse with spaces
            year_match = re.search(r'^(\d{4})\s*', vehicle_text)
            if year_match:
                result["year"] = year_match.group(1)
                remaining = vehicle_text[year_match.end():].strip()
                
                # Split remaining into parts
                parts = remaining.split()
                if len(parts) >= 2:
                    result["make"] = parts[0]
                    result["model"] = parts[1]
                    
                    # Look for engine spec (e.g., "1.4L", "5.0L", "V6")
                    for i, part in enumerate(parts[2:], start=2):
                        if re.match(r'^\d+\.\d+L$', part, re.I) or re.match(r'^V\d$', part, re.I):
                            result["engine"] = part
                            # Remaining parts might be submodel
                            if i + 1 < len(parts):
                                result["submodel"] = ' '.join(parts[i+1:])
                            break
                    else:
                        # No engine found, rest might be submodel
                        if len(parts) > 2:
                            result["submodel"] = ' '.join(parts[2:])
                elif len(parts) == 1:
                    result["make"] = parts[0]
        
        return result
