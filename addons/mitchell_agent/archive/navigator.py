#!/usr/bin/env python3
"""
Mitchell Navigator - Unified browser automation for ShopKeyPro
==============================================================

Combines CDP server functionality with navigation/extraction.

Key design principles (learned from test_stable_agent.py):
1. DETERMINISTIC vehicle selection (not AI-driven)
2. TEXT-BASED data extraction (not vision - captures scrollable content)
3. QUICK ACCESS buttons with known IDs for navigation
4. GEMINI for data parsing from extracted text

Quick Access Button IDs:
- #fluidsQuickAccess - Fluid Capacities
- #commonSpecsAccess - Common Specs (torque specs, general specs)
- #resetProceduresAccess - Reset Procedures (oil life reset, TPMS reset)
- #technicalBulletinAccess - Technical Bulletins / TSBs
- #dtcIndexAccess - DTC Index (trouble codes)
- #tpmsTireFitmentQuickAccess - Tire Information & TPMS
- #adasAccess - Driver Assist / ADAS
- #wiringDiagramsAccess - Wiring Diagrams
- #electricalComponentLocationAccess - Electrical Component Locations
- #ctmQuickAccess - Component Tests
- #serviceManualQuickAccess - Service Manual

Usage:
    from addons.mitchell_agent.navigator import MitchellNavigator
    
    async def main():
        nav = MitchellNavigator()
        await nav.connect()
        
        data = await nav.get_data(
            year=2020, make="Toyota", model="Camry", engine="2.5L",
            data_type="fluid capacities"
        )
        
        await nav.logout()
        await nav.disconnect()
"""
import asyncio
import base64
import httpx
import json
import os
import random
import re
import signal
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Load environment
load_dotenv()


# =============================================================================
# Human-like Delays (avoid bot detection)
# =============================================================================

