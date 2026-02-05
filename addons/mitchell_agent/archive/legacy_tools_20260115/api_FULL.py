"""
Mitchell Agent API
===================
High-level API for Autotech AI server integration.

This module provides simple async functions for retrieving
automotive data from ShopKeyPro. It handles browser lifecycle,
session management, and tool execution.

Example Usage:
    from addons.mitchell_agent.api import MitchellAPI
    
    async def get_info():
        api = MitchellAPI()
        await api.connect()
        
        result = await api.get_fluid_capacities(
            year=2018,
            make="Ford", 
            model="F-150",
            engine="5.0L"
        )
        
        await api.disconnect()
        return result
"""
import asyncio
import subprocess
import signal
import time
import socket
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, replace

from .tools import (
    Vehicle,
    ToolResult,
    ToolRegistry,
    get_registry,
)
from .portal import MitchellPortal
from .config import Config, load_config

# Playwright imports
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


@dataclass
class VehicleSpec:
    """Simplified vehicle specification for API calls."""
    year: int
    make: str
    model: str
    engine: Optional[str] = None
    submodel: Optional[str] = None
    
    def to_vehicle(self) -> Vehicle:
        """Convert to internal Vehicle object."""
        return Vehicle(
            year=self.year,
            make=self.make,
            model=self.model,
            engine=self.engine or "",
            submodel=self.submodel
        )


