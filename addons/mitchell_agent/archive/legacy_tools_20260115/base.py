"""
Base classes for Mitchell Agent tools.
"""
import asyncio
import json
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime

from .. import selectors as SEL


# Global timeout for tool execution (2 minutes)
TOOL_TIMEOUT_SECONDS = 120


class ToolTimeoutError(Exception):
    """Raised when a tool execution exceeds the timeout."""
    pass


async def random_delay(min_ms: int = 300, max_ms: int = 800) -> None:
    """Add a random delay to simulate human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


@dataclass
class Vehicle:
    """Vehicle specification for tool queries."""
    year: int
    make: str
    model: str
    engine: str
    submodel: Optional[str] = None
    options: Optional[Dict[str, str]] = None  # e.g., {"drive_type": "4WD", "transmission_code": "..."}
    
    def __str__(self) -> str:
        parts = [str(self.year), self.make, self.model, self.engine]
        if self.submodel:
            parts.append(self.submodel)
        if self.options:
            parts.append(str(self.options))
        return " ".join(parts)
    
    def to_selector_format(self) -> Dict[str, str]:
        """Format for ShopKeyPro vehicle selector."""
        result = {
            "year": str(self.year),
            "make": self.make,
            "model": self.model,
            "engine": self.engine,
            "submodel": self.submodel or ""
        }
        if self.options:
            result["options"] = self.options
        return result


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    source: Optional[str] = None  # e.g., "fluid_capacities", "dtc_index", "1search"
    cached: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    needs_more_info: bool = False  # True if additional info needed from user (deprecated - prefer auto_selected_options)
    required_options: Optional[Dict[str, List[str]]] = None  # e.g., {"drive_type": ["4WD", "RWD"]} (deprecated)
    images: Optional[List[Dict[str, str]]] = None  # List of {"name": "...", "base64": "...", "mime_type": "image/png"}
    auto_selected_options: Optional[Dict[str, str]] = None  # Options that were auto-selected, e.g., {"drive_type": "4WD"}
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, default=str)


class MitchellTool(ABC):
    """
    Base class for all Mitchell Agent tools.
    
    Each tool implements a specific data retrieval pattern from ShopKeyPro.
    
    All tool executions are wrapped with a 2-minute timeout. If the tool
    doesn't complete within 2 minutes, it will return an error and the
    agent should log out.
    """
    
    # Tool metadata (override in subclasses)
    name: str = "base_tool"
    description: str = "Base Mitchell tool"
    tier: int = 1  # 1=high-level, 2=search, 3=browse, 4=raw
    
    # Debug screenshot directory
    DEBUG_SCREENSHOT_DIR = Path("/tmp/navigator_screenshots")
    
    def __init__(self, browser_controller=None, debug_screenshots: bool = False):
        """
        Initialize tool with optional browser controller.
        
        Args:
            browser_controller: Browser automation controller (Playwright-based)
            debug_screenshots: If True, save screenshots at each step to DEBUG_SCREENSHOT_DIR
        """
        self.browser = browser_controller
        self.debug_screenshots = debug_screenshots
        self._screenshot_counter = 0
        self._auto_selected_options: Dict[str, str] = {}  # Track auto-selected vehicle options
    
    async def save_debug_screenshot(self, step_name: str) -> Optional[str]:
        """
        Save a debug screenshot if debug_screenshots is enabled.
        
        Screenshots are saved to /tmp/navigator_screenshots/ with format:
        {tool_name}_{counter:02d}_{step_name}.png
        
        Args:
            step_name: Description of the current step (e.g., "after_vehicle_select")
            
        Returns:
            Path to saved screenshot, or None if not saved
        """
        if not self.debug_screenshots or not self.browser:
            return None
        
        try:
            # Ensure directory exists
            self.DEBUG_SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            self._screenshot_counter += 1
            safe_step = step_name.replace(" ", "_").replace("/", "_")[:50]
            filename = f"{self.name}_{self._screenshot_counter:02d}_{safe_step}.png"
            filepath = self.DEBUG_SCREENSHOT_DIR / filename
            
            # Save screenshot
            await self.browser.screenshot(path=str(filepath))
            print(f"[{self.name}] 📸 Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[{self.name}] ⚠ Screenshot failed: {e}")
            return None

    @abstractmethod
    async def execute(self, vehicle: Vehicle, **kwargs) -> ToolResult:
        """
        Execute the tool for the given vehicle.
        
        Args:
            vehicle: Vehicle specification
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with data or error
        """
        pass
    
    async def run_with_timeout(self, vehicle: Vehicle, timeout: int = TOOL_TIMEOUT_SECONDS, **kwargs) -> ToolResult:
        """
        Execute the tool with a timeout watchdog.
        
        If the tool doesn't complete within the timeout (default 2 minutes),
        it will return an error result and the caller should log out.
        
        Args:
            vehicle: Vehicle specification
            timeout: Timeout in seconds (default: 120 = 2 minutes)
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with data, error, or timeout error
        """
        try:
            result = await asyncio.wait_for(
                self.execute(vehicle, **kwargs),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            error_msg = f"Tool '{self.name}' timed out after {timeout} seconds. Agent should log out."
            print(f"[TIMEOUT] ⚠ {error_msg}")
            return ToolResult(
                success=False,
                error=error_msg,
                source=self.name
            )
        except Exception as e:
            error_msg = f"Tool '{self.name}' failed with error: {str(e)}"
            print(f"[ERROR] {error_msg}")
            return ToolResult(
                success=False,
                error=error_msg,
                source=self.name
            )
    
    def get_selector(self, path: str) -> str:
        """
        Get a selector by dot-notation path.
        
        Example: get_selector("module_selector.maintenance")
                 get_selector("quick_access.fluid_capacities")
        """
        parts = path.split(".")
        if len(parts) == 2:
            return SEL.get_selector(parts[0], parts[1])
        return ""
    
    async def ensure_vehicle_selected(self, vehicle: Vehicle) -> bool:
        """
        Ensure the given vehicle is selected in ShopKeyPro.
        
        Flow: Year -> Make -> Model -> Engine -> (Submodel if shown) -> Options -> Use This Vehicle
        
        This method handles:
        - Detecting if vehicle is already selected
        - Selecting year/make/model/engine/submodel
        - Detecting and handling required options (drive type, etc.)
        - Returning False with pending_required_options if user input is needed
        
        Returns True if vehicle selection successful.
        Returns False if selection failed OR if more info is required.
        Call get_pending_required_options() to check what info is needed.
        """
        if not self.browser:
            return False
        
        # Clear any pending required options from previous attempt
        self._pending_required_options = None
        self._auto_selected_options = {}  # Reset auto-selected options
        
        try:
            # Use hardcoded selectors from SEL module
            vs = SEL.VEHICLE_SELECTOR
            
            # FIRST: Check if a vehicle selection modal/panel is open with required options
            # This MUST be checked before "Change Vehicle" button because the modal overlays everything
            options_modal_open = await self._check_vehicle_selector_open()
            if options_modal_open:
                print(f"[Vehicle] Vehicle selector panel is open - checking for required selections...")
                required_opts = await self._detect_required_options()
                if required_opts:
                    # If vehicle has options provided, try to select them
                    if vehicle.options:
                        print(f"[Vehicle] Attempting to select provided options: {vehicle.options}")
                        selected = await self._select_provided_options(vehicle.options)
                        if selected:
                            # Try clicking Use This Vehicle again
                            use_button = vs.get("use_vehicle_button", "input[data-action='SelectComplete']")
                            await random_delay(500, 1000)
                            await self.browser.click(use_button, timeout=5000)
                            await random_delay(2000, 3500)
                            # Verify selector closed
                            still_open = await self._check_vehicle_selector_open()
                            if not still_open:
                                print(f"[Vehicle] ✓ Vehicle selected with options: {vehicle}")
                                return True
                            # Still open - may need more options
                            required_opts = await self._detect_required_options()
                    
                    # Options required but not provided - AUTO-SELECT first available
                    if required_opts:
                        print(f"[Vehicle] ⚠ Required options detected - auto-selecting first available...")
                        await self._auto_select_first_options()
                        # Try clicking Use This Vehicle
                        use_button = vs.get("use_vehicle_button", "input[data-action='SelectComplete']")
                        await random_delay(500, 1000)
                        await self.browser.click(use_button, timeout=5000)
                        await random_delay(2000, 3500)
                        still_open = await self._check_vehicle_selector_open()
                        if not still_open:
                            print(f"[Vehicle] ✓ Vehicle selected with auto-selected options")
                            return True
            
            # SECOND: Check if a vehicle is already fully selected (no modal blocking)
            button_sel = vs.get("select_vehicle_button", "#vehicleSelectorButton")
            try:
                button = await self.browser.query_selector(button_sel)
                if button:
                    button_text = await button.inner_text()
                    # Check if vehicle info is in the button text (e.g., "2018 Ford F-150 5.0L")
                    vehicle_str = f"{vehicle.year} {vehicle.make} {vehicle.model}"
                    if vehicle_str in button_text:
                        print(f"[Vehicle] ✓ Vehicle already selected: {vehicle}")
                        # Wait for page to fully stabilize after vehicle selection
                        await asyncio.sleep(2)
                        return True
                    # If button says "Change Vehicle" AND no modal is blocking, vehicle is selected
                    if "Change Vehicle" in button_text:
                        print(f"[Vehicle] ✓ Vehicle already selected (Change Vehicle button visible)")
                        # Wait for page to fully stabilize after vehicle selection
                        await asyncio.sleep(2)
                        return True
            except Exception as e:
                print(f"[Vehicle] Could not check button: {e}")
            
            # After login, ShopKeyPro shows the year selector automatically
            # Check if year tab is already visible
            year_tab = vs.get("year_tab", "#qualifierTypeSelector li.year")
            
            try:
                year_elem = await self.browser.query_selector(year_tab)
                year_visible = year_elem and await year_elem.is_visible()
            except:
                year_visible = False
            
            if not year_visible:
                # Need to open vehicle selector
                button_sel = vs.get("select_vehicle_button", "#vehicleSelectorButton")
                print(f"[Vehicle] Opening vehicle selector...")
                await self.browser.click(button_sel, timeout=5000)
                await asyncio.sleep(1.5)
            else:
                print(f"[Vehicle] Vehicle selector already open")
            
            # Select Year
            print(f"[Vehicle] Selecting year: {vehicle.year}")
            await random_delay(400, 900)
            await self.browser.click(year_tab, timeout=5000)
            await random_delay(600, 1200)
            year_value = f"#qualifierValueSelector li.qualifier:has-text('{vehicle.year}')"
            await self.browser.click(year_value, timeout=5000)
            await random_delay(800, 1500)
            
            # Select Make
            make_tab = vs.get("make_tab", "#qualifierTypeSelector li.make")
            print(f"[Vehicle] Selecting make: {vehicle.make}")
            await random_delay(400, 900)
            await self.browser.click(make_tab, timeout=5000)
            await random_delay(600, 1200)
            make_value = f"#qualifierValueSelector li.qualifier:has-text('{vehicle.make}')"
            await self.browser.click(make_value, timeout=5000)
            await random_delay(800, 1500)
            
            # Select Model
            model_tab = vs.get("model_tab", "#qualifierTypeSelector li.model")
            print(f"[Vehicle] Selecting model: {vehicle.model}")
            await random_delay(400, 900)
            await self.browser.click(model_tab, timeout=5000)
            await random_delay(600, 1200)
            model_value = f"#qualifierValueSelector li.qualifier:has-text('{vehicle.model}')"
            await self.browser.click(model_value, timeout=5000)
            await random_delay(800, 1500)
            
            # Select Engine (if provided and tab exists)
            engine_tab = vs.get("engine_tab", "#qualifierTypeSelector li.engine")
            try:
                engine_elem = await self.browser.query_selector(engine_tab)
                if engine_elem and await engine_elem.is_visible():
                    if vehicle.engine:
                        print(f"[Vehicle] Selecting engine: {vehicle.engine}")
                        await random_delay(400, 900)
                        await self.browser.click(engine_tab, timeout=5000)
                        await random_delay(600, 1200)
                        engine_value = f"#qualifierValueSelector li.qualifier:has-text('{vehicle.engine}')"
                        await self.browser.click(engine_value, timeout=5000)
                        await random_delay(800, 1500)
                    else:
                        # Click first available engine
                        print(f"[Vehicle] Selecting first available engine...")
                        await random_delay(400, 900)
                        await self.browser.click(engine_tab, timeout=5000)
                        await random_delay(600, 1200)
                        await self.browser.click("#qualifierValueSelector li.qualifier:first-child", timeout=5000)
                        await random_delay(800, 1500)
            except Exception as e:
                print(f"[Vehicle] Engine tab not found or not needed: {e}")
            
            # Check for submodel tab and select if present
            submodel_tab = vs.get("submodel_tab", "#qualifierTypeSelector li.submodel")
            try:
                submodel_elem = await self.browser.query_selector(submodel_tab)
                if submodel_elem and await submodel_elem.is_visible():
                    if vehicle.submodel:
                        print(f"[Vehicle] Selecting submodel: {vehicle.submodel}")
                        await random_delay(400, 900)
                        await self.browser.click(submodel_tab, timeout=5000)
                        await random_delay(600, 1200)
                        submodel_value = f"#qualifierValueSelector li.qualifier:has-text('{vehicle.submodel}')"
                        await self.browser.click(submodel_value, timeout=5000)
                        await random_delay(800, 1500)
                    else:
                        # Click first available submodel
                        print(f"[Vehicle] Selecting first available submodel...")
                        await random_delay(400, 900)
                        await self.browser.click(submodel_tab, timeout=5000)
                        await random_delay(600, 1200)
                        await self.browser.click("#qualifierValueSelector li.qualifier:first-child", timeout=5000)
                        await random_delay(800, 1500)
            except Exception as e:
                print(f"[Vehicle] Submodel tab not found or not needed: {e}")
            
            # Handle vehicle options if provided - auto-selects first option if required but not provided
            await self._handle_vehicle_options(vehicle, vs)
            
            # Click Use This Vehicle button
            use_button = vs.get("use_vehicle_button", "input[data-action='SelectComplete']")
            print(f"[Vehicle] Clicking 'Use This Vehicle'...")
            await random_delay(500, 1000)
            await self.browser.click(use_button, timeout=5000)
            await random_delay(2000, 3500)  # Wait for vehicle to load
            
            # DEFINITIVE CHECK: Look for "Highlighted sections are required." message
            # If options are still required, auto-select first available and retry
            required_options_needed = await self._check_required_options_needed()
            if required_options_needed:
                print(f"[Vehicle] ⚠ 'Highlighted sections are required.' detected - auto-selecting...")
                
                # CAPTURE ACTUAL DOM STRUCTURE for debugging
                await self._capture_options_dom_structure()
                
                # Auto-select first available options
                await self._auto_select_first_options()
                
                # Try clicking Use This Vehicle again
                await random_delay(500, 1000)
                await self.browser.click(use_button, timeout=5000)
                await random_delay(2000, 3500)
                
                # Check if still stuck
                still_required = await self._check_required_options_needed()
                if still_required:
                    # Last resort: try to click any visible option and retry
                    print(f"[Vehicle] ⚠ Still requires options - clicking first visible qualifier...")
                    try:
                        await self.browser.click("#qualifierValueSelector li.qualifier:first-child", timeout=2000)
                        await random_delay(500, 800)
                        await self.browser.click(use_button, timeout=5000)
                        await random_delay(2000, 3500)
                    except:
                        pass
            
            self._pending_required_options = None
            print(f"[Vehicle] ✓ Vehicle selected: {vehicle}")
            if self._auto_selected_options:
                print(f"[Vehicle] ℹ Auto-selected options: {self._auto_selected_options}")
            return True
            
        except Exception as e:
            print(f"Error selecting vehicle: {e}")
            return False
    
    async def _capture_options_dom_structure(self) -> None:
        """Capture and log the DOM structure of the vehicle options panel for debugging."""
        if not self.browser:
            return
        
        try:
            dom_info = await self.browser.evaluate("""
                () => {
                    const info = {
                        driveTypeSection: null,
                        allClickableOptions: [],
                        highlightedSection: null
                    };
                    
                    // Find the DRIVE TYPE section and its children
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent?.trim() || '';
                        
                        // Find DRIVE TYPE header
                        if (text === 'DRIVE TYPE:' || text.startsWith('DRIVE TYPE')) {
                            info.driveTypeSection = {
                                tag: el.tagName,
                                className: el.className,
                                id: el.id,
                                parentTag: el.parentElement?.tagName,
                                parentClass: el.parentElement?.className,
                                innerHTML: el.outerHTML.substring(0, 500)
                            };
                        }
                        
                        // Find 4WD and RWD elements specifically
                        if (text === '4WD' || text === 'RWD' || text === 'AWD' || text === 'FWD' || text === '2WD') {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                info.allClickableOptions.push({
                                    text: text,
                                    tag: el.tagName,
                                    className: el.className,
                                    id: el.id,
                                    parentTag: el.parentElement?.tagName,
                                    parentClass: el.parentElement?.className,
                                    grandparentTag: el.parentElement?.parentElement?.tagName,
                                    grandparentClass: el.parentElement?.parentElement?.className,
                                    outerHTML: el.outerHTML.substring(0, 300)
                                });
                            }
                        }
                    }
                    
                    // Find the highlighted/light-blue section
                    const highlighted = document.querySelector('[style*="rgb(198, 217, 241)"], [style*="#C6D9F1"], [style*="background"]');
                    if (highlighted) {
                        info.highlightedSection = {
                            tag: highlighted.tagName,
                            className: highlighted.className,
                            innerHTML: highlighted.innerHTML.substring(0, 1000)
                        };
                    }
                    
                    return info;
                }
            """)
            
            print(f"\n[DOM CAPTURE] ========== OPTIONS PANEL STRUCTURE ==========")
            print(f"[DOM CAPTURE] DRIVE TYPE section: {dom_info.get('driveTypeSection')}")
            print(f"[DOM CAPTURE] Clickable options found: {len(dom_info.get('allClickableOptions', []))}")
            for opt in dom_info.get('allClickableOptions', []):
                print(f"[DOM CAPTURE]   {opt.get('text')}: <{opt.get('tag')}> class='{opt.get('className')}' parent=<{opt.get('parentTag')}> class='{opt.get('parentClass')}'")
                print(f"[DOM CAPTURE]     outerHTML: {opt.get('outerHTML')}")
            print(f"[DOM CAPTURE] =================================================\n")
            
        except Exception as e:
            print(f"[DOM CAPTURE] Error capturing DOM: {e}")
    
    async def _handle_vehicle_options(self, vehicle: Vehicle, vs: dict) -> Optional[Dict[str, List[str]]]:
        """
        Handle vehicle options tab - select provided options OR auto-select first available option.
        
        BEHAVIOR: If options are required but not provided, we AUTO-SELECT the first available
        option instead of asking for clarification. The technician can re-query with specific
        options if needed.
        
        Args:
            vehicle: Vehicle with optional options dict
            vs: Vehicle selector config dict
            
        Returns:
            None (always continues, never returns required_options for clarification)
        """
        options_tab = vs.get("options_tab", "#qualifierTypeSelector li.options")
        try:
            options_elem = await self.browser.query_selector(options_tab)
            if not options_elem or not await options_elem.is_visible():
                return None  # No options tab
            
            print(f"[Vehicle] Options tab found...")
            await random_delay(400, 900)
            await self.browser.click(options_tab, timeout=5000)
            await random_delay(800, 1200)
            
            # If vehicle has options specified, try to select them
            if vehicle.options:
                for opt_name, opt_value in vehicle.options.items():
                    print(f"[Vehicle] Selecting option {opt_name}: {opt_value}")
                    try:
                        await self.browser.click(f"text={opt_value}", timeout=3000)
                        await random_delay(500, 800)
                    except Exception as e:
                        print(f"[Vehicle] Could not select option {opt_name}={opt_value}: {e}")
                return None  # Options were provided, attempted to select
            
            # No options provided - AUTO-SELECT first available option for each required group
            await self._auto_select_first_options()
            return None  # Never return required_options - always continue
            
        except Exception as e:
            print(f"[Vehicle] Options handling error: {e}")
            return None
    
    async def _auto_select_first_options(self) -> None:
        """
        Auto-select the first available option for each required option group.
        
        This enables the agent to proceed without user clarification. The selected
        options are stored in self._auto_selected_options for reporting.
        """
        if not self.browser:
            return
        
        try:
            # Use hardcoded selectors from SEL module
            vo = SEL.VEHICLE_OPTIONS
            
            # Check for option groups (div.optionGroup) - these contain required selections
            option_groups = await self.browser.query_selector_all(vo.get("option_group", "div.optionGroup"))
            
            for group in option_groups:
                try:
                    # Get the option group heading (e.g., "DRIVE TYPE:")
                    heading_elem = await group.query_selector(vo.get("option_group_title", "div.heading h1") or "h1")
                    heading_text = await heading_elem.inner_text() if heading_elem else "unknown"
                    heading_key = heading_text.lower().replace(":", "").replace(" ", "_").strip()
                    
                    # Check if already selected (has a value in h2)
                    value_elem = await group.query_selector(vo.get("option_group_value", "div.heading h2") or "h2")
                    existing_value = await value_elem.inner_text() if value_elem else ""
                    if existing_value.strip():
                        print(f"[Vehicle] Option {heading_text} already has value: {existing_value}")
                        continue
                    
                    # Find the first clickable option in this group
                    first_option = await group.query_selector(vo.get("option_item", "ul li.qualifier") or "li.qualifier")
                    if first_option:
                        option_text = await first_option.inner_text()
                        print(f"[Vehicle] 🔧 Auto-selecting first option for {heading_text}: {option_text}")
                        await random_delay(300, 600)
                        await first_option.click()
                        await random_delay(500, 800)
                        # Record what we selected
                        self._auto_selected_options[heading_key] = option_text.strip()
                    
                except Exception as e:
                    print(f"[Vehicle] Error processing option group: {e}")
                    continue
            
            if self._auto_selected_options:
                print(f"[Vehicle] ✓ Auto-selected options: {self._auto_selected_options}")
                
        except Exception as e:
            print(f"[Vehicle] Auto-select error: {e}")
    
    async def _detect_required_options(self) -> Optional[Dict[str, List[str]]]:
        """
        Detect required vehicle options and their available values.
        
        Looks for the options panel in ShopKeyPro which shows:
        - "Highlighted sections are required." message
        - Expandable sections like "DRIVE TYPE:" with options like "4WD", "RWD"
        - Highlighted (light blue/yellow) backgrounds indicating required selection
        
        Returns:
            Dict mapping option names to available values, or None if no required options.
            Example: {"drive_type": ["4WD", "RWD"], "transfer_case_type": ["Electronic", "Manual"]}
        """
        if not self.browser:
            return None
        
        try:
            # Use JavaScript to extract required options from the options panel
            required_options = await self.browser.evaluate("""
                () => {
                    const result = {};
                    
                    // Check if we're in the options panel (has "Highlighted sections are required" message)
                    const pageText = document.body.innerText || '';
                    const hasRequiredMessage = pageText.includes('Highlighted sections are required');
                    
                    if (!hasRequiredMessage) {
                        // Also check if Options tab is active
                        const optionsTab = document.querySelector('#qualifierTypeSelector li.options.active, #qualifierTypeSelector li.options.selected');
                        if (!optionsTab) {
                            return null;  // Not on options page
                        }
                    }
                    
                    // Look for expandable option sections
                    // The structure is typically:
                    //   ▼ DRIVE TYPE:
                    //      4WD (highlighted if selectable)
                    //      RWD
                    
                    // Strategy 1: Find all option category headers and their values
                    // Headers contain text like "DRIVE TYPE:", "TRANSFER CASE TYPE:", etc.
                    const optionCategories = [
                        { name: 'drive_type', patterns: ['DRIVE TYPE', 'DRIVE'] },
                        { name: 'transfer_case_type', patterns: ['TRANSFER CASE TYPE', 'TRANSFER CASE'] },
                        { name: 'transmission_control_type', patterns: ['TRANSMISSION CONTROL TYPE', 'TRANSMISSION CONTROL'] },
                        { name: 'transmission_code', patterns: ['TRANSMISSION CODE'] },
                        { name: 'body_style', patterns: ['BODY STYLE'] },
                        { name: 'fuel_type', patterns: ['FUEL TYPE'] },
                    ];
                    
                    // Find highlighted/expanded sections - they have a light blue/yellow background
                    // and contain the option values to choose from
                    const highlightedSections = document.querySelectorAll(
                        '[style*="background"][style*="rgb(198, 217, 241)"], ' +  // Light blue
                        '[style*="background"][style*="#C6D9F1"], ' +
                        '[style*="background"][style*="rgb(255, 255, 204)"], ' +  // Yellow
                        '[style*="background"][style*="#FFFFCC"], ' +
                        '.highlighted, .required, .selected-section'
                    );
                    
                    // Look for option values (4WD, RWD, etc.) in the qualifier value selector
                    const qualifierValues = document.querySelectorAll('#qualifierValueSelector li');
                    const visibleValues = [];
                    for (const item of qualifierValues) {
                        const text = item.textContent?.trim();
                        if (text && text.length > 0 && text.length < 30) {
                            visibleValues.push(text);
                        }
                    }
                    
                    // Try to determine which category is currently active/required
                    // by looking at what's highlighted or expanded
                    let activeCategory = null;
                    
                    // Check page text for category headers that are expanded
                    for (const cat of optionCategories) {
                        for (const pattern of cat.patterns) {
                            // Look for the pattern followed by a colon (indicating it's a header)
                            const regex = new RegExp(pattern + '\\s*:', 'i');
                            if (regex.test(pageText)) {
                                // Check if this section appears to be expanded (has values below it)
                                const driveValues = ['4WD', 'RWD', 'AWD', 'FWD', '2WD'];
                                const hasValues = driveValues.some(v => 
                                    pageText.includes(v) && 
                                    document.querySelector(`li:has-text("${v}"), *:contains("${v}")`)
                                );
                                if (hasValues && cat.name === 'drive_type') {
                                    activeCategory = cat.name;
                                    break;
                                }
                            }
                        }
                        if (activeCategory) break;
                    }
                    
                    // Specifically look for drive type options since they're most common
                    const driveOptions = [];
                    ['4WD', 'RWD', 'AWD', 'FWD', '2WD'].forEach(opt => {
                        // Check if this option exists as clickable text
                        const elements = document.querySelectorAll('li, span, div, a');
                        for (const el of elements) {
                            const text = el.textContent?.trim();
                            if (text === opt && el.offsetParent !== null) {
                                // Verify it's actually clickable/visible
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    driveOptions.push(opt);
                                    break;
                                }
                            }
                        }
                    });
                    
                    // If we found drive options, that's what's required
                    if (driveOptions.length > 0) {
                        result['drive_type'] = driveOptions;
                    }
                    
                    // If we have visible qualifier values but no drive options,
                    // use those with best-guess category
                    if (visibleValues.length > 0 && Object.keys(result).length === 0) {
                        result[activeCategory || 'drive_type'] = visibleValues;
                    }
                    
                    // Debug: log what we found
                    console.log('[_detect_required_options] Found:', JSON.stringify(result));
                    
                    return Object.keys(result).length > 0 ? result : null;
                }
            """)
            
            return required_options
            
        except Exception as e:
            print(f"[Vehicle] Error detecting required options: {e}")
            return None
    
    async def _check_vehicle_selector_open(self) -> bool:
        """
        Check if the vehicle selection panel is open with required options.
        
        The definitive trigger is the text "Highlighted sections are required."
        which appears when the Options modal needs user input.
        
        Returns True if vehicle selector is open AND requires user input.
        """
        if not self.browser:
            return False
        
        try:
            # Check for the definitive trigger: "Highlighted sections are required."
            # This text only appears when the Options modal is open and needs input
            result = await self.browser.evaluate("""
                (() => {
                    // Primary check: Look for the "Highlighted sections are required." message
                    const pageText = document.body.innerText || '';
                    const hasRequiredMessage = pageText.includes('Highlighted sections are required');
                    
                    if (hasRequiredMessage) {
                        return true;  // Definitive trigger
                    }
                    
                    // Secondary check: Vehicle selector panel elements visible
                    const yearTab = document.querySelector('#qualifierTypeSelector li.year');
                    const optionsTab = document.querySelector('#qualifierTypeSelector li.options');
                    const useVehicleBtn = document.querySelector('input[data-action="SelectComplete"]');
                    
                    const isVisible = (el) => {
                        if (!el) return false;
                        const style = window.getComputedStyle(el);
                        return style.display !== 'none' && style.visibility !== 'hidden' && el.offsetParent !== null;
                    };
                    
                    // Only return true if selector is visible (but this is less definitive)
                    return isVisible(yearTab) || isVisible(optionsTab) || isVisible(useVehicleBtn);
                })()
            """)
            return result
        except Exception as e:
            print(f"[Vehicle] Error checking vehicle selector: {e}")
            return False
    
    async def _check_required_options_needed(self) -> bool:
        """
        Check specifically for the "Highlighted sections are required." message.
        
        This is the definitive indicator that the Options modal is open
        and the user needs to provide additional vehicle options.
        
        Returns True if required options message is visible.
        """
        if not self.browser:
            return False
        
        try:
            result = await self.browser.evaluate("""
                (() => {
                    const pageText = document.body.innerText || '';
                    return pageText.includes('Highlighted sections are required');
                })()
            """)
            return result
        except:
            return False
    
    async def _select_provided_options(self, options: Dict[str, str]) -> bool:
        """
        Select the provided vehicle options in the Options panel.
        
        Args:
            options: Dict mapping option names to values, e.g., {"drive_type": "4WD"}
            
        Returns:
            True if all options were selected successfully
        """
        if not self.browser or not options:
            return False
        
        try:
            # Use hardcoded selectors from SEL module
            vs = SEL.VEHICLE_SELECTOR
            
            # First make sure we're on the Options tab
            options_tab = vs.get("options_tab", "#qualifierTypeSelector li.options")
            try:
                options_elem = await self.browser.query_selector(options_tab)
                if options_elem and await options_elem.is_visible():
                    await random_delay(400, 800)
                    await self.browser.click(options_tab, timeout=5000)
                    await random_delay(600, 1000)
            except:
                pass
            
            # Try to select each provided option
            for opt_name, opt_value in options.items():
                print(f"[Vehicle] Selecting option {opt_name}: {opt_value}")
                
                # Try multiple strategies to find and click the option
                selected = False
                
                # Strategy 1: Click directly on the option text
                try:
                    # Look for the value as a list item
                    selector = f"#qualifierValueSelector li:has-text('{opt_value}')"
                    elem = await self.browser.query_selector(selector)
                    if elem and await elem.is_visible():
                        await random_delay(300, 600)
                        await elem.click()
                        await random_delay(500, 800)
                        selected = True
                        print(f"[Vehicle] ✓ Selected {opt_value} via list item")
                except Exception as e:
                    print(f"[Vehicle] Strategy 1 failed: {e}")
                
                # Strategy 2: Click on text directly
                if not selected:
                    try:
                        await self.browser.click(f"text={opt_value}", timeout=3000)
                        await random_delay(500, 800)
                        selected = True
                        print(f"[Vehicle] ✓ Selected {opt_value} via text click")
                    except Exception as e:
                        print(f"[Vehicle] Strategy 2 failed: {e}")
                
                # Strategy 3: Use JavaScript to find and click
                if not selected:
                    try:
                        clicked = await self.browser.evaluate(f"""
                            (() => {{
                                const target = '{opt_value}';
                                // Look in qualifier value selector
                                const items = document.querySelectorAll('#qualifierValueSelector li, li.qualifier');
                                for (const item of items) {{
                                    if (item.textContent.trim() === target) {{
                                        item.click();
                                        return true;
                                    }}
                                }}
                                // Also try any clickable element with that text
                                const all = document.querySelectorAll('li, a, span, div');
                                for (const el of all) {{
                                    if (el.textContent.trim() === target && el.offsetParent !== null) {{
                                        el.click();
                                        return true;
                                    }}
                                }}
                                return false;
                            }})()
                        """)
                        if clicked:
                            await random_delay(500, 800)
                            selected = True
                            print(f"[Vehicle] ✓ Selected {opt_value} via JS")
                    except Exception as e:
                        print(f"[Vehicle] Strategy 3 failed: {e}")
                
                if not selected:
                    print(f"[Vehicle] ✗ Could not select option {opt_name}={opt_value}")
                    return False
            
            return True
            
        except Exception as e:
            print(f"[Vehicle] Error selecting options: {e}")
            return False
    
    def get_pending_required_options(self) -> Optional[Dict[str, List[str]]]:
        """Get any required options that were detected but not provided (deprecated - prefer get_auto_selected_options)."""
        return getattr(self, '_pending_required_options', None)
    
    def get_auto_selected_options(self) -> Dict[str, str]:
        """
        Get any options that were auto-selected because they weren't specified.
        
        Returns:
            Dict mapping option name to selected value, e.g., {"drive_type": "4WD"}
        """
        return getattr(self, '_auto_selected_options', {})
    
    async def click_quick_access(self, item_id: str) -> bool:
        """
        Click a quick access panel item.
        
        Args:
            item_id: Selector ID like "#fluidsQuickAccess"
            
        Note: Each Quick Access item ID exists twice in the DOM:
        - #quickLinkRegion (visible) - the main panel
        - #quickAccessPanel (hidden) - a secondary panel
        We must use #quickLinkRegion prefix to avoid strict mode violations.
        """
        if not self.browser:
            return False
        
        try:
            # Build specific selector to avoid duplicate ID issues
            # The visible panel is #quickLinkRegion, not #quickAccessPanel
            if item_id.startswith("#") and not item_id.startswith("#quickLinkRegion"):
                specific_selector = f"#quickLinkRegion {item_id}"
            else:
                specific_selector = item_id
            
            await random_delay(400, 800)
            await self.browser.click(specific_selector, timeout=10000)
            await random_delay(1200, 2200)  # Wait for modal to load
            return True
        except Exception as e:
            print(f"Error clicking quick access {item_id}: {e}")
            return False
    
    async def close_modal(self) -> bool:
        """Close any open modal dialog."""
        if not self.browser:
            return False
        
        try:
            await random_delay(400, 800)
            await self.browser.evaluate(
                "document.querySelector('.modalDialogView .close')?.click()"
            )
            await random_delay(400, 800)
            return True
        except Exception:
            return False
    
    async def capture_screenshot(self, name: str = "screenshot") -> Optional[Dict[str, str]]:
        """
        Capture a screenshot of the current page/modal.
        
        Args:
            name: Name for the image
            
        Returns:
            Dict with name, base64 data, and mime_type, or None on failure
        """
        if not self.browser:
            return None
        
        try:
            import base64
            screenshot_bytes = await self.browser.screenshot()
            b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
            return {
                "name": name,
                "base64": b64_data,
                "mime_type": "image/png"
            }
        except Exception as e:
            print(f"[Tool] Error capturing screenshot: {e}")
            return None
    
    async def capture_element_screenshot(self, selector: str, name: str = "element") -> Optional[Dict[str, str]]:
        """
        Capture a screenshot of a specific element.
        
        Args:
            selector: CSS selector for the element
            name: Name for the image
            
        Returns:
            Dict with name, base64 data, and mime_type, or None on failure
        """
        if not self.browser:
            return None
        
        try:
            import base64
            element = await self.browser.query_selector(selector)
            if not element:
                return None
            screenshot_bytes = await element.screenshot()
            b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
            return {
                "name": name,
                "base64": b64_data,
                "mime_type": "image/png"
            }
        except Exception as e:
            print(f"[Tool] Error capturing element screenshot: {e}")
            return None
    
    async def extract_images_from_modal(self) -> List[Dict[str, str]]:
        """
        Extract all images from the current modal.
        
        Handles both regular <img> elements and SVG <object> elements.
        
        Returns:
            List of dicts with name, base64 data, and mime_type
        """
        if not self.browser:
            return []
        
        try:
            import base64
            images = []
            
            # First try to extract SVG objects (like wiring diagrams use)
            svg_data = await self.browser.evaluate("""
                () => {
                    const results = [];
                    const serializer = new XMLSerializer();
                    
                    // Look for SVG objects in the modal
                    const modal = document.querySelector('.modalDialogView');
                    if (!modal) return results;
                    
                    const svgObjects = modal.querySelectorAll('object.clsArticleSvg, object[data*=".svg"]');
                    
                    for (let i = 0; i < svgObjects.length; i++) {
                        const obj = svgObjects[i];
                        try {
                            const svgDoc = obj.contentDocument;
                            if (svgDoc) {
                                const svgEl = svgDoc.querySelector('svg');
                                if (svgEl) {
                                    const clone = svgEl.cloneNode(true);
                                    const svgString = serializer.serializeToString(clone);
                                    results.push({
                                        name: `Figure ${i + 1}`,
                                        svg: svgString,
                                        type: 'svg'
                                    });
                                }
                            }
                        } catch (e) {
                            console.error('Error extracting SVG:', e);
                        }
                    }
                    
                    return results;
                }
            """)
            
            # Convert SVGs to PNG using cairosvg if available
            if svg_data:
                try:
                    import cairosvg
                    for item in svg_data:
                        if item.get('svg'):
                            # Scale up for readability
                            png_bytes = cairosvg.svg2png(
                                bytestring=item['svg'].encode('utf-8'),
                                output_width=1200
                            )
                            b64_data = base64.b64encode(png_bytes).decode('utf-8')
                            images.append({
                                "name": item.get('name', 'SVG Image'),
                                "base64": b64_data,
                                "mime_type": "image/png"
                            })
                except ImportError:
                    print("[Tool] cairosvg not available for SVG conversion")
                except Exception as e:
                    print(f"[Tool] Error converting SVG to PNG: {e}")
            
            # Also find regular <img> elements in the modal
            img_elements = await self.browser.query_selector_all('.modalDialogView img')
            
            for i, img in enumerate(img_elements):
                try:
                    # Get image src
                    src = await img.get_attribute('src')
                    alt = await img.get_attribute('alt') or f"image_{i}"
                    
                    if src and src.startswith('data:'):
                        # Already base64
                        parts = src.split(',', 1)
                        if len(parts) == 2:
                            mime_match = parts[0].split(':')[1].split(';')[0] if ':' in parts[0] else 'image/png'
                            images.append({
                                "name": alt,
                                "base64": parts[1],
                                "mime_type": mime_match
                            })
                    elif src:
                        # Take screenshot of the element instead
                        screenshot_bytes = await img.screenshot()
                        b64_data = base64.b64encode(screenshot_bytes).decode('utf-8')
                        images.append({
                            "name": alt,
                            "base64": b64_data,
                            "mime_type": "image/png"
                        })
                except Exception as e:
                    print(f"[Tool] Error extracting image {i}: {e}")
                    continue
            
            return images
        except Exception as e:
            print(f"[Tool] Error extracting images from modal: {e}")
            return []

    async def extract_table(self, table_selector: str = ".modalDialogView table") -> List[Dict[str, str]]:
        """
        Extract data from a table in the current view.
        
        Returns list of dicts with column headers as keys.
        """
        if not self.browser:
            return []
        
        try:
            result = await self.browser.evaluate(f"""
                (() => {{
                    const table = document.querySelector('{table_selector}');
                    if (!table) return [];
                    
                    const rows = Array.from(table.querySelectorAll('tr'));
                    if (rows.length < 2) return [];
                    
                    // Get headers from first row
                    const headers = Array.from(rows[0].querySelectorAll('th, td'))
                        .map(cell => cell.textContent.trim());
                    
                    // Get data rows
                    const data = [];
                    for (let i = 1; i < rows.length; i++) {{
                        const cells = Array.from(rows[i].querySelectorAll('td'));
                        const row = {{}};
                        cells.forEach((cell, idx) => {{
                            if (headers[idx]) {{
                                row[headers[idx]] = cell.textContent.trim();
                            }}
                        }});
                        if (Object.keys(row).length > 0) {{
                            data.push(row);
                        }}
                    }}
                    return data;
                }})()
            """)
            return result if isinstance(result, list) else []
        except Exception as e:
            print(f"Error extracting table: {e}")
            return []


class MockBrowserController:
    """
    Mock browser controller for testing without real browser.
    
    Uses cached responses from test_data/ directory.
    """
    
    def __init__(self, test_data_dir: Optional[Path] = None):
        self.test_data_dir = test_data_dir or Path(__file__).parent.parent / "test_data"
        self.current_page = "home"
    
    async def evaluate(self, script: str) -> Any:
        """Execute JS and return mock result."""
        # Return appropriate mock data based on script content
        return None
    
    async def click(self, selector: str, timeout: int = 10000) -> None:
        """Mock click action."""
        print(f"Mock click: {selector}")
    
    async def type(self, selector: str, text: str) -> None:
        """Mock type action."""
        print(f"Mock type into {selector}: {text}")