async def human_delay(min_ms: int = 800, max_ms: int = 1300) -> None:
    """Add random delay to mimic human behavior and avoid bot detection."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class NavigatorConfig:
    """Navigator configuration from environment."""
    username: str
    password: str
    chrome_path: str
    chrome_user_data: str
    cdp_port: int
    headless: bool
    gemini_api_key: str
    gemini_model: str
    viewport_width: int
    viewport_height: int
    
    @classmethod
    def from_env(cls) -> "NavigatorConfig":
        return cls(
            username=os.environ.get("MITCHELL_USERNAME", ""),
            password=os.environ.get("MITCHELL_PASSWORD", ""),
            chrome_path=os.environ.get("CHROME_EXECUTABLE_PATH", "/usr/bin/google-chrome"),
            chrome_user_data=os.environ.get("CHROME_USER_DATA_PATH", "/tmp/mitchell-chrome"),
            cdp_port=int(os.environ.get("MITCHELL_CDP_PORT", "9222")),
            headless=os.environ.get("MITCHELL_HEADLESS", "false").lower() == "true",
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
            viewport_width=int(os.environ.get("VIEWPORT_WIDTH", "1920")),
            viewport_height=int(os.environ.get("VIEWPORT_HEIGHT", "1080")),
        )


# =============================================================================
# Quick Access Mapping
# =============================================================================
# NOTE: Use #quickLinkRegion prefix because each ID exists twice in the DOM
# (once in #quickLinkRegion, once in #quickAccessPanel). The visible one is
# #quickLinkRegion.

QUICK_ACCESS_BUTTONS = {
    # Fluid Capacities
    "fluid capacities": "#quickLinkRegion #fluidsQuickAccess",
    "fluids": "#quickLinkRegion #fluidsQuickAccess",
    "oil capacity": "#quickLinkRegion #fluidsQuickAccess",
    "coolant capacity": "#quickLinkRegion #fluidsQuickAccess",
    
    # Common Specs (torque, general specs)
    "common specs": "#quickLinkRegion #commonSpecsAccess",
    "specifications": "#quickLinkRegion #commonSpecsAccess",
    "torque specs": "#quickLinkRegion #commonSpecsAccess",
    "torque specifications": "#quickLinkRegion #commonSpecsAccess",
    
    # Reset Procedures
    "reset procedures": "#quickLinkRegion #resetProceduresAccess",
    "oil reset": "#quickLinkRegion #resetProceduresAccess",
    "oil life reset": "#quickLinkRegion #resetProceduresAccess",
    "tpms reset": "#quickLinkRegion #resetProceduresAccess",
    "maintenance reset": "#quickLinkRegion #resetProceduresAccess",
    
    # Technical Bulletins / TSBs
    "technical bulletins": "#quickLinkRegion #technicalBulletinAccess",
    "tsb": "#quickLinkRegion #technicalBulletinAccess",
    "service bulletins": "#quickLinkRegion #technicalBulletinAccess",
    
    # DTC Index
    "dtc": "#quickLinkRegion #dtcIndexAccess",
    "dtc index": "#quickLinkRegion #dtcIndexAccess",
    "trouble codes": "#quickLinkRegion #dtcIndexAccess",
    "diagnostic codes": "#quickLinkRegion #dtcIndexAccess",
    
    # Tire Information (TPMS & Tire Fitment)
    "tire information": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tire specs": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tires": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tire pressure": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    "tpms": "#quickLinkRegion #tpmsTireFitmentQuickAccess",
    
    "adas": "#quickLinkRegion #adasAccess",
    "driver assist": "#quickLinkRegion #adasAccess",
    "calibration": "#quickLinkRegion #adasAccess",
    "adas calibration": "#quickLinkRegion #adasAccess",
}

def get_quick_access_selector(data_type: str) -> Optional[str]:
    """Map data type to Quick Access button selector."""
    key = data_type.lower().strip()
    return QUICK_ACCESS_BUTTONS.get(key)


# =============================================================================
# Gemini Integration for Data Extraction
# =============================================================================

GEMINI_TOOLS = [{
    "function_declarations": [
        {
            "name": "extract_data",
            "description": "Extract structured data from the page text",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "The extracted data in a readable format"},
                    "complete": {"type": "boolean", "description": "True if all requested data was found"}
                },
                "required": ["data", "complete"]
            }
        },
        {
            "name": "click",
            "description": "Click on an element if more navigation is needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector or text= selector"},
                    "reason": {"type": "string", "description": "Why clicking this"}
                },
                "required": ["selector", "reason"]
            }
        },
        {
            "name": "done",
            "description": "Task complete or cannot continue",
            "parameters": {
                "type": "object",
                "properties": {
                    "success": {"type": "boolean"},
                    "message": {"type": "string"},
                    "data": {"type": "string", "description": "Any extracted data"}
                },
                "required": ["success", "message"]
            }
        }
    ]
}]


async def call_gemini(
    api_key: str,
    model: str,
    system_prompt: str,
    user_content: str
) -> dict:
    """Call Gemini API for text analysis with rate limit retry."""
    contents = [{"role": "user", "parts": [{"text": user_content}]}]
    
    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "tools": GEMINI_TOOLS,
        "tool_config": {"function_calling_config": {"mode": "ANY"}},
        "generation_config": {"temperature": 0.0}
    }
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    # Retry logic for rate limits (429)
    max_retries = 3
    base_delay = 2.0
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for attempt in range(max_retries):
            resp = await client.post(url, json=payload)
            
            if resp.status_code == 429:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)  # 2, 4, 8 seconds
                    print(f"[Gemini] Rate limited (429), retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
            
            return resp.json()


# =============================================================================
# MitchellNavigator - Main Class
# =============================================================================

class MitchellNavigator:
    """
    Unified browser automation for ShopKeyPro.
    
    Handles:
    - Chrome launch with CDP
    - Playwright connection
    - Login/logout
    - Deterministic vehicle selection
    - Text-based data extraction with Gemini
    """
    
    def __init__(self, config: Optional[NavigatorConfig] = None):
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
        
        print(f"[Navigator] Launching Chrome: {self.cfg.chrome_path}")
        print(f"[Navigator] CDP Port: {self.cfg.cdp_port}")
        print(f"[Navigator] Headless: {self.cfg.headless}")
        
        process = subprocess.Popen(
            chrome_args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        
        print(f"[Navigator] Waiting for CDP port {self.cfg.cdp_port}...")
        if not self._wait_for_port(self.cfg.cdp_port):
            process.kill()
            raise RuntimeError(f"Chrome did not start CDP on port {self.cfg.cdp_port}")
        
        print(f"[Navigator] Chrome ready")
        return process
    
    async def connect(self) -> bool:
        """
        Connect to Chrome and ShopKeyPro.
        
        If Chrome with CDP is already running, connects to it.
        Otherwise, launches Chrome.
        """
        if self._connected:
            return True
        
        try:
            self._playwright = await async_playwright().start()
            
            # Check if Chrome is already running with CDP
            if self._is_port_in_use(self.cfg.cdp_port):
                print(f"[Navigator] Found existing Chrome on port {self.cfg.cdp_port}")
            else:
                print("[Navigator] Launching Chrome...")
                self._chrome_process = self._launch_chrome()
                self._owns_chrome = True
            
            # Connect Playwright to Chrome via CDP
            cdp_url = f"http://localhost:{self.cfg.cdp_port}"
            print(f"[Navigator] Connecting to CDP: {cdp_url}")
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
            print(f"[Navigator] Connection error: {e}")
            await self.disconnect()
            return False
    
    async def disconnect(self) -> None:
        """Disconnect and clean up resources."""
        print("[Navigator] Disconnecting...")
        
        try:
            if self._context:
                await self._context.close()
        except Exception as e:
            print(f"[Navigator] Context close error: {e}")
        
        try:
            if self._browser:
                await self._browser.close()
        except Exception as e:
            print(f"[Navigator] Browser close error: {e}")
        
        try:
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            print(f"[Navigator] Playwright stop error: {e}")
        
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
        print(f"[Navigator] Navigating to: {main_url}")
        await self._page.goto(main_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
        
        current_url = self._page.url
        print(f"[Navigator] Current URL: {current_url}")
        
        # Check if already logged in (vehicle selector visible)
        vehicle_btn = await self._page.query_selector("#vehicleSelectorButton")
        if vehicle_btn and await vehicle_btn.is_visible():
            print("[Navigator] ✅ Already logged in")
            self._logged_in = True
            return True
        
        # Need to login
        # Check if on landing page (need to click Login)
        if 'www.shopkeypro.com' in current_url and 'www1' not in current_url:
            print("[Navigator] On landing page, clicking Login...")
            await human_delay(500, 800)
            login_btn = self._page.locator('a:has-text("Login"), button:has-text("Login")')
            await login_btn.first.click()
            await human_delay(1500, 2500)
        
        # Now on login page
        username_field = await self._page.query_selector("#username")
        if username_field:
            print("[Navigator] Entering credentials...")
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
            print("[Navigator] ✅ Login successful")
            self._logged_in = True
            return True
        
        print(f"[Navigator] ⚠️ Login may have failed. URL: {self._page.url}")
        return False
    
    async def logout(self) -> bool:
        """Logout from ShopKeyPro."""
        if not self._page or not self._logged_in:
            return True
        
        print("[Navigator] Logging out...")
        
        # Close any open modals first
        for sel in ["input[data-action='Cancel']", "span.close", ".close"]:
            try:
                loc = self._page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    await loc.click()
                    await asyncio.sleep(0.3)
            except:
                pass
        
        # Click logout
        try:
            logout = self._page.locator("#logout")
            if await logout.is_visible(timeout=2000):
                await logout.click()
                print("[Navigator] ✅ Logged out")
                self._logged_in = False
                self._current_vehicle = None
                return True
        except Exception as e:
            print(f"[Navigator] Logout error: {e}")
        
        return False
    
    async def close_modal_and_reset(self):
        """Close any open modal and reset state for retry."""
        if not self._page:
            return
        
        print("[Navigator] Closing modals and resetting...")
        
        # Close modals
        for sel in [
            "input[data-action='Cancel']",
            "span.close",
            ".modalDialogView .close",
            "#cancelButton",
            "button:has-text('Cancel')"
        ]:
            try:
                loc = self._page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    await loc.click()
                    await asyncio.sleep(0.3)
                    print(f"[Navigator] Closed modal via {sel}")
            except:
                pass
        
        # Wait a moment
        await asyncio.sleep(0.5)
        
        # Clear current vehicle state
        self._current_vehicle = {}
    
    # =========================================================================
    # Vehicle Selection (Deterministic)
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
        
        This is more reliable than AI-driven navigation.
        """
        if not self._page:
            return False
        
        print(f"[Navigator] Selecting vehicle: {year} {make} {model} {engine or ''}")
        
        # Close any open modals
        for sel in ["input[data-action='Cancel']", "span.close"]:
            try:
                loc = self._page.locator(sel).first
                if await loc.is_visible(timeout=500):
                    await loc.click()
                    await asyncio.sleep(0.3)
            except:
                pass
        
        # Open vehicle selector
        try:
            await self._page.click("#vehicleSelectorButton", timeout=5000)
            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"[Navigator] Could not open vehicle selector: {e}")
            return False
        
        # Click "Vehicle Selection" accordion header (important!)
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
            print("[Navigator] Warning: Could not find Vehicle Selection accordion")
        await asyncio.sleep(0.5)
        
        # Helper function to select qualifier option
        async def select_option(value: str, qualifier_type: str):
            """Select a value from the qualifier list."""
            # Human-like delay before action
            await human_delay(600, 1000)
            
            # Try exact match first, then partial match
            options = self._page.locator("#qualifierValueSelector li.qualifier")
            count = await options.count()
            
            for i in range(count):
                opt = options.nth(i)
                text = (await opt.inner_text()).strip()
                if text == value or value.lower() in text.lower():
                    await opt.click()
                    print(f"[Navigator] Selected {qualifier_type}: {text}")
                    return True
            
            print(f"[Navigator] Warning: Could not find {qualifier_type}: {value}")
            return False
        
        # Select Year -> Make -> Model -> Engine (with human delays)
        await select_option(str(year), "Year")
        await human_delay()
        await select_option(make, "Make")
        await human_delay()
        await select_option(model, "Model")
        await human_delay()
        
        if engine:
            await select_option(engine, "Engine")
            await human_delay()
        
        # Select submodel (first one if not specified)
        if submodel:
            await select_option(submodel, "Submodel")
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
                print("[Navigator] ✅ Clicked 'Use This Vehicle'")
                await human_delay(1000, 1500)
        except Exception as e:
            print(f"[Navigator] Note: {e}")
        
        # Store current vehicle
        self._current_vehicle = {
            "year": str(year),
            "make": make,
            "model": model,
            "engine": engine or "",
            "submodel": submodel or ""
        }
        
        return True
    
    # =========================================================================
    # Page Text Extraction
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
    # Data Extraction with Gemini
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
            data_type: Type of data (e.g., "fluid capacities", "reset procedures")
            engine: Engine specification
            submodel: Submodel
            extra_params: Additional parameters (e.g., dtc_code for DTC lookup)
        
        Returns:
            Dict with extracted data or error
        """
        if not self._connected:
            return {"success": False, "error": "Not connected"}
        
        if not self._logged_in:
            await self._ensure_logged_in()
            if not self._logged_in:
                return {"success": False, "error": "Not logged in"}
        
        # Errors that are retryable (transient failures)
        RETRYABLE_ERRORS = [
            "timeout", "execution context", "navigation", "target closed",
            "session", "connection", "modal", "stuck", "not visible"
        ]
        
        def is_retryable(error_msg: str) -> bool:
            """Check if error is transient and worth retrying."""
            error_lower = error_msg.lower()
            return any(err in error_lower for err in RETRYABLE_ERRORS)
        
        # Retry loop for vehicle selection + data extraction
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
                
                # Only retry on transient failures, not permanent errors
                if attempt < max_retries and is_retryable(last_error):
                    print(f"[Navigator] Attempt {attempt} failed (retryable): {last_error}")
                    await self.close_modal_and_reset()
                    await self.logout()
                    await asyncio.sleep(1)
                    await self._ensure_logged_in()
                    if not self._logged_in:
                        return {"success": False, "error": "Could not re-login after retry"}
                else:
                    # Permanent error - don't retry
                    if not is_retryable(last_error):
                        print(f"[Navigator] Permanent error (not retrying): {last_error}")
                    return {"success": False, "error": last_error}
                        
            except asyncio.TimeoutError as e:
                last_error = f"Timeout: {e}"
                print(f"[Navigator] Timeout on attempt {attempt}: {e}")
                if attempt < max_retries:
                    await self.close_modal_and_reset()
                    await self.logout()
                    await asyncio.sleep(1)
                    await self._ensure_logged_in()
            except Exception as e:
                last_error = str(e)
                # Only retry on retryable exceptions
                if attempt < max_retries and is_retryable(last_error):
                    print(f"[Navigator] Error on attempt {attempt} (retrying): {e}")
                    await self.close_modal_and_reset()
                    await self.logout()
                    await asyncio.sleep(1)
                    await self._ensure_logged_in()
                else:
                    print(f"[Navigator] Error (not retrying): {e}")
                    return {"success": False, "error": last_error}
        
        return {"success": False, "error": last_error or "Failed after retries"}
    
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
        """Single attempt to get data (called by get_data with retry logic)."""
        
        # Select vehicle
        vehicle_key = f"{year}|{make}|{model}|{engine or ''}"
        current_key = f"{self._current_vehicle.get('year', '')}|{self._current_vehicle.get('make', '')}|{self._current_vehicle.get('model', '')}|{self._current_vehicle.get('engine', '')}" if self._current_vehicle else ""
        
        if current_key != vehicle_key:
            if not await self.select_vehicle(str(year), make, model, engine, submodel):
                return {"success": False, "error": "Could not select vehicle"}
        
        # Try Quick Access button first
        quick_selector = get_quick_access_selector(data_type)
        if quick_selector:
            try:
                await human_delay()  # Human delay before click
                await self._page.click(quick_selector, timeout=5000)
                print(f"[Navigator] Clicked Quick Access: {quick_selector}")
                await human_delay(1200, 1800)  # Wait for content to load
            except Exception as e:
                print(f"[Navigator] Quick Access click failed: {e}")
        
        # Extract page text
        page_text = await self.get_page_text()
        clickables = await self.get_clickable_elements()
        
        # Use Gemini to extract/parse data
        system_prompt = f"""You are extracting {data_type} from an automotive repair database.
