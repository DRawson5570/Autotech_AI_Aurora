"""
Mitchell Navigator Core
=======================
Main navigator class for ShopKeyPro automation.
"""

import asyncio
import json
import logging
import signal
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from .config import NavigatorConfig
from .delays import human_delay
from .quick_access import get_quick_access_selector
from .gemini import call_gemini, parse_gemini_response, build_extraction_prompt

# Load environment
load_dotenv()

log = logging.getLogger(__name__)


class MitchellNavigator:
    """
    Unified browser automation for ShopKeyPro.
    
    Handles:
    - Chrome launch with CDP
    - Playwright connection
    - Login/logout
    - Deterministic vehicle selection
    - Text-based data extraction with Gemini
    
    Usage:
        nav = MitchellNavigator()
        await nav.connect()
        
        data = await nav.get_data(
            year=2020, make="Toyota", model="Camry", engine="2.5L",
            data_type="fluid capacities"
        )
        
        await nav.logout()
        await nav.disconnect()
    """
    
    def __init__(self, config: Optional[NavigatorConfig] = None):
        """
        Initialize navigator.
        
        Args:
            config: Configuration (defaults to environment)
        """
        self.cfg = config or NavigatorConfig.from_env()
        
        # Playwright objects
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # Chrome process (if we launched it)
        self._chrome_process: Optional[subprocess.Popen] = None
        self._owns_chrome = False
        
        # State
        self._connected = False
        self._logged_in = False
        self._current_vehicle: Optional[Dict[str, str]] = None
    
    @property
    def page(self) -> Optional[Page]:
        """Get the current page."""
        return self._page
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to browser."""
        return self._connected
    
    @property
    def is_logged_in(self) -> bool:
        """Check if logged into ShopKeyPro."""
        return self._logged_in
    
    # =========================================================================
    # Connection Management
    # =========================================================================
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if CDP port is already in use."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(('localhost', port))
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False
    
    def _wait_for_port(self, port: int, timeout: float = 30.0) -> bool:
        """Wait for CDP port to become available."""
        start = time.time()
        while time.time() - start < timeout:
            if self._is_port_in_use(port):
                return True
            time.sleep(0.5)
        return False
    
    def _launch_chrome(self) -> subprocess.Popen:
        """Launch Chrome with CDP enabled."""
        chrome_args = [
            self.cfg.chrome_path,
            f"--remote-debugging-port={self.cfg.cdp_port}",
            f"--user-data-dir={self.cfg.chrome_user_data}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--disable-translate",
            f"--window-size={self.cfg.viewport_width},{self.cfg.viewport_height}",
        ]
        
        if self.cfg.headless:
            chrome_args.append("--headless=new")
        
        log.info(f"Launching Chrome: {self.cfg.chrome_path}")
        log.info(f"CDP Port: {self.cfg.cdp_port}, Headless: {self.cfg.headless}")
        
        process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        log.info(f"Waiting for CDP port {self.cfg.cdp_port}...")
        if not self._wait_for_port(self.cfg.cdp_port):
            process.kill()
            raise RuntimeError(f"Chrome did not start CDP on port {self.cfg.cdp_port}")
        
        log.info("Chrome ready")
        return process
    
    async def connect(self) -> bool:
        """
        Connect to Chrome and ShopKeyPro.
        
        If Chrome with CDP is already running, connects to it.
        Otherwise, launches Chrome.
        
        Returns:
            True if connected successfully
        """
        if self._connected:
            return True
        
        try:
            self._playwright = await async_playwright().start()
            
            # Check if Chrome is already running with CDP
            if self._is_port_in_use(self.cfg.cdp_port):
                log.info(f"Found existing Chrome on port {self.cfg.cdp_port}")
            else:
                log.info("Launching Chrome...")
                self._chrome_process = self._launch_chrome()
                self._owns_chrome = True
            
            # Connect Playwright to Chrome via CDP
            cdp_url = f"http://localhost:{self.cfg.cdp_port}"
            log.info(f"Connecting to CDP: {cdp_url}")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            
            # Use existing context/page if available
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
                pages = self._context.pages
                if pages:
                    self._page = pages[0]
                else:
                    self._page = await self._context.new_page()
            else:
                self._context = await self._browser.new_context()
                self._page = await self._context.new_page()
            
            self._connected = True
            
            # Try to login
            await self._ensure_logged_in()
            
            return True
            
        except Exception as e:
            log.error(f"Connection error: {e}")
            await self.disconnect()
            return False
    
    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        log.info("Disconnecting...")
        
        try:
            if self._context:
                await self._context.close()
        except Exception as e:
            log.warning(f"Context close error: {e}")
        
        try:
            if self._browser:
                await self._browser.close()
        except Exception as e:
            log.warning(f"Browser close error: {e}")
        
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            log.warning(f"Playwright stop error: {e}")
        
        # Kill Chrome if we launched it
        if self._owns_chrome and self._chrome_process:
            try:
                self._chrome_process.terminate()
                self._chrome_process.wait(timeout=5)
            except:
                self._chrome_process.kill()
        
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._chrome_process = None
        self._connected = False
        self._logged_in = False
    
    # =========================================================================
    # Login/Logout
    # =========================================================================
    
    async def _ensure_logged_in(self) -> bool:
        """Ensure we're logged into ShopKeyPro."""
        if not self._page:
            return False
        
        # Navigate to main app
        main_url = "https://www1.shopkeypro.com/Main/Index"
        log.info(f"Navigating to: {main_url}")
        await self._page.goto(main_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        current_url = self._page.url
        log.debug(f"Current URL: {current_url}")
        
        # Check if already logged in (vehicle selector visible)
        vehicle_btn = await self._page.query_selector("#vehicleSelectorButton")
        if vehicle_btn and await vehicle_btn.is_visible():
            log.info("Already logged in")
            self._logged_in = True
            return True
        
        # Need to login
        # Check if on landing page (need to click Login)
        if 'www.shopkeypro.com' in current_url and 'www1' not in current_url:
            log.info("On landing page, clicking Login...")
            await human_delay(500, 800)
            login_btn = self._page.locator('a:has-text("Login"), button:has-text("Login")')
            await login_btn.first.click()
            await human_delay(1500, 2500)
        
        # Now on login page
        username_field = await self._page.query_selector("#username")
        if username_field:
            log.info("Entering credentials...")
            await human_delay(500, 800)
            await self._page.fill("#username", self.cfg.username)
            await human_delay(300, 600)
            await self._page.fill("#password", self.cfg.password)
            await human_delay(500, 800)
            await self._page.click("#loginButton")
            await human_delay(2000, 3500)
        
        # Verify login
        await self._page.wait_for_load_state("networkidle", timeout=30000)
        vehicle_btn = await self._page.query_selector("#vehicleSelectorButton")
        if vehicle_btn and await vehicle_btn.is_visible():
            log.info("Login successful")
            self._logged_in = True
            return True
        
        log.warning(f"Login may have failed. URL: {self._page.url}")
        return False
    
    async def logout(self) -> bool:
        """Logout from ShopKeyPro."""
        if not self._page or not self._logged_in:
            return True
        
        log.info("Logging out...")
        
        # Close any open modals first
        await self._close_modals()
        
        # Click logout
        try:
            logout = self._page.locator("#logout")
            if await logout.is_visible(timeout=2000):
                await logout.click()
                log.info("Logged out")
                self._logged_in = False
                self._current_vehicle = None
                return True
        except Exception as e:
            log.warning(f"Logout error: {e}")
        
        return False
    
    async def _close_modals(self) -> None:
        """Close any open modals."""
        modal_close_selectors = [
            "input[data-action='Cancel']",
            "span.close",
            ".modalDialogView .close",
            "#cancelButton",
            "button:has-text('Cancel')"
        ]
        
        for sel in modal_close_selectors:
            try:
                loc = self._page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    await loc.click()
                    await asyncio.sleep(0.3)
            except:
                pass
    
    async def close_modal_and_reset(self) -> None:
        """Close any open modal and reset state for retry."""
        if not self._page:
            return
        
        log.info("Closing modals and resetting...")
        await self._close_modals()
        await asyncio.sleep(0.5)
        self._current_vehicle = {}
    
    # =========================================================================
    # Vehicle Selection
    # =========================================================================
    
    async def select_vehicle(
        self,
        year: str,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None
    ) -> bool:
        """
        Select vehicle using deterministic approach.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel/trim
            
        Returns:
            True if vehicle selected successfully
        """
        if not self._page:
            return False
        
        log.info(f"Selecting vehicle: {year} {make} {model} {engine or ''}")
        
        # Close any open modals
        await self._close_modals()
        
        # Open vehicle selector
        try:
            await self._page.click("#vehicleSelectorButton", timeout=5000)
            await asyncio.sleep(0.5)
        except Exception as e:
            log.error(f"Could not open vehicle selector: {e}")
            return False
        
        # Click "Vehicle Selection" accordion header
        result = await self._page.evaluate('''() => {
            const headers = document.querySelectorAll('.accordion .header');
            for (const h of headers) {
                if (h.textContent.includes('Vehicle Selection')) {
                    h.click();
                    return 'clicked';
                }
            }
            return 'not found';
        }''')
        if result != 'clicked':
            log.warning("Could not find Vehicle Selection accordion")
        await asyncio.sleep(0.5)
        
        # Select Year -> Make -> Model -> Engine
        await self._select_qualifier_option(str(year), "Year")
        await human_delay()
        await self._select_qualifier_option(make, "Make")
        await human_delay()
        await self._select_qualifier_option(model, "Model")
        await human_delay()
        
        if engine:
            await self._select_qualifier_option(engine, "Engine")
            await human_delay()
        
        # Select submodel (first one if not specified)
        if submodel:
            await self._select_qualifier_option(submodel, "Submodel")
        else:
            await human_delay(500, 800)
            first = self._page.locator("#qualifierValueSelector li.qualifier").first
            if await first.is_visible(timeout=2000):
                await first.click()
        await human_delay()
        
        # Click "Use This Vehicle"
        try:
            utv = self._page.locator('input[value="Use This Vehicle"]')
            if await utv.is_visible(timeout=2000):
                await utv.click()
                log.info("Clicked 'Use This Vehicle'")
                await human_delay(1000, 1500)
        except Exception as e:
            log.warning(f"Note: {e}")
        
        # Store current vehicle
        self._current_vehicle = {
            "year": str(year),
            "make": make,
            "model": model,
            "engine": engine or "",
            "submodel": submodel or ""
        }
        
        return True
    
    async def _select_qualifier_option(self, value: str, qualifier_type: str) -> bool:
        """Select a value from the qualifier list."""
        await human_delay(600, 1000)
        
        options = self._page.locator("#qualifierValueSelector li.qualifier")
        count = await options.count()
        
        for i in range(count):
            opt = options.nth(i)
            text = (await opt.inner_text()).strip()
            if text == value or value.lower() in text.lower():
                await opt.click()
                log.debug(f"Selected {qualifier_type}: {text}")
                return True
        
        log.warning(f"Could not find {qualifier_type}: {value}")
        return False
    
    # =========================================================================
    # Page Content Extraction
    # =========================================================================
    
    async def get_page_text(self) -> str:
        """Extract all text content from the page."""
        if not self._page:
            return ""
        
        text = await self._page.evaluate('''() => {
            // Get modal content if present
            const modals = [];
            document.querySelectorAll('.modal, .modalDialogView, [role="dialog"], .popup').forEach(el => {
                modals.push(el.innerText || el.textContent);
            });
            
            // Get main content
            const mainContent = document.querySelector('#contentPanel, .content, main, #main')?.innerText || '';
            
            // Get all tables
            const tables = [];
            document.querySelectorAll('table').forEach(table => {
                const rows = [];
                table.querySelectorAll('tr').forEach(tr => {
                    const cells = [];
                    tr.querySelectorAll('td, th').forEach(cell => {
                        cells.push(cell.textContent.trim());
                    });
                    if (cells.length) rows.push(cells.join(' | '));
                });
                if (rows.length) tables.push(rows.join('\\n'));
            });
            
            // Get menu items
            const menuItems = [];
            document.querySelectorAll('.menuItem, .category, .accessItem').forEach(el => {
                const t = el.textContent.trim();
                if (t && t.length < 100) menuItems.push(t);
            });
            
            return JSON.stringify({
                url: window.location.href,
                modals: modals.slice(0, 5),
                mainContent: mainContent.substring(0, 15000),
                tables: tables.slice(0, 10),
                menuItems: menuItems.slice(0, 50)
            });
        }''')
        
        return text
    
    async def get_clickable_elements(self) -> List[Dict]:
        """Get list of clickable elements."""
        if not self._page:
            return []
        
        elements = await self._page.evaluate('''() => {
            const items = [];
            
            // Quick Access buttons
            document.querySelectorAll('.accessItem, [id*="Access"]').forEach(el => {
                const text = el.textContent.trim();
                const id = el.id;
                if (text && id) {
                    items.push({text: text.substring(0, 80), id: id, tag: 'quickAccess'});
                }
            });
            
            // Menu items
            document.querySelectorAll('.menuItem, .category, [data-action], a, button').forEach(el => {
                const text = el.textContent.trim();
                const id = el.id;
                if (text && text.length < 100 && text.length > 2) {
                    items.push({text: text.substring(0, 80), id: id || null, tag: el.tagName.toLowerCase()});
                }
            });
            
            return items.slice(0, 100);
        }''')
        
        return elements
    
    # =========================================================================
    # Data Extraction
    # =========================================================================
    
    async def get_data(
        self,
        year: int,
        make: str,
        model: str,
        data_type: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        extra_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Get automotive data for a vehicle.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            data_type: Type of data (e.g., "fluid capacities")
            engine: Engine specification
            submodel: Submodel
            extra_params: Additional parameters
            
        Returns:
            Dict with extracted data or error
        """
        if not self._connected:
            return {"success": False, "error": "Not connected"}
        
        if not self._logged_in:
            await self._ensure_logged_in()
            if not self._logged_in:
                return {"success": False, "error": "Not logged in"}
        
        # Retry logic
        max_retries = 2
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            try:
                result = await self._get_data_attempt(
                    year, make, model, data_type, engine, submodel, extra_params
                )
                if result.get("success"):
                    return result
                
                last_error = result.get("error", "Unknown error")
                
                if attempt < max_retries and self._is_retryable_error(last_error):
                    log.info(f"Attempt {attempt} failed (retryable): {last_error}")
                    await self.close_modal_and_reset()
                    await self.logout()
                    await asyncio.sleep(1)
                    await self._ensure_logged_in()
                    if not self._logged_in:
                        return {"success": False, "error": "Could not re-login after retry"}
                else:
                    return {"success": False, "error": last_error}
                    
            except asyncio.TimeoutError as e:
                last_error = f"Timeout: {e}"
                log.warning(f"Timeout on attempt {attempt}: {e}")
                if attempt < max_retries:
                    await self.close_modal_and_reset()
                    await self.logout()
                    await asyncio.sleep(1)
                    await self._ensure_logged_in()
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries and self._is_retryable_error(last_error):
                    log.warning(f"Error on attempt {attempt} (retrying): {e}")
                    await self.close_modal_and_reset()
                    await self.logout()
                    await asyncio.sleep(1)
                    await self._ensure_logged_in()
                else:
                    log.error(f"Error (not retrying): {e}")
                    return {"success": False, "error": last_error}
        
        return {"success": False, "error": last_error or "Failed after retries"}
    
    def _is_retryable_error(self, error_msg: str) -> bool:
        """Check if error is transient and worth retrying."""
        retryable_keywords = [
            "timeout", "execution context", "navigation", "target closed",
            "session", "connection", "modal", "stuck", "not visible"
        ]
        error_lower = error_msg.lower()
        return any(kw in error_lower for kw in retryable_keywords)
    
    async def _get_data_attempt(
        self,
        year: int,
        make: str,
        model: str,
        data_type: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        extra_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Single attempt to get data."""
        
        # Select vehicle if needed
        vehicle_key = f"{year}|{make}|{model}|{engine or ''}"
        current_key = self._get_current_vehicle_key()
        
        if current_key != vehicle_key:
            if not await self.select_vehicle(str(year), make, model, engine, submodel):
                return {"success": False, "error": "Could not select vehicle"}
        
        # Try Quick Access button first
        quick_selector = get_quick_access_selector(data_type)
        if quick_selector:
            try:
                await human_delay()
                await self._page.click(quick_selector, timeout=5000)
                log.info(f"Clicked Quick Access: {quick_selector}")
                await human_delay(1200, 1800)
            except Exception as e:
                log.warning(f"Quick Access click failed: {e}")
        
        # Extract with Gemini
        return await self._extract_with_gemini(data_type, extra_params)
    
    def _get_current_vehicle_key(self) -> str:
        """Get key for current vehicle."""
        if not self._current_vehicle:
            return ""
        return (
            f"{self._current_vehicle.get('year', '')}|"
            f"{self._current_vehicle.get('make', '')}|"
            f"{self._current_vehicle.get('model', '')}|"
            f"{self._current_vehicle.get('engine', '')}"
        )
    
    async def _extract_with_gemini(
        self,
        data_type: str,
        extra_params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Use Gemini to extract data from page."""
        page_text = await self.get_page_text()
        clickables = await self.get_clickable_elements()
        
        system_prompt = build_extraction_prompt(data_type, self._current_vehicle or {})
        
        user_content = f"""Extract {data_type} for this vehicle.

PAGE CONTENT:
{page_text}

CLICKABLE ELEMENTS:
{json.dumps(clickables[:50])}"""
        
        extracted_data = None
        
        for step in range(1, 10):
            response = await call_gemini(
                self.cfg.gemini_api_key,
                self.cfg.gemini_model,
                system_prompt,
                user_content
            )
            
            action = parse_gemini_response(response)
            if not action:
                break
            
            log.debug(f"Step {step}: {action['name']}")
            
            if action["name"] == "extract_data":
                extracted_data = action["args"].get("data", "")
                if action["args"].get("complete", False) or extracted_data:
                    break
            
            elif action["name"] == "click":
                selector = action["args"]["selector"]
                try:
                    await human_delay()
                    if selector.startswith("text=") or selector.startswith("#"):
                        await self._page.click(selector, timeout=5000)
                    else:
                        await self._page.click(f"text={selector}", timeout=5000)
                    await human_delay(1200, 1800)
                except Exception as e:
                    log.warning(f"Click error: {e}")
                
                # Get updated page content
                page_text = await self.get_page_text()
                clickables = await self.get_clickable_elements()
                user_content = f"""Continue extracting {data_type}.

PAGE CONTENT:
{page_text}

CLICKABLE ELEMENTS:
{json.dumps(clickables[:50])}"""
            
            elif action["name"] == "done":
                extracted_data = action["args"].get("data", "")
                if not action["args"].get("success", False):
                    return {
                        "success": False,
                        "error": action["args"].get("message", "Could not extract data"),
                        "vehicle": self._current_vehicle
                    }
                break
        
        if extracted_data:
            return {
                "success": True,
                "data": extracted_data,
                "data_type": data_type,
                "vehicle": self._current_vehicle
            }
        else:
            return {
                "success": False,
                "error": "No data extracted",
                "vehicle": self._current_vehicle
            }
    
    # =========================================================================
    # Convenience Methods
    # =========================================================================
    
    async def get_fluid_capacities(self, year: int, make: str, model: str,
                                   engine: str = None, submodel: str = None) -> Dict:
        """Get fluid capacities for a vehicle."""
        return await self.get_data(year, make, model, "fluid capacities", engine, submodel)
    
    async def get_reset_procedures(self, year: int, make: str, model: str,
                                   engine: str = None, submodel: str = None) -> Dict:
        """Get reset procedures for a vehicle."""
        return await self.get_data(year, make, model, "reset procedures", engine, submodel)
    
    async def get_tire_info(self, year: int, make: str, model: str,
                           engine: str = None, submodel: str = None) -> Dict:
        """Get tire information for a vehicle."""
        return await self.get_data(year, make, model, "tire information", engine, submodel)
    
    async def get_common_specs(self, year: int, make: str, model: str,
                              engine: str = None, submodel: str = None) -> Dict:
        """Get common specifications for a vehicle."""
        return await self.get_data(year, make, model, "common specs", engine, submodel)
    
    async def get_tsb(self, year: int, make: str, model: str,
                     engine: str = None, submodel: str = None) -> Dict:
        """Get technical service bulletins for a vehicle."""
        return await self.get_data(year, make, model, "technical bulletins", engine, submodel)
    
    async def get_dtc_info(self, year: int, make: str, model: str,
                          dtc_code: str, engine: str = None, submodel: str = None) -> Dict:
        """Get DTC code information for a vehicle."""
        return await self.get_data(
            year, make, model, f"DTC code {dtc_code}", engine, submodel,
            extra_params={"dtc_code": dtc_code}
        )
    
    async def get_adas_info(self, year: int, make: str, model: str,
                           engine: str = None, submodel: str = None) -> Dict:
        """Get ADAS calibration info for a vehicle."""
        return await self.get_data(year, make, model, "adas calibration", engine, submodel)


# =============================================================================
# CLI for Testing
# =============================================================================

async def main():
    """Test the navigator."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mitchell Navigator")
    parser.add_argument("--year", type=str, default="2020")
    parser.add_argument("--make", type=str, default="Toyota")
    parser.add_argument("--model", type=str, default="Camry")
    parser.add_argument("--engine", type=str, default="2.5L")
    parser.add_argument("--data", type=str, default="fluid capacities")
    parser.add_argument("--no-logout", action="store_true")
    parser.add_argument("--keep-open", action="store_true")
    args = parser.parse_args()
    
    print("=" * 60)
    print("MITCHELL NAVIGATOR TEST")
    print("=" * 60)
    print(f"Vehicle: {args.year} {args.make} {args.model} {args.engine}")
    print(f"Data: {args.data}")
    
    nav = MitchellNavigator()
    
    try:
        if not await nav.connect():
            print("Failed to connect")
            return
        
        result = await nav.get_data(
            int(args.year), args.make, args.model, args.data, args.engine
        )
        
        print("\n" + "=" * 60)
        print("RESULT")
        print("=" * 60)
        
        if result.get("success"):
            print(result.get("data", ""))
        else:
            print(f"Error: {result.get('error')}")
        
    finally:
        if args.keep_open:
            await nav.logout()
            print("[Navigator] Browser left open (--keep-open). Logged out.")
        else:
            if not args.no_logout:
                await nav.logout()
            await nav.disconnect()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
