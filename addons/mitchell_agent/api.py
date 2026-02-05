"""
Mitchell Agent API
===================
Simplified API for Autotech AI server integration.

This module handles browser lifecycle, session management, and delegates
all queries to the AI Navigator for autonomous navigation.

Example Usage:
    from addons.mitchell_agent.api import MitchellAPI
    
    async def get_info():
        api = MitchellAPI()
        await api.connect()
        
        result = await api.query(
            year=2018,
            make="Ford", 
            model="F-150",
            engine="5.0L",
            question="What are the oil capacity specs?"
        )
        
        await api.disconnect()
        return result

Architecture (2026-01):
    All queries now go through the AI Navigator (query_autonomous).
    Legacy scripted tools have been archived - the AI can navigate
    to any data on ShopKeyPro dynamically.
"""
import asyncio
import subprocess
import signal
import time
import socket
from typing import Dict, Any, Optional, List
from pathlib import Path
from dataclasses import dataclass, replace


class SessionLimitError(Exception):
    """Raised when ShopKeyPro has no available sessions (all licenses in use)."""
    pass

from .portal import MitchellPortal
from .config import Config, load_config

# Playwright imports
from playwright.async_api import async_playwright, Browser, BrowserContext, Page


@dataclass
class Vehicle:
    """Vehicle specification."""
    year: int
    make: str
    model: str
    engine: str = ""
    submodel: Optional[str] = None


