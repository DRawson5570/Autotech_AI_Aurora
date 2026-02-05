"""
Request Handler
===============
Processes individual Mitchell requests.
"""

import asyncio
import logging
import re
import time
from typing import Optional

log = logging.getLogger(__name__)


class RequestHandler:
    """
    Handles execution of individual Mitchell requests.
    
    Coordinates:
    - Vehicle navigation
    - Tool execution
    - Clarification flow
    - Error handling
    
    Usage:
        handler = RequestHandler(api, navigator, session)
        result = await handler.process(request)
    """
    
    def __init__(self, api, navigator_factory, session):
        """
        Initialize request handler.
        
        Args:
            api: MitchellAPI instance
            navigator_factory: Callable that creates Navigator
            session: SessionManager instance
        """
        self._api = api
        self._navigator_factory = navigator_factory
        self._session = session
    
    async def process(self, request: dict) -> dict:
        """
        Process a single request.
        
        Args:
            request: Request dict with id, tool, vehicle, params
            
        Returns:
            Result dict with success, data/error, timing
        """
        request_id = request["id"]
        tool = request["tool"]
        vehicle = request["vehicle"]
        params = request.get("params", {})
        
        log.info(f"Processing request {request_id}: {tool}")
        log.info(f"  Vehicle: {vehicle['year']} {vehicle['make']} {vehicle['model']}")
        
        start_time = time.time()
        needs_clarification = False
        should_logout = False
        
        try:
            # Ensure logged in
            if not await self._session.ensure_logged_in():
                return self._error_result("Failed to connect to ShopKeyPro", tool, start_time)
            
            self._session.update_activity()
            
            # Create navigator for this request
            navigator = self._navigator_factory(self._api._page)
            navigator.request_id = request_id
            
            # Skip vehicle navigation for lookup tools
            if tool in ("lookup_vehicle", "query_by_plate"):
                log.info(f"Skipping vehicle navigation for {tool}")
                nav_result = {"success": True}
            else:
                nav_result = await self._navigate_to_vehicle(navigator, vehicle)
            
            self._session.update_activity()
            
            # Handle navigation failure
            if not nav_result.get("success"):
                if nav_result.get("missing_info"):
                    needs_clarification = True
                    return self._clarification_result(nav_result, tool, start_time)
                else:
                    should_logout = True
                    return self._error_result(
                        nav_result.get("error", "Vehicle navigation failed"),
                        tool,
                        start_time
                    )
            
            # Execute the tool
            log.info(f"Executing tool: {tool}")
            result = await self._execute_tool(tool, vehicle, params)
            self._session.update_activity()
            
            execution_time = int((time.time() - start_time) * 1000)
            
            # Build response
            response = {
                "success": result.get("success", False),
                "data": result.get("data"),
                "error": result.get("error"),
                "tool_used": tool,
                "execution_time_ms": execution_time,
                "images": result.get("images"),
                "auto_selected": nav_result.get("auto_selected"),
            }
            
            # Don't logout after each request - keep session alive for next request
            # Session timeout will handle cleanup if no activity
            # should_logout = True  # REMOVED - let session timeout handle this
            log.info(f"Request {request_id} completed in {execution_time}ms")
            return response
            
        except Exception as e:
            log.exception(f"Error processing request {request_id}: {e}")
            should_logout = True
            return self._error_result(str(e), tool, start_time)
            
        finally:
            if should_logout:
                log.info("Logging out...")
                await self._session.logout()
            elif needs_clarification:
                log.info("Session kept open for clarification")
    
    def _error_result(self, error: str, tool: str, start_time: float) -> dict:
        """Build error result dict."""
        return {
            "success": False,
            "error": error,
            "tool_used": tool,
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }
    
    def _clarification_result(self, nav_result: dict, tool: str, start_time: float) -> dict:
        """Build clarification result dict."""
        missing_info = nav_result.get("missing_info", [])
        if not missing_info:
            # Shouldn't happen, but safety check
            return self._error_result("Missing info expected but not found", tool, start_time)
        missing = missing_info[0]
        return {
            "success": False,
            "error": nav_result.get("error"),
            "data": {
                "clarification_needed": True,
                "missing_field": missing["option"].lower().replace(" ", "_"),
                "options": missing["values"],
                "message": missing["message"],
            },
            "tool_used": tool,
            "execution_time_ms": int((time.time() - start_time) * 1000),
        }
    
    async def _navigate_to_vehicle(self, navigator, vehicle: dict) -> dict:
        """Navigate to a vehicle using Navigator."""
        
        # Extract drive_type if not provided
        drive_type = vehicle.get("drive_type")
        
        if not drive_type:
            all_text = " ".join([
                str(vehicle.get("submodel", "")),
                str(vehicle.get("body_style", "")),
                str(vehicle.get("engine", ""))
            ])
            drive_match = re.search(r'\b(4WD|AWD|RWD|FWD|2WD|4x4|4X4)\b', all_text, re.IGNORECASE)
            if drive_match:
                drive_type = drive_match.group(1).upper()
                log.info(f"Extracted drive_type: {drive_type}")
        
        # Build navigation goal
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
        log.info(f"Navigating to: {goal}")
        
        # Clarification handler
        missing_info = []
        
        async def handle_clarification(option_name: str, values: list, message: str) -> Optional[str]:
            log.info(f"Missing info: {option_name} - options: {values}")
            missing_info.append({
                "option": option_name,
                "values": values,
                "message": message,
            })
            return None  # Abort navigation
        
        navigator.on_clarification_needed = handle_clarification
        
        # Navigate
        result = await navigator.navigate(goal)
        
        # Handle missing info
        if missing_info:
            await self._close_vehicle_selector(navigator)
            
            info = missing_info[0]
            options_str = ", ".join(info["values"][:6])
            if len(info["values"]) > 6:
                options_str += f", ... ({len(info['values'])} total)"
            
            return {
                "success": False,
                "error": f"Additional info needed: {info['option']}. Options: {options_str}",
                "missing_info": missing_info,
            }
        
        return {
            "success": result.success,
            "error": result.error,
            "auto_selected": result.auto_selected,
        }
    
    async def _close_vehicle_selector(self, navigator):
        """Close vehicle selector dialog."""
        try:
            cancel_btn = navigator.page.locator("input[data-action='Cancel']")
            if await cancel_btn.count() > 0:
                await cancel_btn.click(timeout=3000)
                await asyncio.sleep(0.5)
        except Exception:
            pass
    
    async def _execute_tool(self, tool: str, vehicle: dict, params: dict) -> dict:
        """Execute a tool against ShopKeyPro."""
        year = vehicle["year"]
        make = vehicle["make"]
        model = vehicle["model"]
        engine = vehicle.get("engine")
        
        # Handle query_by_plate specially
        if tool == "query_by_plate":
            return await self._execute_query_by_plate(params)
        
        # Map tools to API methods
        tool_map = {
            "get_fluid_capacities": lambda: self._api.get_fluid_capacities(
                year, make, model, engine,
                fluid_type=params.get("fluid_type"),
            ),
            "get_dtc_info": lambda: self._api.get_dtc_info(
                year, make, model,
                dtc_code=params.get("dtc_code", ""),
                engine=engine,
            ),
            "get_torque_specs": lambda: self._api.get_torque_specs(
                year, make, model, engine,
                component=params.get("component"),
            ),
            "get_reset_procedure": lambda: self._api.get_reset_procedure(
                year, make, model,
                procedure=params.get("procedure", ""),
                engine=engine,
            ),
            "get_tsb_list": lambda: self._api.get_tsb_list(
                year, make, model, engine,
                category=params.get("category"),
            ),
            "get_adas_calibration": lambda: self._api.get_adas_calibration(
                year, make, model, engine,
                component=params.get("component"),
                info_type=params.get("info_type"),
            ),
            "get_tire_specs": lambda: self._api.get_tire_specs(
                year, make, model, engine,
            ),
            "get_wiring_diagram": lambda: self._api.get_wiring_diagram(
                year, make, model, engine,
                system=params.get("system"),
                subsystem=params.get("subsystem"),
                diagram=params.get("diagram"),
                search=params.get("search"),
            ),
            "get_specs_procedures": lambda: self._api.get_specs_procedures(
                year, make, model, engine,
                category=params.get("category"),
                topic=params.get("topic"),
                search=params.get("search"),
            ),
            "get_component_location": lambda: self._api.get_component_location(
                year, make, model, engine,
                component=params.get("component"),
                location_type=params.get("location_type"),
            ),
            "get_component_tests": lambda: self._api.get_component_tests(
                year, make, model, engine,
                component=params.get("component"),
                system=params.get("system"),
            ),
            "lookup_vehicle": lambda: self._api.lookup_vehicle(
                vin=params.get("vin"),
                plate=params.get("plate"),
                state=params.get("state"),
                raw_input=params.get("raw_input"),
            ),
            "search_mitchell": lambda: self._api.search(
                year, make, model,
                query=params.get("query", ""),
                engine=engine,
            ),
            "query_mitchell": lambda: self._api.query(
                year, make, model,
                query=params.get("question", ""),
                engine=engine,
            ),
        }
        
        if tool not in tool_map:
            return {"success": False, "error": f"Unknown tool: {tool}"}
        
        return await tool_map[tool]()
    
    async def _execute_query_by_plate(self, params: dict) -> dict:
        """Execute plate lookup followed by target tool."""
        plate = params.get("plate")
        state = params.get("state")
        target_tool = params.get("target_tool")
        
        # Sanitize plate
        if plate:
            plate = plate.replace(" ", "").replace("-", "").upper()
        
        if not plate or not state:
            return {"success": False, "error": "plate and state are required"}
        if not target_tool:
            return {"success": False, "error": "target_tool is required"}
        
        log.info(f"Query by plate: {plate} {state} -> {target_tool}")
        
        # Lookup vehicle
        lookup_result = await self._api.lookup_vehicle(plate=plate, state=state)
        
        if not lookup_result.get("success"):
            return {
                "success": False,
                "error": f"Plate lookup failed: {lookup_result.get('error')}",
            }
        
        # Extract vehicle info
        data = lookup_result.get("data", {})
        year = data.get("year")
        make = data.get("make")
        model = data.get("model")
        engine = data.get("engine")
        vin = data.get("vin")
        
        if not year or not make or not model:
            return {
                "success": False,
                "error": f"Incomplete vehicle info: {data}",
            }
        
        log.info(f"Decoded: {year} {make} {model} {engine} (VIN: {vin})")
        
        # Execute target tool
        vehicle = {
            "year": int(year) if isinstance(year, str) else year,
            "make": make,
            "model": model,
            "engine": engine,
        }
        
        tool_params = {k: v for k, v in params.items() 
                      if k not in ("plate", "state", "target_tool")}
        
        result = await self._execute_tool(target_tool, vehicle, tool_params)
        
        # Add looked up vehicle info
        if result.get("success"):
            result["looked_up_vehicle"] = {
                "year": year,
                "make": make,
                "model": model,
                "engine": engine,
                "vin": vin,
                "from_plate": f"{plate} {state}",
            }
        
        return result
