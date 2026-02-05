"""
title: Mitchell Automotive Data
author: autotech-ai
author_url: https://github.com/autotech-ai
version: 2.1.0
description: Retrieve automotive technical data from ShopKeyPro via remote polling agent.
required_open_webui_version: 0.4.0

=== DEVELOPMENT VERSION ===
For: localhost:8080 (local dev)
Paste this entire file into Open WebUI > Workspace > Tools > Mitchell Automotive Data
"""

import httpx
from typing import Optional, Any
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo

# Debug logging to file (DISABLED - set to True to enable)
_DEBUG_ENABLED = False

def _debug_log(msg: str):
    """Write debug message to file for tracing."""
    if not _DEBUG_ENABLED:
        return
    import datetime
    with open("/tmp/mitchell_tool_debug.log", "a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {msg}\n")


def _sanitize_value(value: Any) -> Any:
    """Convert FieldInfo objects to None (handles direct Python calls with Field() defaults)."""
    if isinstance(value, FieldInfo):
        return None
    if value == "":
        return None
    return value


class Tools:
    """
    Mitchell Automotive Data Tools
    
    Connects to remote Mitchell polling agents running at customer sites.
    Requests are queued and results returned when the agent completes them.
    
    Token Usage:
    - If the agent uses server-side navigation (no local GPU), tokens are billed
      to the user's account via the user_id passed in requests.
    """
    
    class Valves(BaseModel):
        """Admin-configurable settings for Mitchell integration."""
        SHOP_ID: str = Field(
            default="",
            description="Shop identifier - must match the agent's shop_id"
        )
        API_BASE_URL: str = Field(
            default="https://automotive.aurora-sentient.net",
            description="Base URL for Mitchell API endpoints"
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="How long to wait for agent response (seconds)"
        )
    
    def __init__(self):
        self.valves = self.Valves()
        self.citation = True
    
    async def _make_request(
        self,
        tool: str,
        year: int,
        make: str,
        model: str,
        engine: Optional[str] = None,
        submodel: Optional[str] = None,
        body_style: Optional[str] = None,
        drive_type: Optional[str] = None,
        __user__: dict = None,
        **params
    ) -> str:
        """Queue a request and wait for result from remote agent."""
        
        if not self.valves.SHOP_ID:
            return "Error: Shop ID not configured. Please set SHOP_ID in tool settings."
        
        # Sanitize optional fields (handles FieldInfo objects from direct calls)
        engine = _sanitize_value(engine)
        submodel = _sanitize_value(submodel)
        body_style = _sanitize_value(body_style)
        drive_type = _sanitize_value(drive_type)
        
        # DEBUG: Log what we're about to send
        print(f"[Tool DEBUG] drive_type after sanitize: '{drive_type}'")
        
        # Get user_id for billing (if user context is available)
        user_id = __user__.get("id") if __user__ else None
        
        # Sanitize params as well
        sanitized_params = {k: _sanitize_value(v) for k, v in params.items()}
        sanitized_params = {k: v for k, v in sanitized_params.items() if v is not None}
        
        # Build request payload
        payload = {
            "shop_id": self.valves.SHOP_ID,
            "user_id": user_id,  # For billing if server-side navigation is used
            "tool": tool,
            "vehicle": {
                "year": year,
                "make": make,
                "model": model,
                "engine": engine,
                "submodel": submodel,
                "body_style": body_style,
                "drive_type": drive_type
            },
            "params": sanitized_params,
            "timeout_seconds": self.valves.REQUEST_TIMEOUT
        }
        
        # DEBUG: Log the full payload
        print(f"[Tool DEBUG] Full payload vehicle: {payload['vehicle']}")
        
        base_url = self.valves.API_BASE_URL.rstrip("/")
        
        try:
            async with httpx.AsyncClient(timeout=self.valves.REQUEST_TIMEOUT + 30) as client:
                # Create request
                response = await client.post(
                    f"{base_url}/api/mitchell/request",
                    json=payload
                )
                response.raise_for_status()
                request_data = response.json()
                request_id = request_data["id"]
                
                # Poll for result, returning clarifications to user when needed
                result = await self._poll_for_result(client, base_url, request_id, tool)
                print(f"[DEBUG _make_request] Returning result length: {len(result)}")
                print(f"[DEBUG _make_request] Contains '![': {'![' in result}")
                print(f"[DEBUG _make_request] Contains '/static/mitchell/': {'/static/mitchell/' in result}")
                return result
                    
        except httpx.TimeoutException:
            return "Error: Request timed out waiting for Mitchell agent."
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

    async def _poll_for_result(
        self,
        client,  # httpx.AsyncClient - no type hint to avoid Pydantic schema issues
        base_url: str,
        request_id: str,
        tool: str
    ) -> str:
        """Poll for result until completed, failed, or timeout."""
        import asyncio
        import time
        
        print(f"[Mitchell Tool] Starting poll for request {request_id}")
        
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > self.valves.REQUEST_TIMEOUT:
                _debug_log(f"Timeout after {elapsed:.1f}s")
                return "Error: Request timed out waiting for agent."
            
            # Check request status
            try:
                status_response = await client.get(
                    f"{base_url}/api/mitchell/status/{request_id}"
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    
                    _debug_log(f"Status: {status}")
                    
                    if status == "completed":
                        result = status_data.get("result", {})
                        _debug_log(f"Result keys: {list(result.keys())}")
                        _debug_log(f"Has images key: {'images' in result}")
                        _debug_log(f"Images value type: {type(result.get('images'))}")
                        images_raw = result.get('images')
                        _debug_log(f"Images count: {len(images_raw) if images_raw else 0}")
                        if images_raw:
                            _debug_log(f"First image keys: {list(images_raw[0].keys()) if images_raw else 'N/A'}")
                        if result.get("success"):
                            # Check for images FIRST - put them at the top
                            images = result.get("images")
                            _debug_log(f"images variable: {images is not None}, len={len(images) if images else 0}")
                            image_section = ""
                            if images:
                                _debug_log(f"Calling _format_images with {len(images)} images")
                                image_section = self._format_images(images)
                                _debug_log(f"image_section length: {len(image_section)}")
                                _debug_log(f"image_section preview: {image_section[:500] if image_section else 'EMPTY'}")
                            
                            formatted = self._format_result(result.get("data", {}), f"{tool} Result")
                            _debug_log(f"formatted length before images: {len(formatted)}")
                            
                            # Prepend images to the result so they appear first
                            if image_section:
                                formatted = image_section + "\n\n" + formatted
                                _debug_log(f"formatted length after images: {len(formatted)}")
                            
                            # Note any auto-selected options
                            auto_selected = result.get("auto_selected")
                            if auto_selected:
                                formatted += self._format_auto_selected(auto_selected)
                            _debug_log(f"FINAL formatted length: {len(formatted)}")
                            _debug_log(f"FINAL formatted first 800 chars: {formatted[:800]}")
                            return formatted
                        else:
                            # Check if this is a clarification request
                            data = result.get("data", {})
                            if data and data.get("clarification_needed"):
                                return self._format_clarification(data)
                            # Return error message
                            return f"Error: {result.get('error', 'Unknown error')}"
                    elif status == "failed":
                        result = status_data.get("result", {})
                        return f"Error: {result.get('error', 'Request failed')}"
                    elif status == "expired":
                        return "Error: Request expired. The agent may be offline."
            except Exception as e:
                print(f"[Mitchell Tool] Error checking status: {e}")
            
            # Wait before next poll
            await asyncio.sleep(2.0)

    def _format_images(self, images: list) -> str:
        """Format images as markdown with file URLs.
        
        Images are saved to the static/mitchell directory and URLs are returned.
        This avoids huge base64 strings in the response which can break rendering.
        """
        if not images:
            _debug_log("_format_images: No images to format")
            return ""
        
        _debug_log(f"_format_images: Processing {len(images)} images")
        
        import os
        import base64
        from pathlib import Path
        import uuid
        
        # Try multiple possible static directory locations
        possible_dirs = [
            os.environ.get("STATIC_DIR"),
            "/app/backend/static",  # Docker
            "/prod/autotech_ai/backend/open_webui/static",  # Production (poweredge2)
            "/home/drawson/autotech_ai/backend/open_webui/static",  # Dev
            Path(__file__).parent.parent.parent / "backend" / "open_webui" / "static",
        ]
        
        static_dir = None
        for d in possible_dirs:
            if d and Path(d).exists():
                static_dir = Path(d)
                break
        
        if not static_dir:
            _debug_log(f"Could not find static directory, tried: {possible_dirs}")
            return "\n\n*(Images captured but could not be saved - static directory not found)*"
        
        mitchell_dir = static_dir / "mitchell"
        try:
            mitchell_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            _debug_log(f"Could not create mitchell dir: {e}")
            return f"\n\n*(Images captured but could not be saved: {e})*"
        
        _debug_log(f"_format_images called with {len(images)} images")
        _debug_log(f"Saving images to: {mitchell_dir}")
        
        lines = ["**DIAGRAM IMAGES:**\n"]
        for idx, img in enumerate(images):
            _debug_log(f"Processing image {idx}: name={img.get('name')}, has_base64={bool(img.get('base64'))}")
            name = img.get("name", f"Image {idx + 1}")
            base64_data = img.get("base64", "")
            mime_type = img.get("mime_type", "image/png")
            
            if base64_data:
                # Determine file extension
                ext = "png" if "png" in mime_type else "jpg"
                
                # Generate unique filename
                filename = f"diagram_{uuid.uuid4().hex[:8]}.{ext}"
                filepath = mitchell_dir / filename
                
                # Decode and save image
                try:
                    img_bytes = base64.b64decode(base64_data)
                    filepath.write_bytes(img_bytes)
                    _debug_log(f"Saved image: {filepath} ({len(img_bytes)} bytes)")
                    
                    # Return URL to the static file - use markdown format
                    url = f"/static/mitchell/{filename}"
                    lines.append(f"![{name}]({url})")
                    lines.append("")
                    _debug_log(f"Added markdown: ![{name}]({url})")
                except Exception as e:
                    _debug_log(f"Error saving image {name}: {e}")
                    lines.append(f"- {name}: (Error saving image: {e})")
        
        result = "\n".join(lines)
        _debug_log(f"_format_images returning: {result}")
        return result

    def _format_auto_selected(self, auto_selected: dict) -> str:
        """Format auto-selected options note for the user."""
        if not auto_selected:
            return ""
        
        items = []
        for key, value in auto_selected.items():
            field_name = key.replace("_", " ").title()
            items.append(f"{field_name}: **{value}**")
        
        options_str = ", ".join(items)
        return (
            f"\n\n---\n"
            f"*Note: The following options were auto-selected (first available): {options_str}. "
            f"If this is incorrect, please specify the correct option in your next query.*"
        )

    def _format_clarification(self, data: dict) -> str:
        """Format a clarification request so the LLM knows to retry with the right param."""
        field = data.get("missing_field", "unknown")
        options = data.get("options", [])
        
        # Show up to 8 options
        options_display = options[:8]
        if len(options) > 8:
            options_display.append(f"... and {len(options) - 8} more")
        
        options_str = ", ".join(str(o) for o in options_display)
        
        # Map field names to parameter names
        field_to_param = {
            "submodel": "submodel",
            "body_style": "body_style",
            "drive_type": "drive_type",
        }
        param_name = field_to_param.get(field, field)
        
        return (
            f"**Additional information needed**\\n\\n"
            f"To provide accurate specs, I need the **{field.replace('_', ' ').title()}**.\\n\\n"
            f"Available options: {options_str}\\n\\n"
            f"Can you confirm the {field.replace('_', ' ')}? "
            f"(e.g., 2018 Ford F-150 **XLT** 5.0L engine)\\n\\n"
            f"*Once confirmed, I'll call the tool again with `{param_name}` set to your choice.*"
        )

    def _format_result(self, data: dict, title: str) -> str:
        """Format result data into readable string."""
        if not data:
            return f"No {title.lower()} found."
        
        lines = []
        
        # Check for looked up vehicle info - display FIRST and PROMINENTLY
        if isinstance(data, dict) and "_looked_up_vehicle" in data:
            veh = data["_looked_up_vehicle"]
            year = veh.get("year", "")
            make = veh.get("make", "")
            model = veh.get("model", "")
            engine = veh.get("engine", "")
            plate = veh.get("from_plate", "")
            lines.append(f"**VEHICLE IDENTIFIED: {year} {make} {model} {engine}**")
            if plate:
                lines.append(f"*(From plate: {plate})*\n")
            else:
                lines.append("")
        
        if isinstance(data, list):
            lines.append(f"**{title}:**\n")
            for item in data:
                if isinstance(item, dict):
                    for k, v in item.items():
                        if v:
                            lines.append(f"- {k}: {v}")
                    lines.append("")
                else:
                    lines.append(f"- {item}")
            return "\n".join(lines)
        
        elif isinstance(data, dict):
            lines.append(f"**{title}:**\n")
            for k, v in data.items():
                # Skip the looked up vehicle info (already displayed above)
                if k == "_looked_up_vehicle":
                    continue
                if isinstance(v, list):
                    lines.append(f"\n**{k}:**")
                    for item in v:
                        if isinstance(item, dict):
                            for ik, iv in item.items():
                                if iv:
                                    lines.append(f"  - {ik}: {iv}")
                        else:
                            lines.append(f"  - {item}")
                elif v:
                    lines.append(f"- {k}: {v}")
            return "\n".join(lines)
        
        return str(data)
    
    # ==================== Tool Functions ====================
    
    async def get_fluid_capacities(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        engine: str = Field(default="", description="Engine specification (e.g., 5.0L) - optional"),
        submodel: str = Field(default="", description="Submodel/trim (e.g., XLT, Lariat) - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style (e.g., 2D Pickup, 4D Sedan) - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (e.g., 2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        fluid_type: str = Field(default="", description="Filter by fluid type: oil, coolant, transmission, differential, brake - optional"),
        __user__: dict = {}
    ) -> str:
        """
        Get fluid capacities for a vehicle including oil, coolant, transmission fluid, differential fluid, and brake fluid specifications.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed and report what was selected.
        """
        return await self._make_request(
            "get_fluid_capacities",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            fluid_type=fluid_type
        )
    
    async def get_dtc_info(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        dtc_code: str = Field(..., description="Diagnostic trouble code (e.g., P0300)"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Get diagnostic trouble code (DTC) information including description, causes, and recommended actions.
        
        DTC prefixes: P=Powertrain, B=Body, C=Chassis, U=Network
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_dtc_info",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            dtc_code=dtc_code
        )
    
    async def get_torque_specs(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        component: str = Field(default="", description="Filter by component: wheel, caliper, suspension, engine - optional"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Get torque specifications for vehicle components including wheel lug nuts, brake calipers, and suspension bolts.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_torque_specs",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            component=component
        )
    
    async def get_reset_procedure(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        procedure: str = Field(..., description="Type of reset: oil, tpms, maintenance, battery"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Get reset procedures for oil life monitor, TPMS sensor relearn, and maintenance lights.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_reset_procedure",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            procedure=procedure
        )
    
    async def get_tsb_list(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        category: str = Field(default="", description="Filter by category: engine, transmission, electrical, body - optional"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Get Technical Service Bulletins (TSBs) documenting known issues and manufacturer fixes.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_tsb_list",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            category=category
        )
    
    async def get_adas_calibration(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        component: str = Field(default="", description="ADAS component to look up: camera, radar, blind spot, anti-lock brake, etc."),
        info_type: str = Field(default="", description="Type of info to get: specs, remove, wiring, location, connector, tsb - optional"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Get ADAS calibration requirements and detailed component info.
        
        Use cases:
        - No component: Returns all ADAS components with calibration requirements
        - With component: Filters to specific component (e.g., "blind spot sensor")
        - With component + info_type: Drills down to get specific info (e.g., specs, removal procedure, wiring)
        
        info_type options:
        - specs: Torque specs, specifications
        - remove: Remove & Replace procedures
        - wiring: Wiring diagrams
        - location: Component location diagrams
        - connector: Connector pinouts
        - tsb: Technical Service Bulletins
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_adas_calibration",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            component=component or None,
            info_type=info_type or None
        )
    
    async def get_tire_specs(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Get tire specifications including sizes, pressures, and TPMS sensor part numbers.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_tire_specs",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__
        )
    
    async def get_wiring_diagram(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        system: str = Field(default="", description="Electrical system (e.g., 'Engine', 'Body', 'Chassis') - optional, lists all if empty"),
        subsystem: str = Field(default="", description="Subsystem (e.g., 'Starting/Charging') - optional"),
        diagram: str = Field(default="", description="Specific diagram name (e.g., 'Starter Circuit') - optional, returns image"),
        search: str = Field(default="", description="Search term to find specific diagrams (e.g., 'alternator', 'headlight')"),
        __user__: dict = {}
    ) -> str:
        """
        Get wiring diagrams for vehicle electrical systems.
        
        Use cases:
        - No system/diagram: Lists available electrical systems
        - With system: Shows subsystems and diagrams in that system
        - With diagram: Returns the actual wiring diagram image
        - With search: Finds diagrams matching the search term
        
        Common systems: Engine, Body, Chassis, Lighting, HVAC, Audio
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_wiring_diagram",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            system=system or None,
            subsystem=subsystem or None,
            diagram=diagram or None,
            search=search or None
        )
    
    async def get_specs_procedures(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        category: str = Field(default="", description="Category to browse (e.g., 'Torque', 'Drive Belts') - optional"),
        topic: str = Field(default="", description="Specific topic within category - optional"),
        search: str = Field(default="", description="Search term to find specs/procedures (e.g., 'drive belt', 'torque specs', 'timing chain')"),
        __user__: dict = {}
    ) -> str:
        """
        Get common specifications and service procedures from ShopKeyPro.
        
        Use cases:
        - Torque specifications ("torque specs for intake manifold")
        - Service procedures ("how to replace drive belt", "timing chain procedure")
        - Fluid specifications ("coolant specs", "oil capacity")
        - System specifications ("spark plug gap", "valve clearance")
        
        Use 'search' parameter for semantic matching to find relevant categories.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_specs_procedures",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            category=category or None,
            topic=topic or None,
            search=search or None
        )
    
    async def get_component_location(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        component: str = Field(default="", description="Component to find (e.g., 'radio', 'ECM', 'fuel pump')"),
        location_type: str = Field(default="", description="Type filter: 'fuse', 'relay', 'ground', 'connector', 'module'"),
        __user__: dict = {}
    ) -> str:
        """
        Find electrical component locations, fuse boxes, grounds, and connectors.
        
        Use cases:
        - Find fuse location: "F15 fuse", "radio fuse"
        - Find ground points: "G100", "engine ground"
        - Find component location: "ECM", "radio", "fuel pump"
        - Find relay location: "starter relay", "fuel pump relay"
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_component_location",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            component=component or None,
            location_type=location_type or None
        )
    
    async def get_component_tests(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        component: str = Field(default="", description="Component to test (e.g., 'ABS Module', 'Wheel Speed Sensors')"),
        system: str = Field(default="", description="System category (e.g., 'ABS', 'Body Electrical', 'HVAC System')"),
        __user__: dict = {}
    ) -> str:
        """
        Get component test information, pinouts, and operation descriptions.
        
        Use cases:
        - Get ABS module pinouts: component="ABS Module"
        - Get wheel speed sensor tests: component="Wheel Speed Sensors"
        - Browse system components: system="ABS" (lists all ABS components)
        - HVAC component tests: system="HVAC System"
        
        Available systems: ABS, Body Electrical, Charging System, Engine, HVAC System, Starting System, Transmission
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "get_component_tests",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            component=component or None,
            system=system or None
        )
    
    async def lookup_vehicle(
        self,
        raw_input: str = Field(default="", description="Raw OCR text from plate/VIN photo (e.g., '4mzh83 mi' or '1G1PC5SB8E7123456')"),
        vin: str = Field(default="", description="17-character VIN - use if you have the VIN directly"),
        plate: str = Field(default="", description="License plate number - use if you have plate + state"),
        state: str = Field(default="", description="2-letter state code (e.g., 'MI', 'OH') - required if using plate"),
        __user__: dict = {}
    ) -> str:
        """
        Look up vehicle by VIN or license plate to decode year, make, model, engine.
        
        Use cases:
        - User sends plate photo: raw_input="4mzh83 mi" → decodes to vehicle info
        - User has VIN: vin="1G1PC5SB8E7123456" → decodes to vehicle info
        - User has plate+state: plate="ABC1234", state="MI" → decodes to vehicle info
        
        This tool returns vehicle info (year, make, model, engine) that can be used for subsequent queries.
        
        Examples:
        - "What's the oil capacity for this car? [plate photo showing 4MZH83 MI]"
          → First lookup_vehicle(raw_input="4mzh83 mi"), then use returned info for get_fluid_capacities
        - "Decode this VIN: 1G1PC5SB8E7123456"
          → lookup_vehicle(vin="1G1PC5SB8E7123456")
        """
        if not self.valves.SHOP_ID:
            return "Error: Shop ID not configured. Please set SHOP_ID in tool settings."
        
        # Sanitize inputs
        raw_input = _sanitize_value(raw_input) or ""
        vin = _sanitize_value(vin) or ""
        plate = _sanitize_value(plate) or ""
        state = _sanitize_value(state) or ""
        
        # Remove spaces and dashes from plate number (e.g., "AUE 709" -> "AUE709")
        if plate:
            plate = plate.replace(" ", "").replace("-", "").upper()
        
        # Get user_id for billing
        user_id = __user__.get("id") if __user__ else None
        
        # Build request payload - no vehicle info required for lookup
        payload = {
            "shop_id": self.valves.SHOP_ID,
            "user_id": user_id,
            "tool": "lookup_vehicle",
            "vehicle": {
                "year": 0,  # Dummy - will be looked up
                "make": "Unknown",
                "model": "Unknown",
            },
            "params": {
                "raw_input": raw_input if raw_input else None,
                "vin": vin if vin else None,
                "plate": plate if plate else None,
                "state": state if state else None,
            },
            "timeout_seconds": self.valves.REQUEST_TIMEOUT
        }
        
        # Remove None params
        payload["params"] = {k: v for k, v in payload["params"].items() if v is not None}
        
        base_url = self.valves.API_BASE_URL.rstrip("/")
        
        try:
            async with httpx.AsyncClient(timeout=self.valves.REQUEST_TIMEOUT + 30) as client:
                # Create request
                response = await client.post(
                    f"{base_url}/api/mitchell/request",
                    json=payload
                )
                response.raise_for_status()
                request_data = response.json()
                request_id = request_data["id"]
                
                # Poll for result
                return await self._poll_for_result(client, base_url, request_id, "lookup_vehicle")
                    
        except httpx.TimeoutException:
            return "Error: Request timed out waiting for Mitchell agent."
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def query_by_plate(
        self,
        plate: str = Field(..., description="License plate number (e.g., 'AUE709')"),
        state: str = Field(..., description="2-letter state code (e.g., 'MI', 'OH', 'CA') - 'michigan' = 'MI', 'ohio' = 'OH', etc."),
        request_type: str = Field(..., description="Type of info needed: 'fluids', 'torque', 'dtc', 'reset', 'adas', 'tire', 'tsb', 'wiring', or 'search'"),
        dtc_code: str = Field(default="", description="DTC code (e.g., 'P0300') - required if request_type='dtc'"),
        search_query: str = Field(default="", description="Search query - required if request_type='search'"),
        system: str = Field(default="", description="System for wiring diagrams - optional if request_type='wiring'"),
        reset_type: str = Field(default="", description="Reset type (e.g., 'oil_life', 'tpms') - optional if request_type='reset'"),
        __user__: dict = {}
    ) -> str:
        """
        **USE THIS TOOL when user mentions a license plate number** - looks up the vehicle and gets the requested info in one call.
        
        WHEN TO USE: User says "plate", "license plate", "plate number", or provides something like "AUE709 MI", "ABC-1234 ohio", etc.
        DO NOT ask user for year/make/model if they gave a plate - use this tool instead!
        
        This tool:
        1. Decodes the plate to get year/make/model/engine automatically
        2. Runs the appropriate info tool (fluids, torque, dtc, etc.)
        3. Returns the complete result
        
        Examples:
        - "Give me info on fluids - plate aue709 - state michigan" 
          → query_by_plate(plate="AUE709", state="MI", request_type="fluids")
        - "What's the oil capacity for plate AUE709 MI?" 
          → query_by_plate(plate="AUE709", state="MI", request_type="fluids")
        - "Get P0300 info for plate ABC1234 OH"
          → query_by_plate(plate="ABC1234", state="OH", request_type="dtc", dtc_code="P0300")
        - "TPMS reset procedure for plate XYZ789 CA"
          → query_by_plate(plate="XYZ789", state="CA", request_type="reset", reset_type="tpms")
        - "torque specs for plate 123ABC california"
          → query_by_plate(plate="123ABC", state="CA", request_type="torque")
        """
        if not self.valves.SHOP_ID:
            return "Error: Shop ID not configured. Please set SHOP_ID in tool settings."
        
        # Sanitize inputs
        plate = _sanitize_value(plate) or ""
        state = _sanitize_value(state) or ""
        request_type = (_sanitize_value(request_type) or "").lower()
        dtc_code = _sanitize_value(dtc_code) or ""
        search_query = _sanitize_value(search_query) or ""
        system = _sanitize_value(system) or ""
        reset_type = _sanitize_value(reset_type) or ""
        
        # Remove spaces and dashes from plate (e.g., "AUE 709" -> "AUE709")
        plate = plate.replace(" ", "").replace("-", "").upper()
        
        if not plate or not state:
            return "Error: Both plate and state are required."
        
        # Map request_type to tool name and required params
        tool_map = {
            "fluids": ("get_fluid_capacities", {}),
            "fluid": ("get_fluid_capacities", {}),
            "oil": ("get_fluid_capacities", {"fluid_type": "oil"}),
            "coolant": ("get_fluid_capacities", {"fluid_type": "coolant"}),
            "torque": ("get_torque_specs", {}),
            "dtc": ("get_dtc_info", {"dtc_code": dtc_code}),
            "reset": ("get_reset_procedure", {"reset_type": reset_type}),
            "adas": ("get_adas_calibration", {}),
            "tire": ("get_tire_specs", {}),
            "tpms": ("get_tire_specs", {}),
            "tsb": ("get_tsb_list", {}),
            "wiring": ("get_wiring_diagrams", {"system": system}),
            "search": ("search_mitchell", {"query": search_query}),
        }
        
        if request_type not in tool_map:
            valid_types = ", ".join(sorted(tool_map.keys()))
            return f"Error: Unknown request_type '{request_type}'. Valid types: {valid_types}"
        
        target_tool, extra_params = tool_map[request_type]
        
        # Validate required params for certain tools
        if request_type == "dtc" and not dtc_code:
            return "Error: dtc_code is required when request_type='dtc'"
        if request_type == "search" and not search_query:
            return "Error: search_query is required when request_type='search'"
        
        # Get user_id for billing
        user_id = __user__.get("id") if __user__ else None
        
        # Sanitize plate - remove spaces and dashes (e.g., "AUE 709" -> "AUE709")
        plate = plate.replace(" ", "").replace("-", "").upper()
        
        # Build combined request - agent will do lookup then execute tool
        payload = {
            "shop_id": self.valves.SHOP_ID,
            "user_id": user_id,
            "tool": "query_by_plate",
            "vehicle": {
                "year": 0,  # Will be looked up
                "make": "Unknown",
                "model": "Unknown",
            },
            "params": {
                "plate": plate,
                "state": state.upper(),
                "target_tool": target_tool,
                **{k: v for k, v in extra_params.items() if v}
            },
            "timeout_seconds": self.valves.REQUEST_TIMEOUT
        }
        
        base_url = self.valves.API_BASE_URL.rstrip("/")
        
        try:
            async with httpx.AsyncClient(timeout=self.valves.REQUEST_TIMEOUT + 60) as client:
                # Create request
                response = await client.post(
                    f"{base_url}/api/mitchell/request",
                    json=payload
                )
                response.raise_for_status()
                request_data = response.json()
                request_id = request_data["id"]
                
                # Poll for result
                return await self._poll_for_result(client, base_url, request_id, target_tool)
                    
        except httpx.TimeoutException:
            return "Error: Request timed out waiting for Mitchell agent."
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def search_mitchell(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        query: str = Field(..., description="Search query (e.g., 'timing belt replacement')"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Search all ShopKeyPro content. Use for questions not covered by specific tools.
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "search_mitchell",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            query=query
        )
    
    async def query_mitchell(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        question: str = Field(..., description="Your automotive question"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional, agent will auto-select if needed"),
        body_style: str = Field(default="", description="Body style - optional, agent will auto-select if needed"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional, agent will auto-select if needed"),
        __user__: dict = {}
    ) -> str:
        """
        Ask any automotive question. Automatically selects the best data source.
        
        Examples: "What is the oil capacity?", "How do I reset the oil life?", "What does P0300 mean?"
        
        IMPORTANT: Call this tool even if submodel/body_style/drive_type are unknown. The agent will auto-select defaults if needed.
        """
        return await self._make_request(
            "query_mitchell",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            question=question
        )

    async def save_result(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        query: str = Field(..., description="The original question or query"),
        content: str = Field(..., description="The result content to save"),
        source: str = Field(default="", description="Data source (e.g., 'mitchell', 'alldata') - optional"),
        tool: str = Field(default="", description="Which tool produced this result - optional"),
        engine: str = Field(default="", description="Engine specification - optional"),
        __user__: dict = {},
        __request__: any = None,
    ) -> str:
        """
        Save automotive data to your personal Knowledge base for future reference.
        
        Use this when the user explicitly asks to save or remember automotive information.
        The saved data will be available for RAG retrieval in future conversations.
        
        IMPORTANT: If the user says "Save that" but you don't have the vehicle year, make, 
        and model from context, ask them: "To save this, I need the vehicle information. 
        What's the year, make, and model?"
        
        Example: After getting fluid capacities, user says "Save that" or "Remember this".
        """
        if not __request__:
            return "Error: Request context not available. Cannot save result."
        
        user_id = __user__.get("id")
        if not user_id:
            return "Error: User not authenticated. Cannot save result."
        
        try:
            # Import here to avoid circular imports at module load
            from open_webui.routers.mitchell import save_result_to_knowledge, SaveResultRequest
            from open_webui.models.users import Users
            
            # Get the full user object for the endpoint
            user = Users.get_user_by_id(user_id)
            if not user:
                return "Error: User not found. Cannot save result."
            
            # Build vehicle dict
            vehicle = {
                "year": year,
                "make": make,
                "model": model,
                "engine": engine or None,
            }
            
            # Call the save endpoint directly (we're inside Open WebUI)
            response = save_result_to_knowledge(
                request=__request__,
                form_data=SaveResultRequest(
                    vehicle=vehicle,
                    query=query,
                    content=content,
                    source=source or None,
                    tool=tool or None,
                ),
                user=user,
            )
            
            # Format response for user
            if response.status == "ok":
                # Extract knowledge base name from message
                kb_name = "Saved Automotive Data"
                if "'" in response.message:
                    parts = response.message.split("'")
                    if len(parts) >= 2:
                        kb_name = parts[1]
                
                return (
                    f"✅ **Saved successfully!**\n\n"
                    f"The information has been saved to your '{kb_name}' knowledge base.\n\n"
                    f"---\n"
                    f"⚠️ *{response.notice}*"
                )
            else:
                return f"Error saving result: {response.message}"
                
        except Exception as e:
            return f"Error saving result: {str(e)}"