class MitchellAPI:
    """
    High-level API for Mitchell Agent.
    
    Provides simple methods for retrieving automotive data:
    - get_fluid_capacities()
    - get_dtc_info()
    - get_torque_specs()
    - get_reset_procedure()
    - get_tsb_list()
    - get_adas_calibration()
    - get_tire_specs()
    - search()
    - browse_manual()
    
    Also provides query() method for natural language queries
    with automatic tool selection and fallback.
    """
    
    def __init__(
        self,
        unmapped_log_path: Optional[str] = None,
        headless: bool = True,
        debug_screenshots: bool = False
    ):
        """
        Initialize the Mitchell API.
        
        Args:
            unmapped_log_path: Path to log unmapped queries for future development.
                              Default: /prod/autotech_ai/mitchell_unmapped_queries.jsonl
            headless: Whether to run browser in headless mode
            debug_screenshots: If True, save screenshots at each tool step
        """
        self._portal: Optional[MitchellPortal] = None
        self._registry = get_registry()
        self._headless = headless
        self._connected = False
        self._debug_screenshots = debug_screenshots
        
        # Playwright objects
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._cfg: Optional[Config] = None
        
        # Chrome subprocess (for hybrid mode)
        self._chrome_process: Optional[subprocess.Popen] = None
        self._cdp_port: int = 9222
        
        # Set unmapped log path
        if unmapped_log_path:
            self._unmapped_log_path = Path(unmapped_log_path)
        else:
            # Default production path
            self._unmapped_log_path = Path("/prod/autotech_ai/mitchell_unmapped_queries.jsonl")
        
        self._registry.set_unmapped_log_path(self._unmapped_log_path)
    
    def _find_free_port(self, start_port: int = 9222) -> int:
        """Find a free port starting from start_port."""
        port = start_port
        while port < start_port + 100:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('localhost', port))
                    return port
            except OSError:
                port += 1
        raise RuntimeError(f"Could not find free port in range {start_port}-{start_port + 100}")
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use (e.g., Chrome already running)."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                s.connect(('localhost', port))
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            return False
    
    def _wait_for_port(self, port: int, timeout: float = 30.0) -> bool:
        """Wait for a port to become available (Chrome CDP ready)."""
        start = time.time()
        while time.time() - start < timeout:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1)
                    s.connect(('localhost', port))
                    return True
            except (ConnectionRefusedError, socket.timeout, OSError):
                time.sleep(0.5)
        return False
    
    def _launch_chrome(self, headless: bool = True) -> subprocess.Popen:
        """
        Launch Chrome with remote debugging enabled.
        
        Returns the subprocess.Popen object.
        """
        chrome_path = self._cfg.chrome_executable_path or self._find_chrome()
        if not chrome_path:
            raise RuntimeError("Chrome executable not found. Set CHROME_EXECUTABLE_PATH in .env")
        
        # Use pre-set port if available (for worker pool), otherwise find free port
        if not self._cdp_port:
            self._cdp_port = self._find_free_port()
        
        # Build Chrome arguments
        # Use override path if set, otherwise config, otherwise temp dir per port
        user_data_dir = getattr(self, '_user_data_override', None) or \
                        self._cfg.chrome_user_data_path or \
                        f"/tmp/mitchell-chrome-{self._cdp_port}"
        
        chrome_args = [
            chrome_path,
            f"--remote-debugging-port={self._cdp_port}",
            f"--user-data-dir={user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--disable-translate",
            "--metrics-recording-only",
            "--safebrowsing-disable-auto-update",
            f"--window-size={self._cfg.playwright_viewport_width},{self._cfg.playwright_viewport_height}",
        ]
        
        if headless:
            chrome_args.append("--headless=new")  # Chrome's new headless mode
        
        print(f"[MitchellAPI] Launching Chrome: {chrome_path}")
        print(f"[MitchellAPI] CDP Port: {self._cdp_port}")
        print(f"[MitchellAPI] Headless: {headless}")
        print(f"[MitchellAPI] User data dir: {user_data_dir}")
        
        # Launch Chrome
        process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent process group
        )
        
        # Wait for CDP to be ready
        print(f"[MitchellAPI] Waiting for CDP port {self._cdp_port}...")
        if not self._wait_for_port(self._cdp_port, timeout=30.0):
            process.kill()
            raise RuntimeError(f"Chrome did not start CDP on port {self._cdp_port}")
        
        print(f"[MitchellAPI] Chrome ready on port {self._cdp_port}")
        return process
    
    def _find_chrome(self) -> Optional[str]:
        """Find Chrome/Chromium executable on the system."""
        candidates = [
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/chromium",
            "/usr/bin/chromium-browser",
            "/snap/bin/chromium",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]
        for path in candidates:
            if Path(path).exists():
                return path
        return None
    
    async def connect(self) -> bool:
        """
        Connect to ShopKeyPro and authenticate.
        
        Uses hybrid Chrome + Playwright approach:
        1. Launch real Chrome with CDP enabled (bypasses bot detection)
        2. Connect Playwright to Chrome via CDP (nice automation API)
        3. Use portal for login and session management
        
        Returns:
            True if connection successful
        """
        if self._connected:
            return True
        
        try:
            # Load config from environment
            self._cfg = load_config()
            # Override headless setting if specified
            if self._headless is not None:
                self._cfg = replace(self._cfg, playwright_headless=self._headless)
            
            print(f"[MitchellAPI] Headless mode: {self._cfg.playwright_headless}")
            print(f"[MitchellAPI] Username: {self._cfg.mitchell_username[:3]}***")
            
            # Create portal for login handling
            self._portal = MitchellPortal(self._cfg)
            
            # Start Playwright
            print("[MitchellAPI] Starting Playwright...")
            self._playwright = await async_playwright().start()
            
            # Determine connection mode
            cdp_url = None
            print(f"[MitchellAPI] Connection check: chrome_process={self._chrome_process is not None}, cdp_port={self._cdp_port}")
            
            if self._cfg.chrome_cdp_url:
                # Mode 1: Connect to user-specified Chrome
                cdp_url = self._cfg.chrome_cdp_url
                print(f"[MitchellAPI] Using configured CDP URL: {cdp_url}")
            elif self._chrome_process and self._is_port_in_use(self._cdp_port):
                # Mode 2: We have a Chrome process we launched previously, reconnect to it
                cdp_url = f"http://localhost:{self._cdp_port}"
                print(f"[MitchellAPI] Reconnecting to existing Chrome on port {self._cdp_port}")
            elif self._cdp_port and self._is_port_in_use(self._cdp_port):
                # Mode 3a: Pre-assigned port (worker pool) - connect to our specific port
                cdp_url = f"http://localhost:{self._cdp_port}"
                print(f"[MitchellAPI] Connecting to pre-assigned port {self._cdp_port}")
            elif not self._cdp_port and self._is_port_in_use(9222):
                # Mode 3b: Existing Chrome with CDP on default port (externally managed)
                # Only use this if we don't have a pre-assigned port
                cdp_url = "http://localhost:9222"
                self._cdp_port = 9222
                print(f"[MitchellAPI] Found existing Chrome on port 9222")
            else:
                # Mode 4: Launch Chrome ourselves with CDP
                print("[MitchellAPI] Launching Chrome with CDP...")
                self._chrome_process = self._launch_chrome(headless=self._cfg.playwright_headless)
                cdp_url = f"http://localhost:{self._cdp_port}"
            
            print(f"[MitchellAPI] Connecting Playwright to CDP: {cdp_url}")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            
            # When connecting via CDP, use the default context (first one)
            # This preserves cookies/session from the Chrome profile
            contexts = self._browser.contexts
            if contexts:
                print(f"[MitchellAPI] Using existing browser context (found {len(contexts)} contexts)")
                self._context = contexts[0]
            else:
                print("[MitchellAPI] Creating new browser context...")
                self._context = await self._browser.new_context()
            
            # Check if there's already a page open
            pages = self._context.pages
            if pages:
                print(f"[MitchellAPI] Found {len(pages)} existing pages")
                self._page = pages[0]
            else:
                print("[MitchellAPI] Creating new page...")
                self._page = await self._context.new_page()
            
            # Set default timeout
            self._page.set_default_timeout(self._cfg.playwright_nav_timeout_ms)
            
            # Navigate to ShopKeyPro main app directly (works if session exists)
            main_app_url = "https://www1.shopkeypro.com/Main/Index"
            print(f"[MitchellAPI] Navigating to ShopKeyPro main app: {main_app_url}")
            await self._page.goto(main_app_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)  # Give page time to settle
            
            # Check current state
            current_url = self._page.url
            print(f"[MitchellAPI] Current URL: {current_url}")
            
            # Determine where we ended up
            username_field = await self._page.query_selector('#username')
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            
            # Case 1: On login page (has username field)
            if username_field:
                print("[MitchellAPI] Login page detected, entering credentials...")
                await self._do_login()
            
            # Case 2: Redirected to landing page (shopkeypro.com without www1)
            elif 'www.shopkeypro.com' in current_url and 'www1' not in current_url:
                print("[MitchellAPI] Landing page detected, need to login...")
                # Click the Login button on landing page
                login_btn = self._page.locator('a:has-text("Login"), button:has-text("Login")')
                await login_btn.first.click()
                # Wait for navigation to login page
                print("[MitchellAPI] Waiting for login page navigation...")
                await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
                await asyncio.sleep(1)
                print(f"[MitchellAPI] After login click URL: {self._page.url}")
                await self._do_login()
            
            # Case 3: Already on main app with vehicle selector
            elif vehicle_btn and await vehicle_btn.is_visible():
                print("[MitchellAPI] ✅ Already logged in (vehicle selector found)")
            
            # Case 4: Unknown state
            else:
                print(f"[MitchellAPI] Unknown page state, attempting login anyway...")
                # Try navigating to login page directly
                await self._page.goto("https://aui.mitchell1.com/Login", wait_until="domcontentloaded")
                await asyncio.sleep(2)
                await self._do_login()
            
            # Final verification - check for vehicle selector
            await asyncio.sleep(1)
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            if vehicle_btn and await vehicle_btn.is_visible():
                print("[MitchellAPI] ✅ Login confirmed (vehicle selector found)")
            else:
                print(f"[MitchellAPI] Warning: Vehicle selector not found. URL: {self._page.url}")
            
            # Set browser for tool registry and mark as connected
            self._registry.set_browser(self._page)
            self._connected = True
            return True
            
        except Exception as e:
            import traceback
            print(f"[MitchellAPI] Connection error: {e}")
            traceback.print_exc()
            await self._cleanup()
            return False
    
    async def _do_login(self):
        """Perform login with credentials."""
        # Wait for login page to fully load - the username field should appear
        print("[MitchellAPI] Waiting for login form to load...")
        try:
            await self._page.wait_for_selector('#username', timeout=10000)
        except Exception as e:
            print(f"[MitchellAPI] Login form did not load: {e}")
            print(f"[MitchellAPI] Current URL: {self._page.url}")
            # Take a screenshot for debugging
            try:
                await self._page.screenshot(path='/tmp/login_form_missing.png')
                print("[MitchellAPI] Screenshot saved to /tmp/login_form_missing.png")
            except:
                pass
            return
        
        username_field = await self._page.query_selector('#username')
        if not username_field:
            print("[MitchellAPI] Warning: No username field found on current page")
            return
        
        print("[MitchellAPI] Entering credentials...")
        await self._page.locator('#username').fill(self._cfg.mitchell_username)
        await asyncio.sleep(0.5)
        
        await self._page.locator('#password').fill(self._cfg.mitchell_password)
        await asyncio.sleep(0.5)
        
        print("[MitchellAPI] Clicking login button...")
        await self._page.locator('#loginButton').click()
        
        # Wait for navigation - ShopKeyPro does multiple redirects after login
        print("[MitchellAPI] Waiting for login to complete...")
        
        # First wait for the login form to disappear or page to start navigating
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass  # May timeout during redirect, that's OK
        
        # Wait for ShopKeyPro main app to load (vehicle selector button)
        print("[MitchellAPI] Waiting for main app to load...")
        for attempt in range(10):  # Up to 20 seconds
            await asyncio.sleep(2)
            current_url = self._page.url
            print(f"[MitchellAPI] Login check {attempt+1}/10, URL: {current_url[:60]}...")
            
            # Check if we're on main app
            if "shopkeypro.com/Main" in current_url or "shopkeypro.com/Home" in current_url:
                try:
                    vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
                    if vehicle_btn:
                        print("[MitchellAPI] ✅ Main app loaded successfully")
                        break
                except Exception:
                    pass  # Page still loading
            
            # Still on login page - wait more
            if "mitchell1.com/Login" in current_url or "aui.mitchell1.com" in current_url:
                continue
        
        print(f"[MitchellAPI] Post-login URL: {self._page.url}")
    
    async def _cleanup(self) -> None:
        """Clean up all resources."""
        # Close Playwright resources
        try:
            if self._context:
                await self._context.close()
        except Exception as e:
            print(f"[MitchellAPI] Context close error: {e}")
        
        try:
            if self._browser:
                await self._browser.close()
        except Exception as e:
            print(f"[MitchellAPI] Browser close error: {e}")
        
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            print(f"[MitchellAPI] Playwright stop error: {e}")
        
        # Kill Chrome subprocess if we launched it
        if self._chrome_process:
            try:
                print(f"[MitchellAPI] Terminating Chrome process...")
                self._chrome_process.terminate()
                try:
                    self._chrome_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    print("[MitchellAPI] Chrome didn't terminate, killing...")
                    self._chrome_process.kill()
            except Exception as e:
                print(f"[MitchellAPI] Chrome cleanup error: {e}")
        
        self._portal = None
        self._context = None
        self._browser = None
        self._playwright = None
        self._page = None
        self._chrome_process = None
        self._connected = False
    
    async def ensure_clean_state(self) -> bool:
        """Ensure browser is in a clean, logged-out state.
        
        This should be called at agent startup to handle cases where:
        - Browser is already logged in from a previous session
        - A modal is blocking the screen
        - The page is in an unknown state
        
        Process:
        1. Initialize browser connection (without full login)
        2. Close any blocking modals
        3. If logged in, log out
        4. Leave browser ready for fresh login
        
        Returns True if browser is now in clean state.
        """
        try:
            print("[MitchellAPI] Ensuring clean browser state...")
            
            # Load config if needed
            if not self._cfg:
                from dataclasses import replace
                self._cfg = load_config()
                if self._headless is not None:
                    self._cfg = replace(self._cfg, playwright_headless=self._headless)
            
            # Initialize portal if needed
            if not self._portal:
                self._portal = MitchellPortal(self._cfg)
            
            # Start Playwright if needed
            if not self._playwright:
                print("[MitchellAPI] Starting Playwright...")
                self._playwright = await async_playwright().start()
            
            # Connect to browser
            cdp_url = None
            print(f"[MitchellAPI] ensure_clean_state check: chrome_process={self._chrome_process is not None}, cdp_port={self._cdp_port}")
            
            if self._cfg.chrome_cdp_url:
                cdp_url = self._cfg.chrome_cdp_url
                print(f"[MitchellAPI] Using configured CDP URL: {cdp_url}")
            elif self._chrome_process and self._is_port_in_use(self._cdp_port):
                # We have a Chrome process we launched previously, reconnect to it
                cdp_url = f"http://localhost:{self._cdp_port}"
                print(f"[MitchellAPI] Reconnecting to existing Chrome on port {self._cdp_port}")
            elif self._is_port_in_use(9222):
                cdp_url = "http://localhost:9222"
                self._cdp_port = 9222
                print(f"[MitchellAPI] Found existing Chrome on port 9222")
            else:
                print("[MitchellAPI] Launching Chrome with CDP...")
                self._chrome_process = self._launch_chrome(headless=self._cfg.playwright_headless)
                cdp_url = f"http://localhost:{self._cdp_port}"
            
            if not self._browser:
                print(f"[MitchellAPI] Connecting Playwright to CDP: {cdp_url}")
                self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            
            # Get context
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
            else:
                self._context = await self._browser.new_context()
            
            # Get or create page
            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = await self._context.new_page()
            
            self._page.set_default_timeout(self._cfg.playwright_nav_timeout_ms)
            
            # Navigate to ShopKeyPro to check state
            current_url = self._page.url or ""
            if 'shopkeypro.com' not in current_url.lower() and 'mitchell' not in current_url.lower():
                # Not on ShopKeyPro, navigate there
                print("[MitchellAPI] Navigating to ShopKeyPro to check state...")
                await self._page.goto("https://www1.shopkeypro.com/Main/Index", wait_until="domcontentloaded")
                await asyncio.sleep(2)
            
            # Check current state
            current_url = self._page.url
            print(f"[MitchellAPI] Current URL: {current_url}")
            
            # Step 1: Close any blocking modals
            print("[MitchellAPI] Step 1: Closing any blocking modals...")
            for attempt in range(3):
                modal_closed = False
                modal_selectors = [
                    "input.grey.button[value='Cancel']",
                    "input[data-action='Cancel']",
                    "span.close",
                    "button.close",
                    ".modalDialogView .close",
                    "[aria-label='Close']",
                ]
                for sel in modal_selectors:
                    try:
                        close_btn = self._page.locator(sel).first
                        if await close_btn.is_visible(timeout=500):
                            await close_btn.click()
                            print(f"[MitchellAPI] Closed modal using: {sel}")
                            await asyncio.sleep(0.5)
                            modal_closed = True
                            break
                    except Exception:
                        continue
                if not modal_closed:
                    break
            
            # Step 2: Check if logged in and logout if so
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            logout_btn = await self._page.query_selector('#logout')
            
            if vehicle_btn and await vehicle_btn.is_visible():
                print("[MitchellAPI] Currently logged in - logging out for clean state...")
                await self.logout()
                print("[MitchellAPI] ✅ Browser is now in clean logged-out state")
            elif 'login' in current_url.lower() or await self._page.query_selector('#username'):
                print("[MitchellAPI] ✅ Already on login page - clean state")
            elif 'www.shopkeypro.com' in current_url and 'www1' not in current_url:
                print("[MitchellAPI] ✅ On landing page - clean state (not logged in)")
            else:
                print(f"[MitchellAPI] ✅ Unknown state but proceeding: {current_url}")
            
            return True
            
        except Exception as e:
            import traceback
            print(f"[MitchellAPI] Error ensuring clean state: {e}")
            traceback.print_exc()
            return False

    async def logout(self) -> bool:
        """Logout from ShopKeyPro without closing the browser.
        
        Keeps browser open for next request but clears session.
        Returns True if successful, False otherwise.
        """
        if not self._portal or not self._context:
            print("[MitchellAPI] No active session to logout from")
            return False
        
        try:
            print("[MitchellAPI] Logging out of ShopKeyPro...")
            
            # First, close any open modals (like vehicle selector)
            if self._page:
                try:
                    # The Cancel button is an INPUT element, not a button
                    cancel_btn = self._page.locator("input[data-action='Cancel']")
                    if await cancel_btn.is_visible(timeout=1000):
                        print("[MitchellAPI] Clicking Cancel to close vehicle selector...")
                        await cancel_btn.click()
                        await self._page.wait_for_timeout(500)
                except Exception as e:
                    print(f"[MitchellAPI] No modal to close: {e}")
            
            success = await self._portal.logout(self._context)
            
            # Reset connected flag so next connect() will re-login
            self._connected = False
            
            # IMPORTANT: Also disconnect playwright to avoid stale references
            # When the next request comes, connect() will create fresh connections
            # This prevents duplicate CDP sessions after idle timeout
            print("[MitchellAPI] Disconnecting Playwright (will reconnect on next request)...")
            try:
                if self._browser:
                    await self._browser.close()
            except Exception as e:
                print(f"[MitchellAPI] Browser close error: {e}")
            
            try:
                if self._playwright:
                    await self._playwright.stop()
            except Exception as e:
                print(f"[MitchellAPI] Playwright stop error: {e}")
            
            # Reset references (but keep Chrome process running)
            self._browser = None
            self._context = None
            self._page = None
            self._playwright = None
            self._portal = None
            
            if success:
                print("[MitchellAPI] ✅ Logout successful")
            else:
                print("[MitchellAPI] ⚠️ Logout may not have completed fully")
            return success
        except Exception as e:
            print(f"[MitchellAPI] Logout error: {e}")
            self._connected = False  # Reset anyway
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from ShopKeyPro and close browser."""
        print("[MitchellAPI] Disconnecting...")
        
        # Try to logout first (saves session, avoids leaving orphan sessions)
        try:
            if self._portal and self._context:
                print("[MitchellAPI] Logging out of ShopKeyPro...")
                await self._portal.logout(self._context)
        except Exception as e:
            print(f"[MitchellAPI] Logout error (non-fatal): {e}")
        
        # Save storage state for faster login next time
        try:
            if self._context and self._cfg:
                state_path = Path(self._cfg.storage_state_path)
                state_path.parent.mkdir(parents=True, exist_ok=True)
                await self._context.storage_state(path=str(state_path))
                print(f"[MitchellAPI] Saved session state to {state_path}")
        except Exception as e:
            print(f"[MitchellAPI] Storage state save error (non-fatal): {e}")
        
        await self._cleanup()
        print("[MitchellAPI] Disconnected")
    
    def _ensure_connected(self) -> bool:
        """Check if connected."""
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        return True
    
    def _make_vehicle(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None
    ) -> Vehicle:
        """Create a Vehicle object from parameters."""
        return Vehicle(
            year=int(year),  # Ensure year is int
            make=make,
            model=model,
            engine=engine or "",
            submodel=submodel
        )
    
    # ==================== Tier 1 Tools ====================
    
    async def get_fluid_capacities(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        fluid_type: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get fluid capacities for a vehicle.
        
        Args:
            year: Vehicle year
            make: Vehicle make (e.g., "Ford")
            model: Vehicle model (e.g., "F-150")
            engine: Engine specification (e.g., "5.0L")
            submodel: Submodel (e.g., "XLT")
            fluid_type: Filter by fluid type (e.g., "oil", "coolant")
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with fluid capacities data or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_fluid_capacities",
            vehicle,
            fluid_type=fluid_type,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_dtc_info(
        self,
        year: int,
        make: str,
        model: str,
        dtc_code: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get diagnostic trouble code information.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            dtc_code: DTC code (e.g., "P0300")
            engine: Engine specification
            submodel: Submodel
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with DTC information or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_dtc_info",
            vehicle,
            dtc_code=dtc_code,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_torque_specs(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        component: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get torque specifications.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            component: Filter by component (e.g., "wheel", "caliper")
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with torque specifications or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_torque_specs",
            vehicle,
            component=component,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_reset_procedure(
        self,
        year: int,
        make: str,
        model: str,
        procedure: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get reset procedure (oil life, TPMS, etc.).
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            procedure: Type of procedure (e.g., "oil", "tpms")
            engine: Engine specification
            submodel: Submodel
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with reset procedure or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_reset_procedure",
            vehicle,
            procedure=procedure,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_tsb_list(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        category: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get Technical Service Bulletins.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            category: Filter by category (e.g., "engine", "transmission")
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with TSB list or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_tsb_list",
            vehicle,
            category=category,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_adas_calibration(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        component: Optional[str] = None,
        info_type: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get ADAS calibration requirements.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            component: Filter by component (e.g., "camera", "radar", "anti-lock brake")
            info_type: Type of detailed info to get (e.g., "specs", "remove", "wiring", "location")
                      When specified with component, drills down to get specific details.
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with calibration requirements or detailed component info
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_adas_calibration",
            vehicle,
            component=component,
            info_type=info_type,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_tire_specs(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get tire and TPMS specifications.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with tire specs or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_tire_specs",
            vehicle,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_wiring_diagram(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        system: Optional[str] = None,
        subsystem: Optional[str] = None,
        diagram: Optional[str] = None,
        search: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get wiring diagrams for vehicle electrical systems.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            system: Electrical system (e.g., "Engine", "Body", "Chassis")
            subsystem: Subsystem (e.g., "Starting/Charging")
            diagram: Specific diagram name (e.g., "Starter Circuit")
            search: Search term to find diagrams
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with diagram systems/categories or image data
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_wiring_diagram",
            vehicle,
            system=system,
            subsystem=subsystem,
            diagram=diagram,
            search=search,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_specs_procedures(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        category: Optional[str] = None,
        topic: Optional[str] = None,
        search: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get common specifications and service procedures.
        
        Use for:
        - Torque specs ("torque specs for intake manifold")
        - Service procedures ("how to replace drive belt", "timing chain procedure")
        - Fluid specifications ("coolant specs", "oil capacity")
        - System specifications ("spark plug gap", "valve clearance")
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            category: Category to browse (e.g., "Torque", "Drive Belts")
            topic: Specific topic within category
            search: Search term to find relevant specs/procedures
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with specifications/procedures or navigation info
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_specs_procedures",
            vehicle,
            category=category,
            topic=topic,
            search=search,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_component_location(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        component: Optional[str] = None,
        location_type: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Find electrical component locations.
        
        Use for:
        - Fuse location ("F15 fuse", "radio fuse")
        - Ground points ("G100", "engine ground")
        - Component location ("ECM", "radio", "fuel pump")
        - Relay location ("starter relay", "fuel pump relay")
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            component: Component to find (e.g., "radio", "F15 fuse", "G100")
            location_type: Type filter ("fuse", "relay", "ground", "connector", "module")
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with component location info or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_component_location",
            vehicle,
            component=component,
            location_type=location_type,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def get_component_tests(
        self,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        component: Optional[str] = None,
        system: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Get component test information, pinouts, and operation descriptions.
        
        Use for:
        - ABS module pinouts
        - Wheel speed sensor tests
        - Starter motor tests
        - HVAC component tests
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            engine: Engine specification
            submodel: Submodel
            component: Component to test (e.g., "ABS Module", "Wheel Speed Sensors")
            system: System category (e.g., "ABS", "Body Electrical", "HVAC System")
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with component test info, pinouts, operation descriptions
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "get_component_tests",
            vehicle,
            component=component,
            system=system,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    async def lookup_vehicle(
        self,
        vin: Optional[str] = None,
        plate: Optional[str] = None,
        state: Optional[str] = None,
        raw_input: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Look up vehicle by VIN or license plate.
        
        Use for:
        - Decoding VIN to year/make/model/engine
        - Looking up vehicle from license plate
        - Handling OCR'd plate photos
        
        Args:
            vin: 17-character VIN
            plate: License plate number
            state: 2-letter state code (required if using plate)
            raw_input: Raw OCR text (e.g., "4mzh83 mi") - will be parsed
        
        Returns:
            Dict with decoded vehicle info: year, make, model, engine, vin
        """
        self._ensure_connected()
        
        # Create dummy vehicle for interface compatibility
        vehicle = Vehicle(year=0, make="Unknown", model="Unknown", engine="")
        
        result = await self._registry.execute_tool(
            "lookup_vehicle",
            vehicle,
            vin=vin,
            plate=plate,
            state=state,
            raw_input=raw_input,
            debug_screenshots=self._debug_screenshots
        )
        
        return result.to_dict()
    
    # ==================== Tier 2: Search ====================
    
    async def search(
        self,
        year: int,
        make: str,
        model: str,
        query: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Search Mitchell content using 1Search.
        
        This is the Tier 2 fallback for queries not handled
        by specific tools.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            query: Search query
            engine: Engine specification
            submodel: Submodel
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with search results or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "search_mitchell",
            vehicle,
            query=query,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    # ==================== Tier 3: Manual Browser ====================
    
    async def browse_manual(
        self,
        year: int,
        make: str,
        model: str,
        category: Optional[str] = None,
        subcategory: Optional[str] = None,
        topic: Optional[str] = None,
        engine: Optional[str] = None,
        submodel: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Browse Service Manual by category and topic.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            category: Top-level category (e.g., "Brakes")
            subcategory: Subcategory within category
            topic: Specific topic to retrieve
            engine: Engine specification
            submodel: Submodel
        
        Returns:
            Dict with manual content or navigation info
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_tool(
            "browse_manual",
            vehicle,
            category=category,
            subcategory=subcategory,
            topic=topic,
            debug_screenshots=self._debug_screenshots
        )
        
        return result.to_dict()
    
    # ==================== Smart Query ====================
    
    async def query(
        self,
        year: int,
        make: str,
        model: str,
        query: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        skip_vehicle_selection: bool = False
    ) -> Dict[str, Any]:
        """
        Execute a natural language query with automatic tool selection.
        
        This is the main entry point for Autotech AI. It will:
        1. Analyze the query to select appropriate tool(s)
        2. Execute Tier 1 tools if matched
        3. Fall back to Tier 2 search if no direct match
        4. Log unmapped queries for future development
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            query: Natural language query
            engine: Engine specification
            submodel: Submodel
            skip_vehicle_selection: Skip vehicle selection (already selected via plate lookup)
        
        Returns:
            Dict with query results or error
        """
        self._ensure_connected()
        vehicle = self._make_vehicle(year, make, model, engine, submodel)
        
        result = await self._registry.execute_with_fallback(
            query=query,
            vehicle=vehicle,
            debug_screenshots=self._debug_screenshots,
            skip_vehicle_selection=skip_vehicle_selection
        )
        
        return result.to_dict()
    
    # ==================== Utility ====================
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools.
        
        Returns:
            List of tool metadata dicts
        """
        return self._registry.list_tools()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to ShopKeyPro."""
        return self._connected


# Convenience function for one-shot queries
async def mitchell_query(
    year: int,
    make: str,
    model: str,
    query: str,
    engine: Optional[str] = None,
    submodel: Optional[str] = None
) -> Dict[str, Any]:
    """
    One-shot query to Mitchell.
    
    Handles connection/disconnection automatically.
    For multiple queries, use MitchellAPI directly for efficiency.
    
    Args:
        year: Vehicle year
        make: Vehicle make
        model: Vehicle model
        query: Natural language query
        engine: Engine specification
        submodel: Submodel
    
    Returns:
        Dict with query results or error
    """
    api = MitchellAPI()
    
    try:
        if not await api.connect():
            return {"success": False, "error": "Failed to connect to ShopKeyPro"}
        
        return await api.query(year, make, model, query, engine, submodel)
    finally:
        await api.disconnect()
