"""
title: Mitchell Automotive Data
author: autotech-ai
author_url: https://github.com/autotech-ai
version: 3.0.0
description: AI-powered automotive data retrieval using autonomous navigation.
required_open_webui_version: 0.4.0
"""

import httpx
from typing import Optional, Any
from pydantic import BaseModel, Field
from pydantic.fields import FieldInfo


def _sanitize_value(value: Any) -> Any:
    """Convert FieldInfo objects to None (handles direct Python calls with Field() defaults)."""
    if isinstance(value, FieldInfo):
        return None
    if value == "":
        return None
    return value


class Tools:
    """
    Mitchell Automotive Data - Unified AI Tool
    
    Uses autonomous AI navigation (llama3.1:8b) to intelligently find any
    automotive data in ShopKeyPro. One tool handles all queries.
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
        
        # Sanitize optional fields
        engine = _sanitize_value(engine)
        submodel = _sanitize_value(submodel)
        body_style = _sanitize_value(body_style)
        drive_type = _sanitize_value(drive_type)
        
        # Get user_id for billing
        user_id = __user__.get("id") if __user__ else None
        
        # Sanitize params
        sanitized_params = {k: _sanitize_value(v) for k, v in params.items()}
        sanitized_params = {k: v for k, v in sanitized_params.items() if v is not None}
        
        # Build request payload
        payload = {
            "shop_id": self.valves.SHOP_ID,
            "user_id": user_id,
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
        
        base_url = self.valves.API_BASE_URL.rstrip("/")
        
        try:
            async with httpx.AsyncClient(timeout=self.valves.REQUEST_TIMEOUT + 30) as client:
                response = await client.post(
                    f"{base_url}/api/mitchell/request",
                    json=payload
                )
                response.raise_for_status()
                request_data = response.json()
                request_id = request_data["id"]
                
                return await self._poll_for_result(
                    client, base_url, request_id, tool,
                    vehicle={"year": year, "make": make, "model": model, "engine": engine},
                    params=sanitized_params
                )
                    
        except httpx.TimeoutException:
            return "Error: Request timed out waiting for Mitchell agent."
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

    async def _poll_for_result(
        self,
        client,
        base_url: str,
        request_id: str,
        tool: str,
        vehicle: dict = None,
        params: dict = None
    ) -> str:
        """Poll for result until completed, failed, or timeout."""
        import asyncio
        import time
        
        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > self.valves.REQUEST_TIMEOUT:
                return "Error: Request timed out waiting for agent."
            
            try:
                status_response = await client.get(
                    f"{base_url}/api/mitchell/status/{request_id}"
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    
                    if status == "completed":
                        result = status_data.get("result", {})
                        if result.get("success"):
                            # Format images if present - these will be extracted by middleware
                            # and displayed as file attachments
                            images = result.get("images")
                            image_markdown = ""
                            if images:
                                image_markdown = self._format_images(images)
                            
                            # Format data
                            data = result.get("data", "")
                            
                            # Build response
                            if images:
                                # Return image markdown + data summary
                                # Middleware extracts the images; LLM just describes
                                formatted = image_markdown
                                if data and data.strip():
                                    if not data.startswith("Captured ") and "diagram(s)" not in data:
                                        import re
                                        clean_data = re.sub(r'^===\s*(WIRING\s*DIAGRAMS?|CHARGING|STARTING)\s*===\s*\n?', '', data, flags=re.IGNORECASE | re.MULTILINE)
                                        clean_data = clean_data.strip()
                                        if clean_data:
                                            formatted += f"\n\n{clean_data}"
                            else:
                                formatted = self._format_result(data, f"{tool} Result")
                            
                            # Note auto-selected options
                            auto_selected = result.get("auto_selected")
                            if auto_selected:
                                formatted += self._format_auto_selected(auto_selected)
                            
                            # Collect training data
                            try:
                                from addons.training_data.chat_hook import collect_from_mitchell_tool
                                collect_from_mitchell_tool(
                                    query=params.get("query", "") if params else "",
                                    vehicle=vehicle or {},
                                    tool_name=tool,
                                    result=result,
                                    formatted_response=formatted
                                )
                            except Exception as e:
                                print(f"[Mitchell Tool] Training data collection skipped: {e}")
                            
                            return formatted
                        else:
                            # Check for clarification
                            data = result.get("data", {})
                            if data and isinstance(data, dict) and data.get("clarification_needed"):
                                return self._format_clarification(data)
                            return f"Error: {result.get('error', 'Unknown error')}"
                    elif status == "failed":
                        result = status_data.get("result", {})
                        return f"Error: {result.get('error', 'Request failed')}"
                    elif status == "expired":
                        return "Error: Request expired. The agent may be offline."
            except Exception as e:
                print(f"[Mitchell Tool] Error checking status: {e}")
            
            await asyncio.sleep(2.0)

    def _format_images(self, images: list) -> str:
        """Format images as markdown. Middleware extracts these as file attachments."""
        if not images:
            return ""
        
        import os
        import base64
        from pathlib import Path
        import uuid
        
        # Get the actual STATIC_DIR used by the running server
        try:
            from open_webui.config import STATIC_DIR
            static_dir = Path(STATIC_DIR)
        except ImportError:
            # Fallback - try known locations
            possible_dirs = [
                os.environ.get("STATIC_DIR"),
                "/prod/autotech_ai/backend/open_webui/static",  # Production (hp6)
                "/home/drawson/autotech_ai/backend/open_webui/static",  # Dev
            ]
            
            static_dir = None
            for d in possible_dirs:
                if d and Path(d).exists():
                    static_dir = Path(d)
                    break
        
        if not static_dir or not static_dir.exists():
            self._debug(f"Could not find static directory, tried: {possible_dirs}")
            return "\n\n*(Images captured but could not be saved - static dir not found)*"
        
        mitchell_dir = static_dir / "mitchell"
        try:
            mitchell_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return f"\n\n*(Images captured but could not be saved: {e})*"
        
        lines = []
        for idx, img in enumerate(images):
            name = img.get("name", f"Diagram {idx + 1}")
            base64_data = img.get("base64", "")
            mime_type = img.get("mime_type", "image/png")
            
            if base64_data:
                # Determine correct extension from mime type
                if "svg" in mime_type:
                    ext = "svg"
                elif "png" in mime_type:
                    ext = "png"
                else:
                    ext = "jpg"
                filename = f"diagram_{uuid.uuid4().hex[:8]}.{ext}"
                filepath = mitchell_dir / filename
                
                try:
                    img_bytes = base64.b64decode(base64_data)
                    filepath.write_bytes(img_bytes)
                    url = f"/static/mitchell/{filename}"
                    # Simple markdown - middleware extracts as file attachment
                    lines.append(f"![{name}]({url})")
                except Exception as e:
                    lines.append(f"*(Error saving {name}: {e})*")
        
        return "\n\n".join(lines)

    def _format_auto_selected(self, auto_selected: dict) -> str:
        """Format auto-selected options note."""
        if not auto_selected:
            return ""
        
        items = [f"{k.replace('_', ' ').title()}: **{v}**" for k, v in auto_selected.items()]
        return (
            f"\n\n---\n"
            f"*Note: Auto-selected: {', '.join(items)}. "
            f"Specify in your query if incorrect.*"
        )

    def _format_clarification(self, data: dict) -> str:
        """Format clarification request."""
        field = data.get("missing_field", "unknown")
        options = data.get("options", [])
        options_display = options[:8]
        if len(options) > 8:
            options_display.append(f"... and {len(options) - 8} more")
        
        return (
            f"**Additional information needed**\n\n"
            f"Please specify the **{field.replace('_', ' ').title()}**.\n\n"
            f"Options: {', '.join(str(o) for o in options_display)}"
        )

    def _format_result(self, data, title: str) -> str:
        """Format result data into readable string."""
        if not data:
            return f"No {title.lower()} found."
        
        # Handle string data (from autonomous navigator)
        if isinstance(data, str):
            return f"**{title}:**\n\n{data}"
        
        lines = []
        
        # Check for looked up vehicle info
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
    
    async def mitchell(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        question: str = Field(..., description="Your automotive question - can include MULTIPLE questions in one call"),
        engine: str = Field(default="", description="Engine specification - optional"),
        submodel: str = Field(default="", description="Submodel/trim - optional"),
        body_style: str = Field(default="", description="Body style - optional"),
        drive_type: str = Field(default="", description="Drive type (2WD, 4WD, AWD) - optional"),
        __user__: dict = {},
        __messages__: list = []
    ) -> str:
        """
        Ask any automotive question. AI will intelligently find the answer.
        
        IMPORTANT: Pass the user's FULL question, even if it asks for multiple things!
        Do NOT split into multiple tool calls - this tool handles multi-part questions efficiently.
        
        Examples of GOOD usage:
        - "What's the oil capacity and spark plug gap?" → ONE call with full question
        - "Get me the wiring diagram and connector pinout for the alternator" → ONE call
        - "I need torque specs, fluid capacities, and reset procedure" → ONE call
        
        The AI will find all requested data in a single browser session.
        
        Just ask your question naturally - the AI will figure out the best path.
        """
        # Build conversation context from prior messages
        context = ""
        if __messages__:
            prior_msgs = __messages__[:-1]  # Exclude current message
            if prior_msgs:
                context_parts = []
                for msg in prior_msgs[-4:]:  # Last 4 messages for context
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                    if content:
                        context_parts.append(f"{role}: {content[:500]}")
                if context_parts:
                    context = "CONVERSATION CONTEXT (vehicle already discussed):\n" + "\n".join(context_parts)
        
        return await self._make_request(
            "query_autonomous",
            year, make, model, engine,
            submodel=submodel or None,
            body_style=body_style or None,
            drive_type=drive_type or None,
            __user__=__user__,
            question=question,
            context=context
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
        
        Use this first when:
        - User sends a plate photo
        - User provides a VIN to decode
        - User has plate + state
        
        Returns vehicle info that can be used for subsequent queries.
        """
        if not self.valves.SHOP_ID:
            return "Error: Shop ID not configured."
        
        raw_input = _sanitize_value(raw_input) or ""
        vin = _sanitize_value(vin) or ""
        plate = _sanitize_value(plate) or ""
        state = _sanitize_value(state) or ""
        
        if plate:
            plate = plate.replace(" ", "").replace("-", "").upper()
        
        user_id = __user__.get("id") if __user__ else None
        
        payload = {
            "shop_id": self.valves.SHOP_ID,
            "user_id": user_id,
            "tool": "lookup_vehicle",
            "vehicle": {"year": 0, "make": "Unknown", "model": "Unknown"},
            "params": {
                "raw_input": raw_input if raw_input else None,
                "vin": vin if vin else None,
                "plate": plate if plate else None,
                "state": state if state else None,
            },
            "timeout_seconds": self.valves.REQUEST_TIMEOUT
        }
        payload["params"] = {k: v for k, v in payload["params"].items() if v is not None}
        
        base_url = self.valves.API_BASE_URL.rstrip("/")
        
        try:
            async with httpx.AsyncClient(timeout=self.valves.REQUEST_TIMEOUT + 30) as client:
                response = await client.post(f"{base_url}/api/mitchell/request", json=payload)
                response.raise_for_status()
                request_id = response.json()["id"]
                return await self._poll_for_result(client, base_url, request_id, "lookup_vehicle")
        except httpx.TimeoutException:
            return "Error: Request timed out."
        except httpx.HTTPStatusError as e:
            return f"Error: HTTP {e.response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"

    async def save_result(
        self,
        year: int = Field(..., description="Vehicle year (e.g., 2018)"),
        make: str = Field(..., description="Vehicle make (e.g., Ford)"),
        model: str = Field(..., description="Vehicle model (e.g., F-150)"),
        query: str = Field(..., description="The original question or query"),
        content: str = Field(..., description="The result content to save"),
        source: str = Field(default="", description="Data source - optional"),
        tool: str = Field(default="", description="Which tool produced this result - optional"),
        engine: str = Field(default="", description="Engine specification - optional"),
        __user__: dict = {},
        __request__: any = None,
    ) -> str:
        """
        Save automotive data to your personal Knowledge base.
        
        Use when user explicitly asks to save or remember information.
        """
        if not __request__:
            return "Error: Request context not available."
        
        user_id = __user__.get("id")
        if not user_id:
            return "Error: User not authenticated."
        
        try:
            from open_webui.routers.mitchell import save_result_to_knowledge, SaveResultRequest
            from open_webui.models.users import Users
            
            user = Users.get_user_by_id(user_id)
            if not user:
                return "Error: User not found."
            
            vehicle = {
                "year": year,
                "make": make,
                "model": model,
                "engine": engine or None,
            }
            
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
            
            if response.status == "ok":
                return (
                    f"✅ **Saved successfully!**\n\n"
                    f"---\n"
                    f"⚠️ *{response.notice}*"
                )
            else:
                return f"Error: {response.message}"
                
        except Exception as e:
            return f"Error saving: {str(e)}"
