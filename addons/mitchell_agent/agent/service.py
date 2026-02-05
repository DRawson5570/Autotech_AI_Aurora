"""
Mitchell Polling Agent
======================
Standalone service that runs at customer sites.
Polls the server for pending requests, executes them using browser automation,
and returns results.

Features:
- Ollama-powered vehicle navigation with native tool calling
- Clarification flow for missing vehicle options
- Browser automation via Chrome + CDP

Usage:
    python -m addons.mitchell_agent.agent.service

Or via Docker:
    docker run -d mitchell-agent
"""

import asyncio
import os
import time
import logging
from typing import Optional
from pathlib import Path

import httpx

from ..api import MitchellAPI, SessionLimitError
from .config import AgentConfig, load_config
from .navigator import Navigator, NavigatorBackend, check_ollama_model

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mitchell-agent")

# Global session timeout - if no activity for this long, logout
SESSION_TIMEOUT_SECONDS = 300  # 5 minutes


class MitchellAgent:
    """
    Polling agent that executes Mitchell requests.
    
    Runs at the customer site with access to their ShopKeyPro account.
    Uses LLM-powered navigation for autonomous vehicle selection (Gemini or Ollama).
    
    Session Management:
    - Stays logged in between clarification requests (avoids re-login)
    - Automatically logs out after SESSION_TIMEOUT_SECONDS of inactivity
    - Always logs out after successful completion or fatal error
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self._api: Optional[MitchellAPI] = None
        self._navigator: Optional[Navigator] = None
        self._running = False
        self._http_clients: dict = {}  # Map of server_url -> httpx.AsyncClient
        
        # Session state
        self._session_logged_in = False
        self._last_activity_time: Optional[float] = None
        self._session_timeout_task: Optional[asyncio.Task] = None
    
    async def start(self):
        """Start the agent."""
        logger.info(f"Starting Mitchell Agent for shop: {self.config.shop_id}")
        logger.info(f"Server URLs: {self.config.server_urls}")
        
        # Get backend configuration
        # Priority: NAVIGATOR_BACKEND env var > config > default (gemini)
        backend_str = os.environ.get('NAVIGATOR_BACKEND', getattr(self.config, 'navigator_backend', 'gemini'))
        try:
            backend = NavigatorBackend(backend_str.lower())
        except ValueError:
            logger.warning(f"Unknown backend '{backend_str}', defaulting to gemini")
            backend = NavigatorBackend.GEMINI
        
        logger.info(f"Navigator backend: {backend.value}")
        
        # Backend-specific setup
        if backend == NavigatorBackend.GEMINI:
            gemini_key = os.environ.get('GEMINI_API_KEY', '')
            if not gemini_key:
                logger.error("GEMINI_API_KEY not set. Set it or use NAVIGATOR_BACKEND=ollama")
                return False
            logger.info("Gemini API key configured")
        elif backend == NavigatorBackend.OLLAMA:
            ollama_model = getattr(self.config, 'ollama_model', 'qwen3:8b')
            ollama_url = getattr(self.config, 'ollama_url', 'http://localhost:11434')
            logger.info(f"Checking local Ollama model: {ollama_model}...")
            has_local = await check_ollama_model(ollama_model, ollama_url)
            if has_local:
                logger.info(f"Local Ollama model {ollama_model} ready")
            else:
                logger.error(f"Ollama model {ollama_model} not available. Install with: ollama pull {ollama_model}")
                return False
        else:
            logger.info("Using server-side navigation")
        
        # Initialize Mitchell API (browser automation)
        self._api = MitchellAPI(
            headless=self.config.headless,
            debug_screenshots=self.config.debug_screenshots
        )
        logger.info(f"Mitchell API initialized (debug_screenshots={self.config.debug_screenshots})")
        
        # Ensure browser is in a clean logged-out state before starting
        # This handles cases where Chrome was left logged in from a previous run
        logger.info("Ensuring browser is in clean state...")
        clean = await self._api.ensure_clean_state()
        if clean:
            logger.info("✅ Browser ready in clean logged-out state")
        else:
            logger.warning("⚠️ Could not ensure clean state, proceeding anyway")
        
        # Store navigation config for later (navigator created per request after login)
        self._navigation_config = {
            'backend': backend,
            'gemini_api_key': os.environ.get('GEMINI_API_KEY', ''),
            'gemini_model': os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash'),
            'ollama_url': getattr(self.config, 'ollama_url', 'http://localhost:11434'),
            'ollama_model': getattr(self.config, 'ollama_model', 'qwen3:8b'),
            'server_url': self.config.server_url,  # Primary server for navigation
            'shop_id': self.config.shop_id
        }
        logger.info(f"Navigator configured: {backend.value}")
        
        # Initialize HTTP clients for each server
        self._http_clients = {}
        for server_url in self.config.server_urls:
            self._http_clients[server_url] = httpx.AsyncClient(
                base_url=server_url,
                timeout=30.0
            )
            logger.info(f"  HTTP client initialized for: {server_url}")
        
        self._running = True
        
        # Start session timeout watcher
        self._session_timeout_task = asyncio.create_task(self._session_timeout_watcher())
        
        await self._poll_loop()
        
        return True
    
    async def stop(self):
        """Stop the agent."""
        logger.info("Stopping agent...")
        self._running = False
        
        # Cancel session timeout watcher
        if self._session_timeout_task:
            self._session_timeout_task.cancel()
            try:
                await self._session_timeout_task
            except asyncio.CancelledError:
                pass
        
        # Ensure logged out
        await self._safe_logout()
        
        if self._api:
            await self._api.disconnect()
        
        # Close all HTTP clients
        for server_url, client in self._http_clients.items():
            await client.aclose()
        
        logger.info("Agent stopped")
    
    async def _session_timeout_watcher(self):
        """Background task that logs out after inactivity timeout."""
        while self._running:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            if self._session_logged_in and self._last_activity_time:
                idle_time = time.time() - self._last_activity_time
                if idle_time > SESSION_TIMEOUT_SECONDS:
                    logger.info(f"Session timeout ({idle_time:.0f}s idle) - logging out")
                    await self._safe_logout()
    
    async def _safe_logout(self):
        """Safely logout and cleanup, handling any errors."""
        if not self._session_logged_in:
            return
        
        try:
            if self._api:
                # Close any modals first
                if self._api._page:
                    try:
                        await self._api._page.evaluate('''() => {
                            document.querySelector("input[data-action='Cancel']")?.click();
                            document.querySelector(".modalDialogView .close")?.click();
                        }''')
                        await asyncio.sleep(0.3)
                    except:
                        pass
                
                await self._api.logout()
                logger.info("✅ Session logged out")
        except Exception as e:
            logger.error(f"Error during logout: {e}")
        finally:
            self._session_logged_in = False
            self._last_activity_time = None
    
    def _update_activity(self):
        """Update last activity timestamp."""
        self._last_activity_time = time.time()
    
    async def _poll_loop(self):
        """Main polling loop."""
        consecutive_errors = 0
        max_consecutive_errors = 10
        
        logger.info("=" * 50)
        logger.info("🔄 Agent ready and polling for requests...")
        logger.info(f"   Servers: {', '.join(self.config.server_urls)}")
        logger.info(f"   Shop ID: {self.config.shop_id}")
        logger.info(f"   Poll interval: {self.config.poll_interval}s")
        logger.info("=" * 50)
        
        while self._running:
            try:
                # Poll ALL servers for pending requests
                found_work = False
                for server_url in self.config.server_urls:
                    pending = await self._get_pending_requests(server_url)
                    
                    if pending:
                        logger.info(f"Got {len(pending)} pending request(s) from {server_url}")
                        for request in pending:
                            # Tag request with source server for result submission
                            request['_source_server'] = server_url
                            await self._process_request(request)
                        found_work = True
                        consecutive_errors = 0
                
                if not found_work:
                    # No work from any server, sleep before next poll
                    await asyncio.sleep(self.config.poll_interval)
                    consecutive_errors = 0
                    
            except httpx.HTTPError as e:
                consecutive_errors += 1
                logger.warning(f"HTTP error polling server: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, stopping agent")
                    self._running = False
                else:
                    await asyncio.sleep(self.config.error_backoff)
                    
            except Exception as e:
                consecutive_errors += 1
                logger.exception(f"Error in poll loop: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error("Too many consecutive errors, stopping agent")
                    self._running = False
                else:
                    await asyncio.sleep(self.config.error_backoff)
    
    async def _get_pending_requests(self, server_url: str) -> list:
        """Get pending requests from a specific server."""
        client = self._http_clients.get(server_url)
        if not client:
            logger.warning(f"No HTTP client for {server_url}")
            return []
        
        response = await client.get(
            f"/api/mitchell/pending/{self.config.shop_id}"
        )
        response.raise_for_status()
        
        # Handle empty response (no pending requests)
        if not response.content or response.content == b'':
            return []
        
        try:
            data = response.json()
            return data.get("requests", [])
        except Exception:
            # Empty or invalid JSON = no pending requests
            return []
    
    async def _claim_request(self, request_id: str, server_url: str) -> bool:
        """Claim a request before processing."""
        client = self._http_clients.get(server_url)
        if not client:
            logger.warning(f"No HTTP client for {server_url}")
            return False
        
        try:
            response = await client.post(
                f"/api/mitchell/claim/{request_id}"
            )
            response.raise_for_status()
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Request {request_id} already claimed or not found")
                return False
            raise
    
    async def _submit_result(self, request_id: str, result: dict, server_url: str):
        """Submit result to the originating server."""
        client = self._http_clients.get(server_url)
        if not client:
            logger.warning(f"No HTTP client for {server_url}")
            return
        
        # Ensure only valid fields are sent
        payload = {
            "success": result.get("success", False),
            "data": result.get("data"),
            "error": result.get("error"),
            "tool_used": result.get("tool_used"),
            "execution_time_ms": result.get("execution_time_ms"),
            "images": result.get("images"),  # Include images if present
            "tokens_used": result.get("tokens_used"),  # Include token usage for billing
        }
        
        try:
            response = await client.post(
                f"/api/mitchell/result/{request_id}",
                json=payload
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to submit result: {e}")
            logger.error(f"Payload was: {payload}")
            raise
    
    async def _process_request(self, request: dict):
        """
        Process a single request.
        
        Session management:
        - Reuses existing session if already logged in
        - Does NOT logout after clarification requests (keeps session open)
        - Logs out after successful completion or fatal error
        - Session timeout watcher handles abandoned sessions
        """
        request_id = request["id"]
        tool = request["tool"]
        vehicle = request["vehicle"]
        params = request.get("params", {})
        user_id = request.get("user_id")  # For billing if server-side navigation
        source_server = request.get("_source_server", self.config.server_urls[0])
        
        logger.info(f"Processing request {request_id}: {tool} for {vehicle['year']} {vehicle['make']} {vehicle['model']}")
        logger.info(f"  Source server: {source_server}")
        
        # Claim the request
        if not await self._claim_request(request_id, source_server):
            return
        
        start_time = time.time()
        self._update_activity()
        
        needs_clarification = False
        should_logout = False
        
        try:
            # Login to ShopKeyPro (or reuse existing session)
            if not self._session_logged_in:
                logger.info("Logging in to ShopKeyPro...")
                connected = await self._api.connect()
                if not connected:
                    raise Exception("Failed to connect to ShopKeyPro")
                self._session_logged_in = True
            else:
                logger.info("Reusing existing ShopKeyPro session")
            
            self._update_activity()
            
            # Initialize navigator with logged-in page
            config = self._navigation_config
            self._navigator = Navigator(
                page=self._api._page,
                backend=config['backend'],
                gemini_api_key=config['gemini_api_key'],
                gemini_model=config['gemini_model'],
                ollama_url=config['ollama_url'],
                ollama_model=config['ollama_model'],
                server_url=config['server_url'],
                shop_id=config['shop_id'],
            )
            self._navigator.request_id = request_id
            
            # Skip vehicle navigation for lookup_vehicle and query_by_plate
            # - lookup_vehicle does its own navigation
            # - query_by_plate does lookup first, then navigates
            if tool in ("lookup_vehicle", "query_by_plate"):
                logger.info(f"Skipping initial vehicle navigation for {tool} tool")
                nav_result = {"success": True}
            else:
                # Navigate to the vehicle
                nav_result = await self._navigate_to_vehicle(request_id, vehicle)
            self._update_activity()
            
            if not nav_result["success"]:
                # Check if this is a clarification request (needs more info)
                missing_info = nav_result.get("missing_info", [])
                if missing_info:
                    needs_clarification = True
                    logger.info("Clarification needed - keeping session open")
                    
                    # Include structured clarification data for the tool to use
                    missing = missing_info[0]
                    clarification_data = {
                        "clarification_needed": True,
                        "missing_field": missing["option"].lower().replace(" ", "_"),
                        "options": missing["values"],
                        "message": missing["message"]
                    }
                    
                    execution_time = int((time.time() - start_time) * 1000)
                    await self._submit_result(request_id, {
                        "success": False,
                        "error": nav_result.get("error", "Vehicle navigation failed"),
                        "data": clarification_data,
                        "tool_used": tool,
                        "execution_time_ms": execution_time
                    }, source_server)
                else:
                    # Actual navigation failure - logout
                    should_logout = True
                    
                    execution_time = int((time.time() - start_time) * 1000)
                    await self._submit_result(request_id, {
                        "success": False,
                        "error": nav_result.get("error", "Vehicle navigation failed"),
                        "tool_used": tool,
                        "execution_time_ms": execution_time
                    }, source_server)
                return
            
            # Vehicle selected, now execute the tool
            logger.info(f"[DEBUG] Navigation succeeded, now executing tool: {tool}")
            logger.info(f"[DEBUG] Current page URL: {self._api._page.url}")
            
            # Take a screenshot before tool execution
            try:
                await self._api._page.screenshot(path='/tmp/before_tool_execution.png')
                logger.info("[DEBUG] Screenshot saved: /tmp/before_tool_execution.png")
            except Exception as e:
                logger.info(f"[DEBUG] Could not take screenshot: {e}")
            
            result = await self._execute_tool(tool, vehicle, params)
            logger.info(f"[DEBUG] Tool result: success={result.get('success')}, error={result.get('error')}")
            self._update_activity()
            execution_time = int((time.time() - start_time) * 1000)
            
            # Include auto_selected from nav_result if any
            auto_selected = nav_result.get("auto_selected")
            
            # Submit result (including images if present)
            await self._submit_result(request_id, {
                "success": result.get("success", False),
                "data": result.get("data"),
                "error": result.get("error"),
                "tool_used": tool,
                "execution_time_ms": execution_time,
                "images": result.get("images"),
                "auto_selected": auto_selected,  # Report auto-selected options to the user
            }, source_server)
            
            # Successful completion - logout
            should_logout = True
            logger.info(f"Request {request_id} completed in {execution_time}ms")
        
        except SessionLimitError as e:
            # Session limit error - don't try to logout since we never logged in
            logger.warning(f"Session limit reached: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            await self._submit_result(request_id, {
                "success": False,
                "error": str(e),
                "tool_used": tool,
                "execution_time_ms": execution_time
            }, source_server)
            
            # Don't set should_logout - we never logged in
            self._session_logged_in = False
            
        except Exception as e:
            logger.exception(f"Error processing request {request_id}: {e}")
            execution_time = int((time.time() - start_time) * 1000)
            
            await self._submit_result(request_id, {
                "success": False,
                "error": str(e),
                "tool_used": tool,
                "execution_time_ms": execution_time
            }, source_server)
            
            # Error - logout to ensure clean state
            should_logout = True
            
        finally:
            # Only logout if we completed or had a fatal error
            # Don't logout if we're waiting for clarification
            if should_logout:
                logger.info("Logging out of ShopKeyPro...")
                await self._safe_logout()
            elif needs_clarification:
                logger.info("Session kept open for clarification follow-up")
    
    async def _navigate_to_vehicle(self, request_id: str, vehicle: dict) -> dict:
        """
        Navigate to a vehicle using Ollama Navigator.
        
        If additional info is needed (submodel, drive type, etc.), returns an error
        telling the user what info to include in their next request.
        """
        import re
        
        # Debug: log incoming vehicle dict
        logger.info(f"[DEBUG] Vehicle dict received: {vehicle}")
        
        # Try to extract drive_type from any field if not explicitly provided
        drive_type = vehicle.get("drive_type")
        logger.info(f"[DEBUG] drive_type from vehicle.get(): {drive_type}")
        
        if not drive_type:
            # Look for drive type patterns in submodel, body_style, or engine fields
            all_text = " ".join([
                str(vehicle.get("submodel", "")),
                str(vehicle.get("body_style", "")),
                str(vehicle.get("engine", ""))
            ])
            drive_match = re.search(r'\b(4WD|AWD|RWD|FWD|2WD|4x4|4X4)\b', all_text, re.IGNORECASE)
            if drive_match:
                drive_type = drive_match.group(1).upper()
                logger.info(f"Extracted drive_type '{drive_type}' from vehicle fields")
        
        # Build goal from vehicle info
        goal_parts = [str(vehicle["year"]), vehicle["make"], vehicle["model"]]
        if vehicle.get("engine"):
            goal_parts.append(vehicle["engine"])
        if vehicle.get("submodel"):
            goal_parts.append(vehicle["submodel"])
        if vehicle.get("body_style"):
            goal_parts.append(vehicle["body_style"])
        if drive_type:
            goal_parts.append(drive_type)
        
        goal = " ".join(goal_parts)
        logger.info(f"Navigating to: {goal}")
        
        # Simple clarification handler - just record what's needed and abort
        missing_info = []
        
        async def handle_clarification(option_name: str, available_values: list, message: str) -> Optional[str]:
            """Record missing info and return None to abort navigation."""
            logger.info(f"Missing info: {option_name} - options: {available_values}")
            missing_info.append({
                "option": option_name,
                "values": available_values,
                "message": message
            })
            # Return None to signal navigation should abort
            return None
        
        # Set up navigator with clarification handler
        self._navigator.on_clarification_needed = handle_clarification
        
        # Navigate!
        result = await self._navigator.navigate(goal)
        
        # If we collected missing info, close the selector and return helpful error
        if missing_info:
            # Close the vehicle selector dialog before returning
            try:
                cancel_btn = self._navigator.page.locator("input[data-action='Cancel']")
                if await cancel_btn.count() > 0:
                    await cancel_btn.click(timeout=3000)
                    logger.info("Closed vehicle selector after clarification needed")
                    await asyncio.sleep(0.5)
            except Exception as e:
                logger.debug(f"Could not close vehicle selector: {e}")
            
            info = missing_info[0]  # Usually just one thing missing
            options_str = ", ".join(info["values"][:6])  # Show first 6 options
            if len(info["values"]) > 6:
                options_str += f", ... ({len(info['values'])} total)"
            
            error_msg = (
                f"Additional information needed: {info['option']}. "
                f"Please include one of these in your request: {options_str}. "
                f"Example: '2018 Ford F-150 XLT with 5.0L engine'"
            )
            return {
                "success": False,
                "error": error_msg,
                "missing_info": missing_info
            }
        
        return {
            "success": result.success,
            "error": result.error,
            "auto_selected": result.auto_selected,  # Pass through any auto-selected options
        }
    
    async def _execute_query_by_plate(self, params: dict) -> dict:
        """
        Execute plate lookup followed by target tool in one operation.
        
        This chains:
        1. lookup_vehicle to decode plate → year/make/model/engine
        2. The requested target_tool with the decoded vehicle
        
        Args:
            params: Dict with plate, state, target_tool, and tool-specific params
            
        Returns:
            Result from the target tool (not the lookup)
        """
        plate = params.get("plate")
        state = params.get("state")
        target_tool = params.get("target_tool")
        
        # Sanitize plate - remove spaces and dashes (e.g., "AUE 709" -> "AUE709")
        if plate:
            plate = plate.replace(" ", "").replace("-", "").upper()
        
        if not plate or not state:
            return {"success": False, "error": "Both plate and state are required"}
        if not target_tool:
            return {"success": False, "error": "target_tool is required"}
        
        logger.info(f"Query by plate: {plate} {state} -> {target_tool}")
        
        # Step 1: Lookup the vehicle
        lookup_result = await self._api.lookup_vehicle(
            plate=plate,
            state=state
        )
        
        if not lookup_result.get("success"):
            return {
                "success": False,
                "error": f"Plate lookup failed: {lookup_result.get('error', 'Unknown error')}"
            }
        
        # Extract vehicle info from lookup result
        lookup_data = lookup_result.get("data", {})
        year = lookup_data.get("year")
        make = lookup_data.get("make")
        model = lookup_data.get("model")
        engine = lookup_data.get("engine")
        vin = lookup_data.get("vin")
        
        if not year or not make or not model:
            return {
                "success": False,
                "error": f"Plate lookup returned incomplete vehicle info: {lookup_data}"
            }
        
        logger.info(f"Plate decoded to: {year} {make} {model} {engine} (VIN: {vin})")
        
        # Build vehicle dict for the target tool
        vehicle = {
            "year": int(year) if isinstance(year, str) else year,
            "make": make,
            "model": model,
            "engine": engine,
        }
        
        # Note: Vehicle is already selected from the plate lookup (clicked "Use This Vehicle")
        # No need to navigate again - just execute the target tool
        
        # Step 2: Execute the target tool
        # Remove plate/state/target_tool from params, pass rest to target tool
        tool_params = {k: v for k, v in params.items() 
                       if k not in ("plate", "state", "target_tool")}
        
        # Pass skip_vehicle_selection=True since vehicle was already selected via plate lookup
        result = await self._execute_tool(target_tool, vehicle, tool_params, skip_vehicle_selection=True)
        
        # Add vehicle info to result so user knows what was looked up
        if result.get("success") and isinstance(result.get("data"), dict):
            result["data"]["_looked_up_vehicle"] = {
                "year": year,
                "make": make,
                "model": model,
                "engine": engine,
                "vin": vin,
                "from_plate": f"{plate} {state}"
            }
        elif result.get("success"):
            result["looked_up_vehicle"] = {
                "year": year,
                "make": make,
                "model": model,
                "engine": engine,
                "vin": vin,
                "from_plate": f"{plate} {state}"
            }
        
        return result
    
    async def _execute_tool(self, tool: str, vehicle: dict, params: dict, skip_vehicle_selection: bool = False) -> dict:
        """Execute a tool against ShopKeyPro.
        
        Args:
            tool: Tool name to execute
            vehicle: Vehicle dict with year, make, model, engine
            params: Tool-specific parameters
            skip_vehicle_selection: If True, skip vehicle selection (vehicle already selected)
        """
        year = vehicle["year"]
        make = vehicle["make"]
        model = vehicle["model"]
        engine = vehicle.get("engine")
        
        # NEW: Use autonomous navigator for query_autonomous tool
        if tool == "query_autonomous":
            from ..ai_navigator.autonomous_navigator import query_mitchell_autonomous
            
            logger.info(f"[AUTONOMOUS] Received params: {params}")
            goal = params.get("question", params.get("query", ""))
            context = params.get("context", "")  # Conversation context from prior messages
            if not goal:
                return {"success": False, "error": "No question/query provided"}
            
            logger.info(f"[AUTONOMOUS] Executing query: '{goal}'")
            logger.info(f"[AUTONOMOUS] Vehicle: {year} {make} {model} {engine}")
            if context:
                logger.info(f"[AUTONOMOUS] Context provided: {context[:200]}...")
            
            vehicle_dict = {
                "year": str(year),
                "make": make,
                "model": model,
                "engine": engine or "",
            }
            
            result = await query_mitchell_autonomous(
                page=self._api._page,
                goal=goal,
                vehicle=vehicle_dict,
                context=context,
                # Use default model (gemini-2.5-flash) from autonomous_navigator
            )
            
            logger.info(f"[AUTONOMOUS] Result: success={result.get('success')}, steps={result.get('steps')}")
            
            return result
        
        # Map tool names to API methods
        tool_map = {
            "get_fluid_capacities": lambda: self._api.get_fluid_capacities(
                year, make, model, engine,
                fluid_type=params.get("fluid_type"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_dtc_info": lambda: self._api.get_dtc_info(
                year, make, model,
                dtc_code=params.get("dtc_code", ""),
                engine=engine,
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_torque_specs": lambda: self._api.get_torque_specs(
                year, make, model, engine,
                component=params.get("component"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_reset_procedure": lambda: self._api.get_reset_procedure(
                year, make, model,
                procedure=params.get("procedure", ""),
                engine=engine,
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_tsb_list": lambda: self._api.get_tsb_list(
                year, make, model, engine,
                category=params.get("category"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_adas_calibration": lambda: self._api.get_adas_calibration(
                year, make, model, engine,
                component=params.get("component"),
                info_type=params.get("info_type"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_tire_specs": lambda: self._api.get_tire_specs(
                year, make, model, engine,
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_wiring_diagram": lambda: self._api.get_wiring_diagram(
                year, make, model, engine,
                system=params.get("system"),
                subsystem=params.get("subsystem"),
                diagram=params.get("diagram"),
                search=params.get("search"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_specs_procedures": lambda: self._api.get_specs_procedures(
                year, make, model, engine,
                category=params.get("category"),
                topic=params.get("topic"),
                search=params.get("search"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_component_location": lambda: self._api.get_component_location(
                year, make, model, engine,
                component=params.get("component"),
                location_type=params.get("location_type"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "get_component_tests": lambda: self._api.get_component_tests(
                year, make, model, engine,
                component=params.get("component"),
                system=params.get("system"),
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "lookup_vehicle": lambda: self._api.lookup_vehicle(
                vin=params.get("vin"),
                plate=params.get("plate"),
                state=params.get("state"),
                raw_input=params.get("raw_input")
            ),
            "query_by_plate": lambda: self._execute_query_by_plate(params),
            "search_mitchell": lambda: self._api.search(
                year, make, model,
                query=params.get("query", ""),
                engine=engine,
                skip_vehicle_selection=skip_vehicle_selection
            ),
            "query_mitchell": lambda: self._api.query(
                year, make, model,
                query=params.get("question", ""),
                engine=engine,
                skip_vehicle_selection=skip_vehicle_selection
            ),
        }
        
        if tool not in tool_map:
            return {"success": False, "error": f"Unknown tool: {tool}"}
        
        return await tool_map[tool]()


async def main():
    """Entry point for the agent."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Mitchell Polling Agent")
    parser.add_argument("--shop-id", help="Shop identifier")
    parser.add_argument("--server-url", help="Server URL to poll")
    parser.add_argument("--poll-interval", type=int, help="Poll interval in seconds")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    parser.add_argument("--config", help="Path to config file")
    args = parser.parse_args()
    
    # Load config from file first, then override with CLI args
    config_path = args.config if args.config else None
    config = load_config(config_path)
    
    # CLI args override config file
    if args.shop_id:
        config.shop_id = args.shop_id
    if args.server_url:
        config.server_url = args.server_url
    if args.poll_interval:
        config.poll_interval = args.poll_interval
    if args.headless:
        config.headless = True
    
    # Create and start agent
    agent = MitchellAgent(config)
    
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())