class MitchellAPI:
    """
    High-level API for Mitchell Agent.
    
    All queries are handled by the AI Navigator which can autonomously
    navigate ShopKeyPro to find any information.
    
    Key methods:
    - connect(): Connect to ShopKeyPro and authenticate
    - query(): Ask any question about a vehicle
    - logout(): Log out (keeps browser open)
    - disconnect(): Full cleanup
    """
    
    def __init__(
        self,
        headless: bool = True,
        debug_screenshots: bool = False
    ):
        """
        Initialize the Mitchell API.
        
        Args:
            headless: Whether to run browser in headless mode
            debug_screenshots: If True, save screenshots during navigation
        """
        self._portal: Optional[MitchellPortal] = None
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
            chrome_args.append("--headless=new")
        
        print(f"[MitchellAPI] Launching Chrome: {chrome_path}")
        print(f"[MitchellAPI] CDP Port: {self._cdp_port}")
        print(f"[MitchellAPI] Headless: {headless}")
        print(f"[MitchellAPI] User data dir: {user_data_dir}")
        
        process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
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
                cdp_url = self._cfg.chrome_cdp_url
                print(f"[MitchellAPI] Using configured CDP URL: {cdp_url}")
            elif self._chrome_process and self._is_port_in_use(self._cdp_port):
                cdp_url = f"http://localhost:{self._cdp_port}"
                print(f"[MitchellAPI] Reconnecting to existing Chrome on port {self._cdp_port}")
            elif self._cdp_port and self._is_port_in_use(self._cdp_port):
                cdp_url = f"http://localhost:{self._cdp_port}"
                print(f"[MitchellAPI] Connecting to pre-assigned port {self._cdp_port}")
            elif not self._cdp_port and self._is_port_in_use(9222):
                cdp_url = "http://localhost:9222"
                self._cdp_port = 9222
                print(f"[MitchellAPI] Found existing Chrome on port 9222")
            else:
                print("[MitchellAPI] Launching Chrome with CDP...")
                self._chrome_process = self._launch_chrome(headless=self._cfg.playwright_headless)
                cdp_url = f"http://localhost:{self._cdp_port}"
            
            print(f"[MitchellAPI] Connecting Playwright to CDP: {cdp_url}")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            
            contexts = self._browser.contexts
            if contexts:
                print(f"[MitchellAPI] Using existing browser context (found {len(contexts)} contexts)")
                self._context = contexts[0]
            else:
                print("[MitchellAPI] Creating new browser context...")
                self._context = await self._browser.new_context()
            
            pages = self._context.pages
            if pages:
                print(f"[MitchellAPI] Found {len(pages)} existing pages")
                self._page = pages[0]
            else:
                print("[MitchellAPI] Creating new page...")
                self._page = await self._context.new_page()
            
            self._page.set_default_timeout(self._cfg.playwright_nav_timeout_ms)
            
            # Navigate to ShopKeyPro
            main_app_url = "https://www1.shopkeypro.com/Main/Index"
            print(f"[MitchellAPI] Navigating to ShopKeyPro main app: {main_app_url}")
            await self._page.goto(main_app_url, wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            current_url = self._page.url
            print(f"[MitchellAPI] Current URL: {current_url}")
            
            # Dismiss cookie consent banner if present (OneTrust)
            try:
                consent_btn = self._page.locator('#onetrust-accept-btn-handler, button:has-text("Accept All Cookies")')
                if await consent_btn.count() > 0 and await consent_btn.first.is_visible():
                    print("[MitchellAPI] Dismissing cookie consent banner...")
                    await consent_btn.first.click(timeout=5000)
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"[MitchellAPI] Cookie consent handling: {e}")
            
            username_field = await self._page.query_selector('#username')
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            
            # Check for session limit page FIRST (before trying login)
            session_limit_detected = await self._check_session_limit()
            if session_limit_detected:
                raise SessionLimitError(
                    "All ShopKeyPro sessions are currently in use. "
                    "Please log out from another device or try again in a few minutes."
                )
            
            if username_field:
                print("[MitchellAPI] Login page detected, entering credentials...")
                await self._do_login()
            elif 'www.shopkeypro.com' in current_url and 'www1' not in current_url:
                print("[MitchellAPI] Landing page detected, need to login...")
                login_btn = self._page.locator('a:has-text("Login"), button:has-text("Login")')
                await login_btn.first.click()
                print("[MitchellAPI] Waiting for login page navigation...")
                await self._page.wait_for_load_state("domcontentloaded", timeout=15000)
                await asyncio.sleep(1)
                print(f"[MitchellAPI] After login click URL: {self._page.url}")
                await self._do_login()
            elif vehicle_btn and await vehicle_btn.is_visible():
                print("[MitchellAPI] ✅ Already logged in (vehicle selector found)")
            else:
                print(f"[MitchellAPI] Unknown page state, attempting login anyway...")
                await self._page.goto("https://aui.mitchell1.com/Login", wait_until="domcontentloaded")
                await asyncio.sleep(2)
                await self._do_login()
            
            # Final verification
            await asyncio.sleep(1)
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            if vehicle_btn and await vehicle_btn.is_visible():
                print("[MitchellAPI] ✅ Login confirmed (vehicle selector found)")
            else:
                print(f"[MitchellAPI] Warning: Vehicle selector not found. URL: {self._page.url}")
            
            self._connected = True
            return True
            
        except Exception as e:
            import traceback
            print(f"[MitchellAPI] Connection error: {e}")
            traceback.print_exc()
            await self._cleanup()
            return False
    
    async def connect_browser_only(self, cdp_port: int = None) -> bool:
        """
        Connect to browser WITHOUT logging in.
        
        Used by unified navigator which handles login itself.
        
        Args:
            cdp_port: CDP port to connect to (or launch new Chrome)
        
        Returns:
            True if browser connected
        """
        try:
            self._cfg = load_config()
            if self._headless is not None:
                self._cfg = replace(self._cfg, playwright_headless=self._headless)
            
            self._playwright = await async_playwright().start()
            
            # Connect to existing Chrome or launch new one
            if cdp_port and self._is_port_in_use(cdp_port):
                cdp_url = f"http://localhost:{cdp_port}"
                self._cdp_port = cdp_port
            else:
                self._chrome_process = self._launch_chrome(
                    headless=self._cfg.playwright_headless,
                    port=cdp_port,
                )
                cdp_url = f"http://localhost:{self._cdp_port}"
            
            print(f"[MitchellAPI] Connecting to Chrome: {cdp_url}")
            self._browser = await self._playwright.chromium.connect_over_cdp(cdp_url)
            
            # Get or create page
            contexts = self._browser.contexts
            if contexts:
                self._context = contexts[0]
            else:
                self._context = await self._browser.new_context()
            
            pages = self._context.pages
            if pages:
                self._page = pages[0]
            else:
                self._page = await self._context.new_page()
            
            self._page.set_default_timeout(30000)
            return True
            
        except Exception as e:
            print(f"[MitchellAPI] Browser connection error: {e}")
            return False
    
    async def _check_session_limit(self) -> bool:
        """Check if we're on a session limit page (all licenses in use).
        
        Returns True if session limit is detected, False otherwise.
        """
        try:
            current_url = self._page.url.lower()
            
            # Check URL patterns for session management pages
            session_url_patterns = [
                "selectsession", "select-session", "managesession",
                "session/select", "session/manage", "aui.mitchell1.com/session"
            ]
            if any(pattern in current_url for pattern in session_url_patterns):
                print("[MitchellAPI] ⚠️ Session selection page detected via URL")
                return True
            
            # Check for session limit text on page
            session_limit_texts = [
                "sessions are using licenses",
                "session is using a license", 
                "please manually logout",
                "select the session",
                "maximum.*session",
                "all.*licenses.*in use",
            ]
            
            page_text = await self._page.inner_text("body")
            page_text_lower = page_text.lower()
            
            for pattern in session_limit_texts:
                if pattern in page_text_lower:
                    print(f"[MitchellAPI] ⚠️ Session limit detected: '{pattern}'")
                    # Save screenshot for debugging
                    try:
                        await self._page.screenshot(path='/tmp/session_limit_detected.png')
                        print("[MitchellAPI] Screenshot saved to /tmp/session_limit_detected.png")
                    except:
                        pass
                    return True
            
            return False
            
        except Exception as e:
            print(f"[MitchellAPI] Session limit check error: {e}")
            return False
    
    async def _do_login(self):
        """Perform login with credentials."""
        # Check if auto-login is happening (URL contains autoLogin=True)
        current_url = self._page.url
        if "autoLogin=True" in current_url:
            print("[MitchellAPI] Auto-login detected, waiting for redirect...")
            # Wait for auto-login to complete - page will navigate to main app
            for attempt in range(15):
                await asyncio.sleep(1)
                current_url = self._page.url
                print(f"[MitchellAPI] Auto-login check {attempt+1}/15, URL: {current_url[:60]}...")
                
                if "shopkeypro.com/Main" in current_url or "shopkeypro.com/Home" in current_url:
                    vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
                    if vehicle_btn:
                        print("[MitchellAPI] ✅ Auto-login successful")
                        return
                
                # If we're back at login page without autoLogin, fall through to manual login
                if "mitchell1.com/Login" in current_url and "autoLogin" not in current_url:
                    print("[MitchellAPI] Auto-login failed, falling back to manual login")
                    break
            else:
                # Auto-login took too long, check if we're logged in anyway
                vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
                if vehicle_btn:
                    print("[MitchellAPI] ✅ Login confirmed after wait")
                    return
        
        # Dismiss cookie consent banner if present on login page (OneTrust)
        try:
            consent_btn = self._page.locator('#onetrust-accept-btn-handler, button:has-text("Accept All Cookies")')
            if await consent_btn.count() > 0 and await consent_btn.first.is_visible():
                print("[MitchellAPI] Dismissing cookie consent banner on login page...")
                await consent_btn.first.click(timeout=5000)
                await asyncio.sleep(1)
        except Exception as e:
            print(f"[MitchellAPI] Login page cookie consent handling: {e}")
        
        print("[MitchellAPI] Waiting for login form to load...")
        try:
            await self._page.wait_for_selector('#username', timeout=10000)
        except Exception as e:
            # Check if we're already logged in (auto-login completed)
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            if vehicle_btn:
                print("[MitchellAPI] ✅ Already logged in (auto-login completed)")
                return
            print(f"[MitchellAPI] Login form did not load: {e}")
            print(f"[MitchellAPI] Current URL: {self._page.url}")
            try:
                await self._page.screenshot(path='/tmp/login_form_missing.png')
                print("[MitchellAPI] Screenshot saved to /tmp/login_form_missing.png")
            except:
                pass
            return
        
        username_field = await self._page.query_selector('#username')
        if not username_field:
            # One more check - maybe auto-login happened
            vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
            if vehicle_btn:
                print("[MitchellAPI] ✅ Already logged in")
                return
            print("[MitchellAPI] Warning: No username field found on current page")
            return
        
        print("[MitchellAPI] Entering credentials...")
        try:
            await self._page.locator('#username').fill(self._cfg.mitchell_username)
            await asyncio.sleep(0.5)
            print("[MitchellAPI] Username entered, filling password...")
            
            await self._page.locator('#password').fill(self._cfg.mitchell_password)
            await asyncio.sleep(0.5)
            print("[MitchellAPI] Password entered")
        except Exception as e:
            print(f"[MitchellAPI] Error filling credentials: {e}")
            await self._page.screenshot(path='/tmp/credentials_error.png')
            raise
        
        print("[MitchellAPI] Clicking login button...")
        await self._page.locator('#loginButton').click()
        
        print("[MitchellAPI] Waiting for login to complete...")
        
        try:
            await self._page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        
        print("[MitchellAPI] Waiting for main app to load...")
        for attempt in range(10):
            await asyncio.sleep(2)
            current_url = self._page.url
            print(f"[MitchellAPI] Login check {attempt+1}/10, URL: {current_url[:60]}...")
            
            if "shopkeypro.com/Main" in current_url or "shopkeypro.com/Home" in current_url:
                try:
                    vehicle_btn = await self._page.query_selector('#vehicleSelectorButton')
                    if vehicle_btn:
                        print("[MitchellAPI] ✅ Main app loaded successfully")
                        break
                except Exception:
                    pass
            
            if "mitchell1.com/Login" in current_url or "aui.mitchell1.com" in current_url:
                continue
        
        print(f"[MitchellAPI] Post-login URL: {self._page.url}")
    
    async def _cleanup(self) -> None:
        """Clean up all resources."""
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
            
            # Close any open modals
            if self._page:
                try:
                    cancel_btn = self._page.locator("input[data-action='Cancel']")
                    if await cancel_btn.is_visible(timeout=1000):
                        print("[MitchellAPI] Clicking Cancel to close vehicle selector...")
                        await cancel_btn.click()
                        await self._page.wait_for_timeout(500)
                except Exception as e:
                    print(f"[MitchellAPI] No modal to close: {e}")
            
            success = await self._portal.logout(self._context)
            
            self._connected = False
            
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
            self._connected = False
            return False
    
    async def ensure_clean_state(self) -> bool:
        """Ensure browser is in a clean logged-out state.
        
        Connects to Chrome, checks if logged in, and logs out if necessary.
        This handles cases where Chrome was left logged in from a previous run.
        Returns True if browser is in clean state, False if there was an error.
        """
        try:
            # Try to connect to see current state
            connected = await self.connect_browser_only()
            if not connected:
                # Chrome not running or can't connect - that's clean
                print("[MitchellAPI] No existing Chrome session - clean state")
                return True
            
            # Check if we're on ShopKeyPro and logged in
            if self._page:
                try:
                    url = self._page.url
                    print(f"[MitchellAPI] Current URL: {url}")
                    
                    if "shopkeypro.com" in url and "/Main" in url:
                        # We're logged in - need to logout
                        print("[MitchellAPI] Found existing logged-in session, logging out...")
                        await self.logout()
                        print("[MitchellAPI] Logged out of existing session")
                    else:
                        # Not logged in or not on ShopKeyPro - disconnect
                        await self.disconnect()
                except Exception as e:
                    print(f"[MitchellAPI] Error checking page state: {e}")
                    await self.disconnect()
            else:
                await self.disconnect()
            
            return True
        except Exception as e:
            print(f"[MitchellAPI] Error ensuring clean state: {e}")
            return False
    
    async def disconnect(self) -> None:
        """Disconnect from ShopKeyPro and close browser."""
        print("[MitchellAPI] Disconnecting...")
        
        try:
            if self._portal and self._context:
                print("[MitchellAPI] Logging out of ShopKeyPro...")
                await self._portal.logout(self._context)
        except Exception as e:
            print(f"[MitchellAPI] Logout error (non-fatal): {e}")
        
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
    
    async def query(
        self,
        year: int,
        make: str,
        model: str,
        question: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        context: str = "",
    ) -> Dict[str, Any]:
        """
        Query ShopKeyPro using the AI Navigator.
        
        The AI Navigator will autonomously navigate the portal to find
        the requested information. It can handle any type of query:
        - Fluid capacities
        - Torque specs
        - DTC codes
        - Wiring diagrams
        - TSBs
        - Reset procedures
        - And anything else on ShopKeyPro
        
        Args:
            year: Vehicle year
            make: Vehicle make (e.g., "Ford")
            model: Vehicle model (e.g., "F-150")
            question: What you want to know (e.g., "oil capacity", "P0300 code info")
            engine: Engine specification (e.g., "5.0L")
            submodel: Submodel (e.g., "XLT")
            context: Additional context for the AI
        
        Returns:
            Dict with 'success', 'data', 'images', 'error' keys
        """
        if not self._connected:
            raise RuntimeError("Not connected. Call connect() first.")
        
        from .ai_navigator.autonomous_navigator import query_mitchell_autonomous
        
        vehicle = {
            "year": year,
            "make": make,
            "model": model,
            "engine": engine or "",
            "submodel": submodel,
        }
        
        result = await query_mitchell_autonomous(
            page=self._page,
            goal=question,
            vehicle=vehicle,
            context=context,
        )
        
        return result
    
    @property
    def page(self) -> Optional[Page]:
        """Get the Playwright page object (for advanced usage)."""
        return self._page
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to ShopKeyPro."""
        return self._connected


# Convenience function for one-shot queries
async def mitchell_query(
    year: int,
    make: str,
    model: str,
    question: str,
    engine: Optional[str] = None,
    submodel: Optional[str] = None
) -> Dict[str, Any]:
    """
    One-shot query to Mitchell.
    
    Handles connection/disconnection automatically.
    For multiple queries, use MitchellAPI directly for efficiency.
    """
    api = MitchellAPI()
    
    try:
        if not await api.connect():
            return {"success": False, "error": "Failed to connect to ShopKeyPro"}
        
        return await api.query(year, make, model, question, engine, submodel)
    finally:
        await api.disconnect()
