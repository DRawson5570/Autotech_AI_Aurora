"""
Open WebUI Tool for Operation CHARM (autodb) queries.

This tool provides access to classic automotive service manuals
via the Operation CHARM database (AllData equivalent).
"""

import asyncio
import json
import logging
from typing import Optional, Any, Callable, Awaitable

from pydantic import BaseModel, Field

log = logging.getLogger("autodb_tool")


class Tools:
    """Open WebUI tool for autodb queries."""
    
    class Valves(BaseModel):
        """Configuration for the tool."""
        AUTODB_BASE_URL: str = Field(
            default="http://automotive.aurora-sentient.net/autodb",
            description="Base URL for Operation CHARM site"
        )
        MODEL: str = Field(
            default="gemini-2.0-flash",
            description="LLM model for navigation (gemini-2.0-flash or llama3.1:8b)"
        )
        REQUEST_TIMEOUT: int = Field(
            default=120,
            description="Timeout in seconds for queries"
        )
    
    def __init__(self):
        self.valves = self.Valves()
    
    async def autodb(
        self,
        year: str,
        make: str,
        model: str,
        query: str,
        engine: str = "",
        __user__: dict = None,
        __event_emitter__: Optional[Callable[[dict], Awaitable[None]]] = None,
    ) -> str:
        """
        Query Operation CHARM database for automotive service information.
        
        This tool provides access to classic automotive service manuals,
        specifications, TSBs, wiring diagrams, and repair procedures.
        
        Available data types:
        - Fluid capacities (oil, coolant, transmission)
        - Torque specifications
        - Technical Service Bulletins (TSBs)
        - Diagnostic Trouble Codes (DTCs)
        - Wiring diagrams
        - Repair procedures
        - Parts and labor information
        
        Coverage: 1982-2013 vehicles (varies by make/model)
        
        Args:
            year: Vehicle year (e.g., "2012")
            make: Vehicle make (e.g., "Jeep", "Chevrolet", "Honda")
            model: Vehicle model (e.g., "Liberty", "Accord", "F-150")
            query: What to look up (e.g., "oil capacity", "P0300", "alternator wiring")
            engine: Engine type if known (e.g., "V6-3.7L")
        
        Returns:
            Service manual content matching the query
        """
        # Import here to avoid circular imports
        from addons.autodb_tool.navigator import query_autodb, NavigationResult
        
        # Emit status
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"Searching autodb for {query}...",
                    "done": False
                }
            })
        
        # Build vehicle dict
        vehicle = {
            "year": year,
            "make": make,
            "model": model,
        }
        if engine:
            vehicle["engine"] = engine
        
        try:
            # Run the AI navigator
            result: NavigationResult = await asyncio.wait_for(
                query_autodb(
                    goal=query,
                    vehicle=vehicle,
                    model=self.valves.MODEL
                ),
                timeout=self.valves.REQUEST_TIMEOUT
            )
            
            if result.success:
                # Record token usage for billing
                if result.tokens_used and result.tokens_used.get("total_tokens", 0) > 0:
                    try:
                        from open_webui.models.billing import record_usage_event
                        # __user__ is passed as parameter to this function
                        user_id = __user__.get("id") if __user__ else None
                        
                        if user_id:
                            record_usage_event(
                                user_id=user_id,
                                chat_id=None,
                                message_id=None,
                                tokens_prompt=result.tokens_used.get("prompt_tokens", 0),
                                tokens_completion=result.tokens_used.get("completion_tokens", 0),
                                tokens_total=result.tokens_used.get("total_tokens", 0),
                                token_source="autodb_navigator"
                            )
                            log.info(f"[BILLING] Recorded {result.tokens_used.get('total_tokens', 0)} tokens for user {user_id}")
                        else:
                            log.warning("[BILLING] No user_id available for billing")
                    except Exception as e:
                        log.warning(f"[BILLING] Failed to record usage: {e}")
                
                # Format response
                response = f"""# {query.title()} for {year} {make} {model}

**Source:** Operation CHARM Service Manual
**URL:** {result.url}
**Navigation:** {result.breadcrumb}

---

{result.content}
"""
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "Found data!", "done": True}
                    })
                
                return response
            else:
                error_msg = f"Could not find {query}: {result.error}"
                if result.path_taken:
                    error_msg += f"\n\nNavigation attempted: {' → '.join(result.path_taken)}"
                
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": error_msg, "done": True}
                    })
                
                return error_msg
        
        except asyncio.TimeoutError:
            error_msg = f"Request timed out after {self.valves.REQUEST_TIMEOUT} seconds"
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": error_msg, "done": True}
                })
            return error_msg
        
        except Exception as e:
            log.exception("autodb tool error")
            error_msg = f"Error: {str(e)}"
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": error_msg, "done": True}
                })
            return error_msg