Vehicle: {year} {make} {model} {engine or ''}

TASK: Extract the requested data from the page text provided.

RULES:
1. If the data is visible in the page text, use extract_data to return it
2. Format data as a readable list with all values
3. Include units (quarts, psi, ft-lbs, etc.)
4. If data is not found, use done with success=False

QUICK ACCESS BUTTONS (use # selector if needed):
- #fluidsQuickAccess - Fluid Capacities
- #commonSpecsAccess - Common Specs
- #resetProceduresAccess - Reset Procedures
- #technicalBulletinAccess - Technical Bulletins
- #dtcIndexAccess - DTC Index
- #tireInfoAccess - Tire Information
- #adasAccess - ADAS"""
        
        user_content = f"""Extract {data_type} for this vehicle.

PAGE CONTENT:
{page_text}

CLICKABLE ELEMENTS:
{json.dumps(clickables[:50])}"""
        
        # Call Gemini
        extracted_data = None
        
        for step in range(1, 10):  # Max 9 steps
            response = await call_gemini(
                self.cfg.gemini_api_key,
                self.cfg.gemini_model,
                system_prompt,
                user_content
            )
            
            candidates = response.get("candidates", [])
            if not candidates:
                print(f"[Navigator] No Gemini response: {response}")
                break
            
            parts = candidates[0].get("content", {}).get("parts", [])
            
            action = None
            for part in parts:
                if "functionCall" in part:
                    func = part["functionCall"]
                    action = {"name": func["name"], "args": func.get("args", {})}
                    break
            
            if not action:
                break
            
            print(f"[Navigator] Step {step}: {action['name']}")
            
            if action["name"] == "extract_data":
                extracted_data = action["args"].get("data", "")
                complete = action["args"].get("complete", False)
                if complete or extracted_data:
                    break
            
            elif action["name"] == "click":
                selector = action["args"]["selector"]
                try:
                    # Human delay before clicking
                    await human_delay()
                    if selector.startswith("text="):
                        await self._page.click(selector, timeout=5000)
                    elif selector.startswith("#"):
                        await self._page.click(selector, timeout=5000)
                    else:
                        await self._page.click(f"text={selector}", timeout=5000)
                    # Human delay after clicking (page load)
                    await human_delay(1200, 1800)
                except Exception as e:
                    print(f"[Navigator] Click error: {e}")
                
                # Get updated page text
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
        return await self.get_data(year, make, model, f"DTC code {dtc_code}", engine, submodel,
                                  extra_params={"dtc_code": dtc_code})
    
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
    parser.add_argument("--no-logout", action="store_true", help="Don't logout after (but close browser)")
    parser.add_argument("--keep-open", action="store_true", help="Keep browser open for next test")
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
            # Logout but keep browser for next test
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
