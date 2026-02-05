"""
Open WebUI Tool for AutoDB (Operation CHARM) queries.

This tool provides access to classic automotive service manuals
via the Operation CHARM database.
"""

import asyncio
import logging
from typing import Optional, Callable, Awaitable

from pydantic import BaseModel, Field

# Hardcoded defaults - these get baked into DB tool content
# For dev: use Ollama on poweredge1
# For prod: use Ollama on localhost
DEFAULT_MODEL = "qwen2.5:7b-instruct"
DEFAULT_BASE_URL = "http://automotive.aurora-sentient.net/autodb"

log = logging.getLogger("autodb_tool")


class Tools:
    """Open WebUI tool for AutoDB queries."""
    
    class Valves(BaseModel):
        """Configuration for the tool."""
        AUTODB_BASE_URL: str = Field(
            default=DEFAULT_BASE_URL,
            description="Base URL for Operation CHARM site"
        )
        MODEL: str = Field(
            default=DEFAULT_MODEL,
            description="LLM model for navigation"
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
        
        Coverage: 1982-2013 vehicles (varies by make/model)
        
        Args:
            year: Vehicle year (e.g., "2008")
            make: Vehicle make (e.g., "Honda", "Chevrolet", "Jeep")
            model: Vehicle model (e.g., "Accord", "Silverado", "Liberty")
            query: What to look up (e.g., "oil capacity", "P0300", "alternator wiring")
            engine: Engine type if known (e.g., "V6-3.5L")
        
        Returns:
            Service manual content matching the query
        """
        # Import here to avoid circular imports
        from addons.autodb_agent.navigator import AutodbNavigator
        from addons.autodb_agent.models import Vehicle
        
        # Emit status
        if __event_emitter__:
            await __event_emitter__({
                "type": "status",
                "data": {
                    "description": f"Searching AutoDB for {query}...",
                    "done": False
                }
            })
        
        # Build vehicle
        vehicle = Vehicle(
            year=year,
            make=make,
            model=model,
            engine=engine,
        )
        
        try:
            # Create navigator
            navigator = AutodbNavigator(
                model=self.valves.MODEL,
                base_url=self.valves.AUTODB_BASE_URL,
            )
            
            # Run navigation with timeout
            result = await asyncio.wait_for(
                navigator.navigate(goal=query, vehicle=vehicle),
                timeout=self.valves.REQUEST_TIMEOUT
            )
            
            # Record token usage for billing
            if result.tokens_used and result.tokens_used.get("total_tokens", 0) > 0:
                try:
                    from open_webui.models.billing import record_usage_event
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
                except Exception as e:
                    log.warning(f"[BILLING] Failed to record usage: {e}")
            
            if result.success:
                # Format successful response
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "Found data!", "done": True}
                    })
                
                # Format images if present
                images_text = ""
                if result.images:
                    images_text = "\n\n## Diagrams\n\n"
                    for img_url in result.images:
                        images_text += f"![Diagram]({img_url})\n\n"
                
                return f"""# {query.title()} for {vehicle}

**Source:** Operation CHARM Service Manual
**URL:** {result.url}
**Navigation:** {result.breadcrumb}
**Steps:** {result.steps_taken}

---

{result.content}{images_text}
"""
            else:
                # Format error response
                if __event_emitter__:
                    await __event_emitter__({
                        "type": "status",
                        "data": {"description": "Data not found in manual, using general knowledge", "done": True}
                    })
                
                path_text = result.format_path_taken() if result.path_taken else "none"
                
                return f"""# {query.title()} for {vehicle}

**Operation CHARM Status:** Not found in service manual
**Navigation path attempted:**
{path_text}

---

**IMPORTANT:** The specific data was not found in Operation CHARM service manuals for this vehicle.

Please provide your best answer for "{query}" on a {vehicle} based on your general automotive knowledge. 
Clearly indicate that this is general knowledge, not from the official service manual.
Include any relevant caveats about verifying specs before use."""
        
        except asyncio.TimeoutError:
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Request timed out", "done": True}
                })
            return f"Request timed out after {self.valves.REQUEST_TIMEOUT} seconds. Try a simpler query."
        
        except Exception as e:
            log.exception(f"AutoDB query error: {e}")
            if __event_emitter__:
                await __event_emitter__({
                    "type": "status",
                    "data": {"description": "Error occurred", "done": True}
                })
            return f"Error querying Operation CHARM: {str(e)}"
