from __future__ import annotations

import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Optional
from datetime import datetime

import aiohttp
from playwright.async_api import Browser, BrowserContext, Page

from .config import Config
from .discovery import (
    discover_selectors,
    load_profile,
    merge_profile,
    save_profile,
)

log = logging.getLogger(__name__)


class PortalError(RuntimeError):
    pass


async def human_delay(min_ms: int = 200, max_ms: int = 800) -> None:
    """Add a random delay to mimic human behavior."""
    delay = random.randint(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)


class MitchellPortal:
    def __init__(self, cfg: Config):
        self.cfg = cfg

        self._selectors: dict[str, str] = {
            "sel_year_dropdown": cfg.sel_year_dropdown,
            "sel_make_dropdown": cfg.sel_make_dropdown,
            "sel_model_dropdown": cfg.sel_model_dropdown,
            "sel_engine_dropdown": cfg.sel_engine_dropdown,
            "sel_vehicle_apply_button": cfg.sel_vehicle_apply_button,
            "sel_search_input": cfg.sel_search_input,
            "sel_search_submit": cfg.sel_search_submit,
            "sel_results_container": cfg.sel_results_container,
            "sel_content_frame": cfg.sel_content_frame,
            "sel_breadcrumb": cfg.sel_breadcrumb,
            "sel_page_title": cfg.sel_page_title,
            "sel_tech_content_root": cfg.sel_tech_content_root,
        }

        # Overlay missing selectors from persisted profile.
        try:
            profile = load_profile(cfg.selectors_profile_path)
            for k, v in profile.items():
                if isinstance(v, str) and v and not self._selectors.get(k):
                    self._selectors[k] = v
        except Exception:
            pass
        
        # Default timing values
        self._timing = {
            "after_click": 500,
            "after_type": 300,
            "page_load": 2000,
        }

    def _sel(self, key: str) -> str:
        return (self._selectors.get(key) or "").strip()

    def _set_sel(self, key: str, value: str) -> None:
        if value and isinstance(value, str):
            self._selectors[key] = value.strip()

    def get_timing(self, key: str, default: int = 500) -> int:
        """Get a timing value."""
        return self._timing.get(key, default)

    async def ensure_selectors(self, page: Page) -> None:
        cfg = self.cfg
        if not cfg.auto_discover_selectors:
            return

        critical = [
            "sel_year_dropdown",
            "sel_make_dropdown",
            "sel_model_dropdown",
            "sel_engine_dropdown",
            "sel_vehicle_apply_button",
            "sel_search_input",
            "sel_search_submit",
            "sel_results_container",
            "sel_content_frame",
            "sel_tech_content_root",
        ]
        if all(self._sel(k) for k in critical):
            return

        discovered = await discover_selectors(page)
        for k, v in discovered.to_dict().items():
            if v and not self._sel(k):
                self._set_sel(k, v)

        # Persist only newly discovered values.
        try:
            existing = load_profile(cfg.selectors_profile_path)
            merged = merge_profile(existing, discovered)
            save_profile(cfg.selectors_profile_path, merged)
        except Exception:
            pass

    async def new_context(self, browser: Browser) -> BrowserContext:
        cfg = self.cfg
        state_path = Path(cfg.storage_state_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        # Choose a reasonable user agent if not configured.
        default_ua = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        )
        user_agent = cfg.playwright_user_agent or default_ua

        context_kwargs = {
            "user_agent": user_agent,
            "viewport": {"width": cfg.playwright_viewport_width, "height": cfg.playwright_viewport_height},
            "locale": "en-US",
            "timezone_id": "America/Los_Angeles",
            "extra_http_headers": {"accept-language": "en-US,en;q=0.9"},
        }

        if state_path.exists():
            ctx = await browser.new_context(storage_state=str(state_path), **context_kwargs)
        else:
            ctx = await browser.new_context(**context_kwargs)

        # Anti-detection initialization script (run before any page scripts)
        stealth_js = r"""
        // Prevent webdriver flag
        Object.defineProperty(navigator, 'webdriver', { get: () => false, configurable: true });
        // Provide Chrome runtime stub
        try { window.chrome = window.chrome || { runtime: {} }; } catch(e) {}
        // Languages
        try { Object.defineProperty(navigator, 'languages', { get: () => ['en-US','en'] }); } catch(e) {}
        // Permissions query override
        try {
            const origQuery = navigator.permissions.query;
            navigator.permissions.query = (parameters) =>
                parameters && parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : origQuery(parameters);
        } catch(e) {}
        // Prevent headless detection via plugins
        try { Object.defineProperty(navigator, 'plugins', { get: () => [1,2,3,4,5] }); } catch(e) {}
        // Provide a stable platform and userAgent override if configured
        try {
            Object.defineProperty(navigator, 'platform', { get: () => window.__pw_platform || navigator.platform });
            Object.defineProperty(navigator, 'userAgent', { get: () => window.__pw_user_agent || navigator.userAgent });
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => window.__pw_hwc || navigator.hardwareConcurrency || 8 });
        } catch(e) {}
        """

        await ctx.add_init_script(stealth_js)

        # Configure explicit UA/platform/hwc in the page context for later evaluation
        if cfg.playwright_user_agent:
            await ctx.add_init_script(f"window.__pw_user_agent = '{cfg.playwright_user_agent}';")
        # Platform thunk: try to make it consistent with the UA
        if 'Windows' in (cfg.playwright_user_agent or ''):
            await ctx.add_init_script("window.__pw_platform = 'Win32';")
        else:
            await ctx.add_init_script("window.__pw_platform = navigator.platform || 'Linux x86_64';")
        await ctx.add_init_script(f"window.__pw_hwc = {max(2, min(16, cfg.playwright_viewport_width // 200))};")

        return ctx

    async def ensure_logged_in(self, context: BrowserContext) -> Page:
        """Ensure we're logged in and return the logged-in page.
        
        Returns the page that is logged in - DO NOT close this page.
        """
        cfg = self.cfg
        if not cfg.mitchell_login_url:
            raise PortalError("MITCHELL_LOGIN_URL not configured")

        # First check if there's already a logged-in page in the context
        for existing_page in context.pages:
            if 'shopkeypro.com' in existing_page.url.lower():
                try:
                    vehicle_btn = await existing_page.query_selector('#vehicleSelectorButton')
                    if vehicle_btn:
                        log.info("Found existing logged-in page: %s", existing_page.url)
                        return existing_page
                except Exception:
                    pass

        page = await context.new_page()
        page.set_default_timeout(cfg.playwright_nav_timeout_ms)

        try:
            # First, check if we're already logged in by going to the base URL
            base_url = cfg.mitchell_base_url or cfg.mitchell_login_url.rsplit('/Login', 1)[0]
            await page.goto(base_url, wait_until="domcontentloaded")
            
            # Check for logged-in sentinel
            if cfg.sel_logged_in_sentinel:
                try:
                    await page.locator(cfg.sel_logged_in_sentinel).first.wait_for(timeout=3000)
                    log.info("Already logged in (sentinel found)")
                    return page  # Return the page, don't close it
                except Exception:
                    pass
            
            # Check if we're on a page with vehicle selector (indicates logged in to ShopKeyPro)
            try:
                vehicle_btn = await page.query_selector('#vehicleSelectorButton')
                if vehicle_btn:
                    log.info("Already logged in (vehicle selector present)")
                    return page  # Return the page, don't close it
            except Exception:
                pass
            
            # Check if we landed on the login page directly
            if "/Login" in page.url or "/login" in page.url.lower():
                log.info("On login page, will enter credentials")
                # Continue to credential entry below
            else:
                # We're on some other page - check if there's a Login button
                # which indicates we're NOT logged in
                try:
                    login_btn = page.locator('#btnLogin, #btnLoginHero, button:has-text("Login")').first
                    if await login_btn.is_visible(timeout=2000):
                        log.info("Found Login button, navigating to login page to enter credentials")
                        # Don't just click the button (that relies on saved creds)
                        # Go to the actual login page to enter credentials properly
                        await page.goto(cfg.mitchell_login_url, wait_until="domcontentloaded")
                    else:
                        # No login button visible, might be logged in
                        log.info("No login button found, assuming logged in")
                        return page  # Return the page, don't close it
                except Exception:
                    # If we can't find a login button, assume we're logged in
                    log.info("Already logged in (no login button found)")
                    return page  # Return the page, don't close it

            # Not logged in - need credentials
            if not (cfg.mitchell_username and cfg.mitchell_password):
                raise PortalError("Not logged in and credentials not configured (MITCHELL_USERNAME/MITCHELL_PASSWORD)")

            # Navigate to login page
            await page.goto(cfg.mitchell_login_url, wait_until="domcontentloaded")
            login_url = page.url

            # Start with configured selectors; fall back to discovery if missing or not usable.
            selectors = {
                "username": (cfg.sel_username_input or "").strip(),
                "password": (cfg.sel_password_input or "").strip(),
                "button": (cfg.sel_login_button or "").strip(),
            }

            discovered = await self._discover_login_selectors(page)

            async def usable(sel: str) -> bool:
                if not sel:
                    return False
                try:
                    return await page.locator(sel).first.is_visible(timeout=1500)
                except Exception:
                    return False

            if not selectors["username"] or not await usable(selectors["username"]):
                selectors["username"] = discovered.get("username") or selectors["username"]
            if not selectors["password"] or not await usable(selectors["password"]):
                selectors["password"] = discovered.get("password") or selectors["password"]
            if not selectors["button"] or not await usable(selectors["button"]):
                selectors["button"] = discovered.get("button") or selectors["button"]

            if not (selectors["username"] and selectors["password"]):
                await self._write_login_debug_artifacts(page, "missing_login_selectors")
                raise PortalError(
                    "Login selectors not configured and auto-discovery failed (need SEL_USERNAME_INPUT/SEL_PASSWORD_INPUT)"
                )

            # Prefer explicit ID selectors if present (common on this site)
            try:
                if await page.locator('input#username:visible').count() > 0:
                    selectors["username"] = 'input#username:visible'
            except Exception:
                pass
            try:
                if await page.locator('input#password:visible').count() > 0:
                    selectors["password"] = 'input#password:visible'
            except Exception:
                pass

            # Fill credentials with human-like typing to avoid bot detection
            username_loc = page.locator(selectors["username"]).first
            password_loc = page.locator(selectors["password"]).first
            try:
                # Always use human-like typing for login credentials
                log.info("Entering username")
                await human_delay(300, 800)  # Pause before starting to type
                await username_loc.click()
                await human_delay(200, 500)
                # Clear any existing value first
                await username_loc.fill("")
                await username_loc.type(cfg.mitchell_username, delay=random.randint(30, 80))
                
                log.info("Entering password")
                await human_delay(400, 1000)  # Pause between fields like a human would
                await password_loc.click()
                await human_delay(200, 400)
                await password_loc.fill("")
                # Type password character by character with delays
                for char in cfg.mitchell_password:
                    await password_loc.press(char)
                    await asyncio.sleep(random.uniform(0.03, 0.08))
                
                log.info("Credentials entered")

                # Pause after typing before submitting
                await human_delay(300, 700)

                async def _value_len(sel: str) -> int:
                    try:
                        return int(
                            await page.locator(sel).first.evaluate("(el) => (el && el.value ? el.value.length : 0)")
                        )
                    except Exception:
                        return 0

                if await _value_len(selectors["username"]) == 0 or await _value_len(selectors["password"]) == 0:
                    # fallback: set values directly and dispatch input/change events (some frameworks require this)
                    try:
                        await page.evaluate(
                            """(usSel, pwSel, user, pwd) => {
                                const us = document.querySelector(usSel.replace(':visible',''));
                                const pw = document.querySelector(pwSel.replace(':visible',''));
                                if (us) {
                                    us.focus(); us.value = user; us.dispatchEvent(new Event('input', {bubbles:true})); us.dispatchEvent(new Event('change', {bubbles:true}));
                                }
                                if (pw) {
                                    pw.focus(); pw.value = pwd; pw.dispatchEvent(new Event('input', {bubbles:true})); pw.dispatchEvent(new Event('change', {bubbles:true}));
                                }
                            }""",
                            selectors["username"], selectors["password"], cfg.mitchell_username, cfg.mitchell_password,
                        )
                        await asyncio.sleep(0.1)
                    except Exception:
                        await self._write_login_debug_artifacts(page, "login_fill_js_fallback_exception")
                        raise

                if await _value_len(selectors["username"]) == 0 or await _value_len(selectors["password"]) == 0:
                    await self._write_login_debug_artifacts(page, "login_fill_no_visible_values_after_fallback")
                    raise PortalError(
                        "Login fill did not populate visible fields after fallback (site may block automation)"
                    )
            except Exception:
                await self._write_login_debug_artifacts(page, "login_fill_exception")
                raise

            # Verify visible fields actually got values (avoid filling hidden inputs).
            async def value_len(sel: str) -> int:
                try:
                    return int(
                        await page.locator(sel).first.evaluate("(el) => (el && el.value ? el.value.length : 0)")
                    )
                except Exception:
                    return 0

            if await value_len(selectors["username"]) == 0 or await value_len(selectors["password"]) == 0:
                await self._write_login_debug_artifacts(page, "login_fill_no_visible_values")
                raise PortalError(
                    "Login fill did not populate visible fields (selectors may target hidden inputs)"
                )

            # Attach lightweight debug hooks: responses, requests, and console forwarding
            responses: list[dict] = []
            requests: list[dict] = []

            def _on_response(r):
                try:
                    responses.append({"url": r.url, "status": r.status})
                except Exception:
                    pass

            def _on_request(req):
                try:
                    # May be large; keep only essentials
                    req_info = {"url": req.url, "method": req.method}
                    try:
                        post = req.post_data
                        if post:
                            req_info["postData"] = post[:2000]
                    except Exception:
                        pass
                    requests.append(req_info)
                except Exception:
                    pass

            def _on_console(msg):
                try:
                    log.info("page console: %s", msg.text)
                except Exception:
                    pass

            page.on("response", _on_response)
            page.on("request", _on_request)
            page.on("console", _on_console)

            # Save a pre-submit snapshot to help diagnose immediate rejections
            try:
                await self._write_login_debug_artifacts(page, "login_before_submit")

                nav_snap = await page.evaluate('''() => ({
                    userAgent: navigator.userAgent,
                    webdriver: navigator.webdriver || false,
                    languages: navigator.languages || [],
                    plugins: (navigator.plugins && navigator.plugins.length) || 0,
                    hasChrome: !!window.chrome,
                })''')
                nav_path = Path("addons/mitchell_agent/artifacts/login_debug") / "login_before_submit.navigator.json"
                nav_path.write_text(json.dumps(nav_snap, indent=2), encoding="utf-8")

                req_path = Path("addons/mitchell_agent/artifacts/login_debug") / "login_before_submit.requests.json"
                req_path.write_text(json.dumps(requests, indent=2), encoding="utf-8")

                resp_path = Path("addons/mitchell_agent/artifacts/login_debug") / "login_before_submit.responses.json"
                resp_path.write_text(json.dumps(responses, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Submit
            submitted = False
            if selectors.get("button"):
                try:
                    await page.click(selectors["button"], timeout=5000)
                    submitted = True
                except Exception:
                    submitted = False
            if not submitted:
                try:
                    await page.locator(selectors["password"]).press("Enter")
                    submitted = True
                except Exception:
                    submitted = False
            if not submitted:
                await self._write_login_debug_artifacts(page, "submit_failed")
                raise PortalError("Unable to submit login form (click/Enter failed)")

            # Immediately capture post-submit responses as well
            try:
                resp_path = Path("addons/mitchell_agent/artifacts/login_debug") / "login_post_submit.responses.json"
                resp_path.write_text(json.dumps(responses, indent=2), encoding="utf-8")
            except Exception:
                pass

            # Wait for login to complete - URL should change away from login page
            log.info("Waiting for login redirect...")
            try:
                await page.wait_for_function(
                    "(loginUrl) => !window.location.href.includes('/Login')",
                    arg=login_url,
                    timeout=cfg.playwright_nav_timeout_ms,
                )
            except Exception as e:
                await self._write_login_debug_artifacts(page, "login_timeout")
                raise PortalError(f"Login did not redirect: {e}")
            
            # Wait for page to stabilize after redirect
            await page.wait_for_load_state("networkidle", timeout=15000)
            log.info(f"Login redirected to: {page.url}")
            
            # Handle session limit popup if it appears
            await self._handle_session_limit_popup(page)
            
            # Now check for logged-in sentinel on the destination page
            if cfg.sel_logged_in_sentinel:
                try:
                    await page.locator(cfg.sel_logged_in_sentinel).first.wait_for(timeout=10000)
                    log.info("Login successful (sentinel found)")
                except Exception:
                    log.warning("Logged-in sentinel not found, but URL changed - assuming success")

            # If still on the login URL and password is visible, assume login failed.
            try:
                pw_visible = await page.locator(selectors["password"]).first.is_visible()
            except Exception:
                pw_visible = False
            if "/Login" in page.url and pw_visible:
                await self._write_login_debug_artifacts(page, "login_still_on_login_page")
                raise PortalError("Login did not advance (still on login page)")

            # Persist session
            state_path = Path(cfg.storage_state_path)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(state_path))
            
            # Return the logged-in page - DO NOT close it
            return page
        except Exception:
            await self._write_login_debug_artifacts(page, "login_exception")
            await page.close()  # Only close on error
            raise

    async def logout(self, context: BrowserContext) -> bool:
        """Properly logout from ShopKeyPro to avoid leaving sessions open.
        
        Returns True if logout was successful, False if logout couldn't be completed.
        
        VERIFIED SELECTORS (2026-01-07):
        - Cancel button: input[data-action='Cancel'] or input.grey.button[value='Cancel']
        - Logout: #logout (LI element with icon, no text)
        - Modal close (Fluid Capacities, etc.): span.close
        """
        cfg = self.cfg
        
        # Find an existing page with ShopKeyPro or open one
        page = None
        for p in context.pages:
            if 'shopkeypro.com' in p.url.lower() or 'mitchell' in p.url.lower():
                page = p
                break
        
        if not page:
            # No active ShopKeyPro page - might already be logged out
            log.info("No ShopKeyPro page found, may already be logged out")
            return True
        
        try:
            page.set_default_timeout(cfg.playwright_nav_timeout_ms)
            
            # STEP 1: Smart modal discovery - close any blocking modals
            # Try multiple times in case there are nested modals
            log.info("Step 1: Checking for open modals...")
            for attempt in range(3):
                modal_closed = False
                
                # SMART DISCOVERY: Find any visible close mechanism
                # These are ordered from most specific to most generic
                modal_close_selectors = [
                    # VERIFIED: ShopKeyPro vehicle selector Cancel button
                    "input.grey.button[value='Cancel']",
                    "input[data-action='Cancel']",
                    # VERIFIED: Data modal close (Fluid Capacities, etc.) - X button
                    "span.close",
                    # Generic close patterns
                    "button.close",
                    ".close-button",
                    "[aria-label='Close']",
                    "[aria-label='close']",
                    # Modal close icons
                    ".modal-close",
                    ".modalDialogView .close",
                    "button.close-modal",
                    # Cancel buttons
                    'button:has-text("Cancel")',
                ]
                
                for sel in modal_close_selectors:
                    try:
                        close_btn = page.locator(sel).first
                        if await close_btn.is_visible(timeout=300):
                            await close_btn.click()
                            log.info(f"Closed modal using: {sel}")
                            await human_delay(300, 500)
                            modal_closed = True
                            break  # One modal closed, loop to check for more
                    except Exception:
                        continue
                
                # If no predefined selector worked, try dynamic discovery
                if not modal_closed:
                    try:
                        # Look for any small element with 'close' in class that's visible
                        close_els = await page.query_selector_all('[class*="close"]')
                        for el in close_els[:5]:
                            try:
                                if await el.is_visible():
                                    box = await el.bounding_box()
                                    # Skip if it's a huge container
                                    if box and box['width'] < 100 and box['height'] < 100:
                                        await el.click()
                                        log.info(f"Closed modal with dynamically discovered element")
                                        modal_closed = True
                                        await human_delay(300, 500)
                                        break
                            except Exception:
                                continue
                    except Exception:
                        pass
                
                if not modal_closed:
                    break  # No more modals to close
            
            # STEP 2: Click logout
            # VERIFIED: ShopKeyPro logout is <LI id="logout"> with icon (no text)
            log.info("Step 2: Clicking logout...")
            logout_clicked = False
            
            # Primary selector - verified to work
            try:
                logout = page.locator("#logout")
                if await logout.is_visible(timeout=2000):
                    await human_delay(300, 600)
                    await logout.click()
                    logout_clicked = True
                    log.info("Clicked logout (#logout)")
            except Exception as e:
                log.warning(f"#logout click failed: {e}")
            
            # Fallback selectors
            if not logout_clicked:
                logout_selectors = [
                    '#logout a',
                    'li#logout',
                    'a:has-text("Logout")',
                    'a:has-text("Log Out")',
                    'a:has-text("Sign Out")',
                    '#logoutButton',
                    '.logout',
                    'a[href*="logout"]',
                ]
                
                for sel in logout_selectors:
                    try:
                        loc = page.locator(sel).first
                        if await loc.is_visible(timeout=1000):
                            await human_delay(300, 600)
                            await loc.click()
                            logout_clicked = True
                            log.info(f"Clicked logout using selector: {sel}")
                            break
                    except Exception:
                        continue
            
            if not logout_clicked:
                log.warning("Could not find logout button/link")
                return False
            
            # STEP 3: Confirm logout
            log.info("Step 3: Confirming logout...")
            await human_delay(1500, 2500)  # Wait for redirect
            
            # Take confirmation screenshot
            try:
                await page.screenshot(path='/tmp/logout_confirm.png')
                log.info("Screenshot saved: /tmp/logout_confirm.png")
            except Exception:
                pass
            
            # Check page state to confirm logout
            current_url = page.url.lower()
            
            # Look for indicators we're logged out
            login_indicators = [
                await page.query_selector('#loginButton'),
                await page.query_selector('#btnLogin'),
                await page.query_selector('#username'),
                await page.query_selector('input[name="username"]'),
            ]
            has_login_form = any(ind is not None for ind in login_indicators)
            
            # Look for indicators we're still logged in
            logout_button = await page.query_selector('#logout')
            logout_visible = await logout_button.is_visible() if logout_button else False
            
            # Confirm status
            if has_login_form or 'login' in current_url or 'shopkeypro.com/' == current_url.rstrip('/') or not logout_visible:
                log.info(f"LOGOUT CONFIRMED - URL: {page.url}")
                return True
            else:
                log.warning(f"LOGOUT UNCERTAIN - URL: {page.url}, login_form={has_login_form}, logout_visible={logout_visible}")
                return False
                
        except Exception as e:
            log.warning(f"Logout error: {e}")
            return False
        
    async def _handle_session_limit_popup(self, page: Page) -> None:
        """Handle the 'too many sessions' popup that appears when session limit is reached.
        
        This popup typically shows existing sessions and asks the user to select one
        to terminate, or provides an option to continue anyway.
        """
        try:
            # Wait a bit for any popup/redirect to appear
            await asyncio.sleep(2)
            
            # Check if we're on a session management page
            url_lower = page.url.lower()
            is_session_page = any(x in url_lower for x in [
                "session", "concurrent", "limit", "active", "terminate",
                "selectsession", "select-session", "managesession",
                "mitchell1.com/session",  # Mitchell session manager
            ])
            
            # Common patterns for session limit dialogs/pages
            session_popup_indicators = [
                # Text-based detection (look for visible text)
                'text=/select.*session/i',
                'text=/choose.*session/i',
                'text=/existing.*session/i',
                'text=/active.*session/i',
                'text=/terminate.*session/i',
                'text=/end.*session/i',
                'text=/session.*limit/i',
                'text=/too many.*session/i',
                'text=/already logged in/i', 
                'text=/concurrent/i',
                'text=/maximum.*session/i',
                # Radio buttons or checkboxes for session selection
                'input[type="radio"]',
                'input[type="checkbox"][name*="session" i]',
                # Tables with session info
                'table:has-text("session")',
                'table:has-text("browser")',
                'table:has-text("IP")',
                # Modal/dialog detection
                '.modal:visible',
                '[role="dialog"]:visible',
            ]
            
            popup_found = is_session_page
            found_selector = "URL pattern" if is_session_page else None
            
            if not popup_found:
                for selector in session_popup_indicators:
                    try:
                        elem = page.locator(selector).first
                        if await elem.is_visible(timeout=1000):
                            popup_found = True
                            found_selector = selector
                            log.warning("Session limit popup detected: %s", selector)
                            break
                    except Exception:
                        continue
            
            if not popup_found:
                log.info("No session limit popup detected")
                return
            
            log.warning(f"Session management page detected via: {found_selector}")
            
            # Take a screenshot for debugging
            debug_dir = Path("addons/mitchell_agent/artifacts/login_debug")
            debug_dir.mkdir(parents=True, exist_ok=True)
            try:
                await page.screenshot(path=str(debug_dir / "session_limit_popup.png"))
                html = await page.content()
                (debug_dir / "session_limit_popup.html").write_text(html, encoding="utf-8")
                (debug_dir / "session_limit_popup.url.txt").write_text(page.url, encoding="utf-8")
                log.info(f"Saved session popup debug to {debug_dir}")
            except Exception as e:
                log.warning(f"Could not save session popup debug: {e}")
            
            # Strategy: Click ALL session rows to select them, then click Commit
            # The session page shows clickable rows (no checkboxes) - click each to select
            # From screenshot: rows show "Gary Anderson" with timestamps in a table
            row_selectors = [
                'table tbody tr:has-text("Anderson")',  # Specific to Mitchell session page
                'table tbody tr:has-text("AM")',  # Rows with timestamp
                'table tbody tr:has-text("PM")',  # Rows with timestamp
                'table tbody tr',
                '.session-item',
                '.session-row',
                '[class*="session"]',
                'li:has-text("session")',
                'div[role="row"]',
                '.list-group-item',
                'tr[onclick]',  # Clickable rows
                'tr:has(td)',  # Table rows with data cells
            ]
            
            rows_clicked = 0
            for row_sel in row_selectors:
                try:
                    rows = page.locator(row_sel)
                    count = await rows.count()
                    if count > 0:
                        log.info(f"Found {count} session rows with selector: {row_sel}")
                        # Click each row to select it
                        for i in range(count):
                            try:
                                row = rows.nth(i)
                                if await row.is_visible(timeout=500):
                                    await row.click()
                                    rows_clicked += 1
                                    log.info(f"Selected session row {i+1}/{count}")
                                    await asyncio.sleep(0.3)
                            except Exception as e:
                                log.debug(f"Could not click row {i}: {e}")
                        if rows_clicked > 0:
                            break
                except Exception as e:
                    log.debug(f"Row selector {row_sel} failed: {e}")
            
            if rows_clicked > 0:
                log.info(f"Selected {rows_clicked} session(s), looking for Commit button")
            
            # Now click the Commit button (blue button at bottom right)
            continue_buttons = [
                'button:has-text("Commit")',  # Mitchell session manager uses "Commit"
                'button:has-text("Continue")',
                'button.btn-primary',
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Proceed")',
                'button:has-text("Submit")',
                'button:has-text("OK")',
                '#btnContinue',
                '#continueButton',
                '.btn-primary',
                'button:has-text("Sign In")',
                'button:has-text("Log In")',
            ]
            
            for btn_sel in continue_buttons:
                try:
                    btn = page.locator(btn_sel).first
                    if await btn.is_visible(timeout=1000):
                        log.info(f"Clicking Continue button: {btn_sel}")
                        await btn.click()
                        await page.wait_for_load_state("networkidle", timeout=15000)
                        log.info("Successfully handled session limit popup")
                        return
                except Exception:
                    continue
            
            log.warning("Could not automatically handle session limit popup - may need manual intervention")
            log.warning(f"Current URL: {page.url}")
            
        except Exception as e:
            log.warning(f"Error handling session limit popup: {e}")

    async def _discover_login_selectors(self, page: Page) -> dict[str, str]:
        """Best-effort selector discovery for typical login forms.

        Enhanced to look for placeholders, aria-labels, label 'for' attributes, and
        fall back to the first visible text input if nothing explicit is found.
        """

        discovered: dict[str, str] = {"username": "", "password": "", "button": ""}

        # Password input is usually easiest to locate.
        try:
            pw_loc = page.locator('input[type="password"]:visible').first
            if await pw_loc.count() > 0:
                discovered["password"] = 'input[type="password"]:visible'
        except Exception:
            pass

        # Username: check common attributes and placeholders.
        username_selectors = [
            'input[placeholder*="username" i]:visible',
            'input[placeholder*="user name" i]:visible',
            'input[aria-label*="username" i]:visible',
            'input[aria-label*="user name" i]:visible',
            'input[id*="user" i]:visible',
            'input[name*="user" i]:visible',
            'input[type="email"]:visible',
            'input[type="text"]:visible',
        ]
        for sel in username_selectors:
            try:
                loc = page.locator(sel).first
                if await loc.count() > 0:
                    discovered["username"] = sel
                    break
            except Exception:
                continue

        # If we still don't have a username, try label[text()="Username"] -> for=...
        if not discovered["username"]:
            try:
                label = page.locator('label:has-text("Username")').first
                if await label.count() > 0:
                    # try to get its 'for' attribute
                    fid = await label.get_attribute("for")
                    if fid:
                        candidate = f'input#{fid}:visible'
                        discovered["username"] = candidate
            except Exception:
                pass

        # If still not found, fall back to the first visible text/email input appearing before the password input
        if not discovered["username"]:
            try:
                # find text/email inputs
                text_inputs = page.locator('input[type="text"]:visible, input[type="email"]:visible')
                if await text_inputs.count() > 0:
                    discovered["username"] = 'input[type="text"]:visible'
            except Exception:
                pass

        # Submit button.
        try:
            btn = page.locator('button:has-text("Login"):visible').first
            if await btn.count() > 0:
                discovered["button"] = 'button:has-text("Login"):visible'
        except Exception:
            pass
        if not discovered["button"]:
            try:
                btn2 = page.locator('button[type="submit"]:visible').first
                if await btn2.count() > 0:
                    discovered["button"] = 'button[type="submit"]:visible'
            except Exception:
                pass

        # As a final fallback, 'input[type=submit]' if present
        if not discovered["button"]:
            try:
                btn3 = page.locator('input[type="submit"]:visible').first
                if await btn3.count() > 0:
                    discovered["button"] = 'input[type="submit"]:visible'
            except Exception:
                pass

        return discovered

    async def _write_login_debug_artifacts(self, page: Page, tag: str) -> None:
        """Write basic debug artifacts to help diagnose login issues."""

        try:
            out_dir = Path("addons/mitchell_agent/artifacts") / "login_debug"
            out_dir.mkdir(parents=True, exist_ok=True)

            safe_tag = "".join(c for c in tag if c.isalnum() or c in {"-", "_"})[:64] or "debug"
            (out_dir / f"{safe_tag}.url.txt").write_text(page.url, encoding="utf-8")
            (out_dir / f"{safe_tag}.html").write_text(await page.content(), encoding="utf-8")
            await page.screenshot(path=str(out_dir / f"{safe_tag}.png"), full_page=True)
        except Exception:
            pass

    async def open_task_page(self, context: BrowserContext) -> Page:
        cfg = self.cfg
        if not cfg.mitchell_base_url:
            raise PortalError("MITCHELL_BASE_URL not configured")

        # When using CDP (connecting to existing browser), try to reuse an existing ShopKey page
        # instead of creating a new one that might redirect differently
        existing_pages = context.pages
        for page in existing_pages:
            if 'shopkeypro.com' in page.url.lower() or 'mitchell' in page.url.lower():
                log.info(f"Reusing existing page: {page.url}")
                page.set_default_timeout(cfg.playwright_nav_timeout_ms)
                return page
        
        # No existing ShopKey page found - create a new one
        page = await context.new_page()
        page.set_default_timeout(cfg.playwright_nav_timeout_ms)
        await page.goto(cfg.mitchell_base_url, wait_until="domcontentloaded")
        return page

    async def select_vehicle(self, page: Page, year: str, make: str, model: str, engine: str) -> None:
        """Select vehicle using ShopKeyPro's custom vehicle selector UI.
        
        The UI uses a two-panel approach:
        - Left panel (#qualifierTypeSelector): tabs for Year, Make, Model, Engine
        - Right panel (#qualifierValueSelector): list of values to select
        """
        cfg = self.cfg
        
        # Check if the vehicle selector container is already visible
        shopkey_selector = await page.query_selector('#VehicleSelectorContainer')
        
        if not shopkey_selector:
            # Need to open the vehicle selector panel
            # Step 1: Click the "Select Vehicle" button to open the panel
            select_vehicle_btn = await page.query_selector('#vehicleSelectorButton')
            if select_vehicle_btn:
                log.info("Opening vehicle selector panel")
                await human_delay(300, 700)
                await select_vehicle_btn.click()
                await human_delay(400, 900)  # Wait for panel to open
            
            # Step 2: Expand the "Vehicle Selection" accordion item
            vehicle_selection_header = await page.query_selector('h1:has-text("Vehicle Selection")')
            if vehicle_selection_header:
                log.info("Expanding Vehicle Selection accordion")
                await human_delay(200, 500)
                await vehicle_selection_header.click()
                await human_delay(400, 800)
            
            # Re-check for the selector container
            shopkey_selector = await page.query_selector('#VehicleSelectorContainer')
        
        if shopkey_selector:
            # ShopKeyPro custom vehicle selector
            log.info("Using ShopKeyPro custom vehicle selector")
            
            async def select_qualifier(tab_class: str, value: str):
                """Click a tab and then select a value from the list."""
                # Click the tab (Year, Make, Model, Engine)
                tab = page.locator(f'#qualifierTypeSelector li.{tab_class}')
                await human_delay(200, 600)
                await tab.click()
                await human_delay(300, 700)  # Wait for UI to update
                
                # Find and click the value in the right panel
                value_item = page.locator(f'#qualifierValueSelector li.qualifier:has-text("{value}")')
                try:
                    await human_delay(150, 400)
                    await value_item.first.click(timeout=5000)
                    await human_delay(250, 600)
                except Exception as e:
                    log.warning(f"Could not select {tab_class}={value}: {e}")
                    raise PortalError(f"Could not select {tab_class}={value}")
            
            async def select_first_available(tab_class: str):
                """Click a tab and select the first available option (for optional fields)."""
                tab = page.locator(f'#qualifierTypeSelector li.{tab_class}')
                # Check if tab is disabled
                tab_class_attr = await tab.get_attribute('class') or ''
                if 'disabled' in tab_class_attr:
                    log.info(f"Skipping disabled tab: {tab_class}")
                    return False
                
                await human_delay(200, 500)
                await tab.click()
                await human_delay(300, 600)
                
                # Click the first qualifier option
                first_item = page.locator('#qualifierValueSelector li.qualifier').first
                try:
                    await human_delay(150, 400)
                    await first_item.click(timeout=3000)
                    await human_delay(250, 500)
                    return True
                except Exception:
                    log.info(f"No options available for {tab_class}")
                    return False
            
            # Select Year
            await select_qualifier('year', year)
            
            # Select Make
            await select_qualifier('make', make)
            
            # Select Model  
            await select_qualifier('model', model)
            
            # Select Engine
            await select_qualifier('engine', engine)
            
            # Handle Submodel if required (select first option)
            await select_first_available('submodel')
            
            # Handle Options if required (select first option or skip)
            await select_first_available('options')
            
            # Wait for the button to become enabled
            use_btn = page.locator('input[data-action="SelectComplete"]:not([disabled])')
            try:
                await use_btn.wait_for(state="visible", timeout=5000)
            except Exception:
                # Button still disabled - try clicking it anyway or check what's needed
                log.warning("Use This Vehicle button still disabled, attempting click anyway")
            
            # Click "Use This Vehicle" button
            await human_delay(400, 900)
            use_btn_any = page.locator('input[data-action="SelectComplete"]')
            await use_btn_any.click(force=True)
            await page.wait_for_load_state("networkidle")
            
        else:
            # Standard dropdown-based selector (original implementation)
            await self.ensure_selectors(page)
            required = [
                ("SEL_YEAR_DROPDOWN", self._sel("sel_year_dropdown")),
                ("SEL_MAKE_DROPDOWN", self._sel("sel_make_dropdown")),
                ("SEL_MODEL_DROPDOWN", self._sel("sel_model_dropdown")),
                ("SEL_ENGINE_DROPDOWN", self._sel("sel_engine_dropdown")),
                ("SEL_VEHICLE_APPLY_BUTTON", self._sel("sel_vehicle_apply_button")),
            ]
            missing = [name for name, sel in required if not sel]
            if missing:
                raise PortalError(f"Vehicle selectors missing: {', '.join(missing)}")

            await page.select_option(self._sel("sel_year_dropdown"), label=year)
            await page.select_option(self._sel("sel_make_dropdown"), label=make)
            await page.select_option(self._sel("sel_model_dropdown"), label=model)
            await page.select_option(self._sel("sel_engine_dropdown"), label=engine)
            await page.click(self._sel("sel_vehicle_apply_button"))
            await page.wait_for_load_state("networkidle")

    async def search_and_open(self, page: Page, query: str) -> None:
        """Search for technical information using ShopKeyPro's search interface.
        
        The search UI has:
        - Input field with placeholder "Enter Codes, Components or Symptoms"
        - Blue magnifying glass button to submit
        - Optional dropdown to switch between "Search" and "Part #" modes
        """
        # First, try ShopKeyPro-specific search selectors
        # The search input is inside a container, look for the main search box
        search_input = await page.query_selector('input.searchBox[placeholder*="Enter Codes"]')
        if not search_input:
            search_input = await page.query_selector('input[placeholder*="Codes, Components"]')
        if not search_input:
            search_input = await page.query_selector('input[placeholder*="Components or Symptoms"]')
        
        if search_input:
            log.info("Using ShopKeyPro search interface")
            # Clear any existing text and enter the query with human-like typing
            await human_delay(300, 700)
            await search_input.click()
            await human_delay(150, 400)
            await search_input.fill("")
            
            # Type the query character by character with slight random delays
            for char in query:
                await search_input.type(char, delay=random.randint(30, 120))
            await human_delay(200, 500)
            
            # Find the search submit button - ShopKeyPro uses button.submit class
            # The button is a sibling of the searchField container
            search_btn = await page.query_selector('button.submit')
            if not search_btn:
                search_btn = await page.query_selector('button.search-btn')
            if not search_btn:
                # Try finding by the icon or nearby button
                search_btn = await page.query_selector('button:has(svg[class*="search"])')
            if not search_btn:
                # Look for a button in the parent container
                search_btn = await page.query_selector('.searchField + button.submit')
            if not search_btn:
                search_btn = await page.query_selector('button[type="submit"]')
            
            if search_btn:
                log.info("Clicking search button")
                await human_delay(300, 800)
                await search_btn.click()
            else:
                # Fallback: press Enter in the search input
                log.info("No search button found, pressing Enter")
                await human_delay(200, 500)
                await search_input.press("Enter")
            
            # Wait for results to load
            await page.wait_for_load_state("networkidle")
            await human_delay(500, 1200)  # Give time for results to render
            
            # Look for search results - could be in various containers
            # First check if we landed on a results page
            results_container = await page.query_selector('.search-results')
            if not results_container:
                results_container = await page.query_selector('#searchResults')
            if not results_container:
                results_container = await page.query_selector('[class*="result"]')
            
            # Click the first result if there is one
            if results_container:
                first_link = await results_container.query_selector('a')
                if first_link:
                    log.info("Clicking first search result")
                    await human_delay(400, 900)
                    await first_link.click()
                    await page.wait_for_load_state("domcontentloaded")
            else:
                log.info("No results container found, page may have navigated directly to content")
            
            return
        
        # Fallback to configured selectors
        await self.ensure_selectors(page)
        required = [
            ("SEL_SEARCH_INPUT", self._sel("sel_search_input")),
            ("SEL_SEARCH_SUBMIT", self._sel("sel_search_submit")),
            ("SEL_RESULTS_CONTAINER", self._sel("sel_results_container")),
        ]
        missing = [name for name, sel in required if not sel]
        if missing:
            raise PortalError(f"Search selectors missing: {', '.join(missing)}")

        await page.fill(self._sel("sel_search_input"), query)
        await page.click(self._sel("sel_search_submit"))
        await page.locator(self._sel("sel_results_container")).first.wait_for()

        # Default behavior: click the first result link inside results container.
        # Override by tightening SEL_RESULTS_CONTAINER to point at the desired element.
        await page.locator(self._sel("sel_results_container")).locator("a").first.click()
        await page.wait_for_load_state("domcontentloaded")

    async def extract(self, page: Page, artifacts_dir: Path) -> tuple[str, str, str, list[dict]]:
        """Extract content from the current page.
        
        For ShopKeyPro, content is typically directly on the page, not in an iframe.
        We'll try ShopKeyPro-specific extraction first, then fall back to configured selectors.
        """
        cfg = self.cfg
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # First, try ShopKeyPro-specific extraction (no iframe)
        # Look for the search results content
        results_title = await page.query_selector('.resultsTitle')
        if results_title:
            log.info("Using ShopKeyPro search results extraction")
            
            # Get the page title from h1 or results title
            page_title = ""
            try:
                h1 = await page.query_selector('h1')
                if h1:
                    page_title = (await h1.inner_text()).strip()
            except Exception:
                pass
            if not page_title:
                try:
                    page_title = (await results_title.inner_text()).strip()
                except Exception:
                    page_title = ""
            
            # Get the main content area - look for search results or content divs
            html = ""
            content_selectors = [
                '#searchResultsContainer',
                '.search-results',
                '#ApplicationRegion',
                '.application-content',
                'main',
                '#main-content'
            ]
            
            for sel in content_selectors:
                el = await page.query_selector(sel)
                if el:
                    try:
                        html = await el.inner_html()
                        if len(html) > 100:  # Make sure we got meaningful content
                            log.info(f"Extracted content from {sel} ({len(html)} chars)")
                            break
                    except Exception:
                        continue
            
            # If no specific container found, get body content
            if not html or len(html) < 100:
                try:
                    body = await page.query_selector('body')
                    if body:
                        html = await body.inner_html()
                        log.info(f"Extracted full body content ({len(html)} chars)")
                except Exception:
                    pass
            
            # Get breadcrumb if available
            breadcrumb = ""
            try:
                bc_el = await page.query_selector('.breadcrumb, #breadcrumb, .crumbs')
                if bc_el:
                    breadcrumb = (await bc_el.inner_text()).strip()
            except Exception:
                pass
            
            assets: list[dict] = []
            if cfg.download_assets:
                assets = await self._download_assets_from_page(page, artifacts_dir)
            
            return html, page_title, breadcrumb, assets
        
        # Fall back to iframe-based extraction if configured
        await self.ensure_selectors(page)
        if not self._sel("sel_content_frame"):
            raise PortalError("SEL_CONTENT_FRAME not configured")
        if not self._sel("sel_tech_content_root"):
            raise PortalError("SEL_TECH_CONTENT_ROOT not configured")

        artifacts_dir.mkdir(parents=True, exist_ok=True)

        # Content may be inside an iframe; SEL_CONTENT_FRAME should match the iframe element.
        frame = page.frame_locator(self._sel("sel_content_frame"))

        html = await frame.locator(self._sel("sel_tech_content_root")).evaluate("(el) => el.innerHTML")

        page_title = ""
        breadcrumb = ""
        if self._sel("sel_page_title"):
            try:
                page_title = (
                    await frame.locator(self._sel("sel_page_title")).first.inner_text()
                ).strip()
            except Exception:
                page_title = ""
        if self._sel("sel_breadcrumb"):
            try:
                breadcrumb = (
                    await frame.locator(self._sel("sel_breadcrumb")).first.inner_text()
                ).strip()
            except Exception:
                breadcrumb = ""

        assets: list[dict] = []
        if cfg.download_assets:
            assets = await self._download_assets(page, frame, artifacts_dir)

        return html, page_title, breadcrumb, assets

    async def _download_assets(self, page: Page, frame_locator, artifacts_dir: Path) -> list[dict]:
        cfg = self.cfg
        exts = cfg.asset_extensions

        # Collect candidate asset URLs from the frame (img/src and link/href)
        urls: set[str] = set()
        try:
            img_srcs = await frame_locator.locator("img").evaluate_all(
                "(els) => els.map(e => e.getAttribute('src')).filter(Boolean)"
            )
            for u in img_srcs:
                urls.add(u)
        except Exception:
            pass

        try:
            hrefs = await frame_locator.locator("a,link").evaluate_all(
                "(els) => els.map(e => e.getAttribute('href')).filter(Boolean)"
            )
            for u in hrefs:
                urls.add(u)
        except Exception:
            pass

        # Filter to requested extensions only
        def ok(u: str) -> bool:
            ul = u.lower()
            return any(ul.endswith(ext) for ext in exts)

        asset_urls = [u for u in urls if isinstance(u, str) and ok(u)]

        downloaded: list[dict] = []
        for u in asset_urls:
            try:
                # Make absolute
                abs_url = u
                if abs_url.startswith("//"):
                    abs_url = "https:" + abs_url
                elif abs_url.startswith("/"):
                    abs_url = cfg.mitchell_base_url.rstrip("/") + abs_url

                resp = await page.request.get(abs_url)
                if not resp.ok:
                    continue
                data = await resp.body()
                name = abs_url.split("?", 1)[0].split("/")[-1] or "asset"
                out_path = artifacts_dir / name
                out_path.write_bytes(data)
                downloaded.append({"url": abs_url, "path": str(out_path)})
            except Exception:
                continue

        return downloaded

    async def _download_assets_from_page(self, page: Page, artifacts_dir: Path) -> list[dict]:
        """Download assets directly from the page (not iframe)."""
        cfg = self.cfg
        exts = cfg.asset_extensions

        urls: set[str] = set()
        try:
            img_srcs = await page.evaluate(
                "() => Array.from(document.querySelectorAll('img')).map(e => e.getAttribute('src')).filter(Boolean)"
            )
            for u in img_srcs:
                urls.add(u)
        except Exception:
            pass

        try:
            hrefs = await page.evaluate(
                "() => Array.from(document.querySelectorAll('a,link')).map(e => e.getAttribute('href')).filter(Boolean)"
            )
            for u in hrefs:
                urls.add(u)
        except Exception:
            pass

        def ok(u: str) -> bool:
            ul = u.lower()
            return any(ul.endswith(ext) for ext in exts)

        asset_urls = [u for u in urls if isinstance(u, str) and ok(u)]

        downloaded: list[dict] = []
        for u in asset_urls:
            try:
                abs_url = u
                if abs_url.startswith("//"):
                    abs_url = "https:" + abs_url
                elif abs_url.startswith("/"):
                    abs_url = cfg.mitchell_base_url.rstrip("/") + abs_url

                resp = await page.request.get(abs_url)
                if not resp.ok:
                    continue
                data = await resp.body()
                name = abs_url.split("?", 1)[0].split("/")[-1] or "asset"
                out_path = artifacts_dir / name
                out_path.write_bytes(data)
                downloaded.append({"url": abs_url, "path": str(out_path)})
            except Exception:
                continue

        return downloaded
