"""
AutoDB Navigator.

Main orchestration for AI-powered navigation of Operation CHARM site.
Brain-only model: AI decides what to click based on page state.
"""

import logging
import time
from typing import Optional

from .config import config
from .models import (
    PageState, NavigationResult, PathStep, ToolResult, Vehicle, LLMResponse
)
from .page_parser import PageParser
from .llm_client import LLMClient, parse_llm_action
from .prompts import build_system_prompt, build_user_message
from .tools import Tools

log = logging.getLogger("autodb_agent.navigator")


class AutodbNavigator:
    """
    AI-powered navigator for Operation CHARM site.
    
    Uses LLM to decide navigation actions based on page state.
    No hard-coded rules - trusts the AI to find the data.
    """
    
    def __init__(self, model: str = None, base_url: str = None):
        self.model = model or config.model
        self.base_url = base_url or config.base_url
        
        self.parser = PageParser(self.base_url)
        self.llm = LLMClient(self.model)
        self.tools = Tools(self.parser)
        
        log.info(f"AutodbNavigator initialized: model={self.model}, base_url={self.base_url}")
    
    async def close(self):
        """Clean up resources."""
        await self.parser.close()
        await self.llm.close()
    
    async def navigate(
        self,
        goal: str,
        vehicle: Vehicle | dict,
        max_steps: int = None,
    ) -> NavigationResult:
        """
        Navigate to find the requested information.
        
        Args:
            goal: What to find (e.g., "oil capacity", "torque specs")
            vehicle: Vehicle info (year, make, model, engine)
            max_steps: Maximum navigation steps (default from config)
        
        Returns:
            NavigationResult with content or error
        """
        max_steps = max_steps or config.max_steps
        
        # Normalize vehicle
        if isinstance(vehicle, dict):
            vehicle = Vehicle.from_dict(vehicle)
        
        log.info(f"Starting navigation: goal='{goal}', vehicle={vehicle}")
        
        # Initialize tools with vehicle info for egrep support
        self.tools = Tools(self.parser, vehicle=vehicle, base_url=self.base_url)
        
        path_taken: list[PathStep] = []
        
        # Timing instrumentation
        timing = {
            "start": time.time(),
            "llm_calls": [],
            "http_fetches": [],
            "parsing": [],
        }
        nav_start = time.time()
        
        try:
            # Start at homepage
            t0 = time.time()
            current_state = await self.parser.fetch_and_parse(self.base_url)
            timing["http_fetches"].append(("homepage", time.time() - t0))
            
            # Build system prompt (stays constant)
            system_prompt = build_system_prompt(goal, vehicle)
            
            for step in range(max_steps):
                log.info(f"Step {step + 1}/{max_steps}: {current_state.title}")
                
                # Build user message with current page state
                # Pass goal and vehicle to filter links when there are many
                page_text = current_state.to_prompt_text(
                    max_links=config.max_links_shown,
                    max_content=config.max_content_chars,
                    goal=goal,
                    vehicle=vehicle,
                )
                user_message = build_user_message(
                    page_text, 
                    path_taken,
                    max_path_history=config.max_path_history,
                )
                
                # DUMP THE PROMPT for debugging
                log.debug(f"=== SYSTEM PROMPT ===\n{system_prompt}")
                log.debug(f"=== USER MESSAGE ===\n{user_message}")
                
                # Ask LLM what to do
                t0 = time.time()
                response = await self.llm.call(system_prompt, user_message)
                llm_time = time.time() - t0
                timing["llm_calls"].append((f"step_{step+1}", llm_time))
                action = parse_llm_action(response.content)
                
                tool = action.get("tool", "extract")
                log.info(f"LLM action: {action}")
                
                # Execute the action
                if tool == "click":
                    link_text = action.get("link_text", "")
                    t0 = time.time()
                    result = await self.tools.click(link_text, current_state)
                    timing["http_fetches"].append((f"click_{link_text[:20]}", time.time() - t0))
                    
                    path_taken.append(PathStep(
                        action=f"CLICK '{link_text}'",
                        result_hint=result.hint,
                    ))
                    
                    if result.success and result.new_state:
                        current_state = result.new_state
                    elif not result.success:
                        # Link not found - let AI try again
                        log.warning(f"Click failed: {result.error}")
                        continue
                
                elif tool == "extract":
                    result = await self.tools.extract(current_state)
                    
                    if result.success:
                        total_time = time.time() - nav_start
                        llm_total = sum(t for _, t in timing["llm_calls"])
                        http_total = sum(t for _, t in timing["http_fetches"])
                        
                        log.info(f"Extraction successful: {len(result.extracted_content)} chars")
                        log.info(f"⏱️  TIMING BREAKDOWN:")
                        log.info(f"   Total: {total_time:.2f}s")
                        log.info(f"   LLM calls: {llm_total:.2f}s ({len(timing['llm_calls'])} calls)")
                        for name, t in timing["llm_calls"]:
                            log.info(f"      - {name}: {t:.2f}s")
                        log.info(f"   HTTP fetches: {http_total:.2f}s ({len(timing['http_fetches'])} fetches)")
                        for name, t in timing["http_fetches"]:
                            log.info(f"      - {name}: {t:.2f}s")
                        log.info(f"   Other: {total_time - llm_total - http_total:.2f}s")
                        
                        return NavigationResult(
                            success=True,
                            content=result.extracted_content,
                            url=current_state.url,
                            breadcrumb=" > ".join(current_state.breadcrumb),
                            images=current_state.images,  # Include any images found
                            path_taken=path_taken,
                            tokens_used={
                                "prompt_tokens": 0,  # Not tracked per-call
                                "completion_tokens": 0,
                                "total_tokens": self.llm.total_tokens_used,
                            },
                            steps_taken=step + 1,
                            timing={"total": total_time, "llm": llm_total, "http": http_total},
                        )
                    else:
                        log.warning(f"Extract failed: {result.error}")
                        # AI asked to extract but nothing there - continue
                        path_taken.append(PathStep(
                            action="EXTRACT",
                            result_hint=result.hint,
                        ))
                
                elif tool == "go_back":
                    result = await self.tools.go_back()
                    
                    path_taken.append(PathStep(
                        action="GO_BACK",
                        result_hint=result.hint,
                    ))
                    
                    if result.success and result.new_state:
                        current_state = result.new_state
                
                elif tool == "where_am_i":
                    result = self.tools.where_am_i(current_state, path_taken)
                    
                    path_taken.append(PathStep(
                        action="WHERE_AM_I",
                        result_hint=result.hint,
                    ))
                    # AI will see the result in the next page state via extracted_content
                    # For now, just log it - the AI will see it in the path_taken
                    log.info(f"where_am_i result:\n{result.extracted_content}")
                
                elif tool == "how_did_i_get_here":
                    result = self.tools.how_did_i_get_here(path_taken)
                    
                    path_taken.append(PathStep(
                        action="HOW_DID_I_GET_HERE",
                        result_hint=result.hint,
                    ))
                    log.info(f"how_did_i_get_here result:\n{result.extracted_content}")
                
                elif tool == "collect":
                    data = action.get("data", "")
                    label = action.get("label")
                    result = self.tools.collect(data, label)
                    
                    path_taken.append(PathStep(
                        action=f"COLLECT '{label or 'data'}'",
                        result_hint=result.hint,
                    ))
                    log.info(f"collect result: {result.hint}")
                
                elif tool == "done":
                    result = self.tools.done()
                    
                    if result.success:
                        total_time = time.time() - nav_start
                        llm_total = sum(t for _, t in timing["llm_calls"])
                        http_total = sum(t for _, t in timing["http_fetches"])
                        
                        log.info(f"Done successful: {len(result.extracted_content)} chars from {len(self.tools.collected_data)} items")
                        log.info(f"⏱️  TIMING BREAKDOWN:")
                        log.info(f"   Total: {total_time:.2f}s")
                        log.info(f"   LLM calls: {llm_total:.2f}s ({len(timing['llm_calls'])} calls)")
                        log.info(f"   HTTP fetches: {http_total:.2f}s ({len(timing['http_fetches'])} fetches)")
                        
                        return NavigationResult(
                            success=True,
                            content=result.extracted_content,
                            url=current_state.url,
                            breadcrumb=" > ".join(current_state.breadcrumb),
                            images=current_state.images,
                            path_taken=path_taken,
                            tokens_used={
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "total_tokens": self.llm.total_tokens_used,
                            },
                            steps_taken=step + 1,
                            timing={"total": total_time, "llm": llm_total, "http": http_total},
                        )
                    else:
                        # No collected data - let AI try again
                        path_taken.append(PathStep(
                            action="DONE",
                            result_hint=result.hint,
                        ))
                        log.warning(f"done failed: {result.error}")
                
                elif tool == "grep":
                    pattern = action.get("pattern", "")
                    result = self.tools.grep(pattern, current_state)
                    
                    path_taken.append(PathStep(
                        action=f"GREP '{pattern}'",
                        result_hint=result.hint,
                    ))
                    log.info(f"grep result: {result.hint}")
                    
                    # If grep found results, show them to the AI in a special way
                    if result.success and result.extracted_content:
                        # The grep results become the "content" shown to AI
                        # Store it temporarily so the next prompt shows it
                        current_state = PageState(
                            url=current_state.url,
                            title=f"GREP results for '{pattern}' on {current_state.title}",
                            breadcrumb=current_state.breadcrumb,
                            links=current_state.links,
                            content_text=result.extracted_content,
                            tables=current_state.tables,
                            images=current_state.images,
                            has_data=True,
                        )
                
                elif tool == "cat":
                    result = self.tools.cat(current_state)
                    
                    path_taken.append(PathStep(
                        action="CAT",
                        result_hint=result.hint,
                    ))
                    log.info(f"cat result: {result.hint}")
                    
                    # Replace current view with full content
                    if result.success and result.extracted_content:
                        current_state = PageState(
                            url=current_state.url,
                            title=f"Full content: {current_state.title}",
                            breadcrumb=current_state.breadcrumb,
                            links=current_state.links,
                            content_text=result.extracted_content,
                            tables=[],  # Already included in content
                            images=current_state.images,
                            has_data=True,
                        )
                
                elif tool == "egrep":
                    pattern = action.get("pattern", "")
                    result = self.tools.egrep(pattern)
                    
                    path_taken.append(PathStep(
                        action=f"EGREP '{pattern}'",
                        result_hint=result.hint,
                    ))
                    log.info(f"egrep result: {result.hint}")
                    
                    # Show search results to AI
                    if result.success and result.extracted_content:
                        current_state = PageState(
                            url=current_state.url,
                            title=f"SITE SEARCH results for '{pattern}'",
                            breadcrumb=["Search Results"],
                            links=current_state.links,
                            content_text=result.extracted_content,
                            tables=[],
                            images=[],
                            has_data=True,
                        )
                
                elif tool == "goto":
                    path = action.get("path", "")
                    result = self.tools.goto(path)
                    
                    path_taken.append(PathStep(
                        action=f"GOTO '{path}'",
                        result_hint=result.hint,
                    ))
                    
                    if result.success and result.extracted_content.startswith("GOTO:"):
                        # Navigate directly to the path
                        target_path = result.extracted_content.replace("GOTO:", "").strip()
                        
                        # The path from egrep may be:
                        # 1. Full path including vehicle: "Jeep Truck/1985/L4-150/Repair/..."
                        # 2. Relative path from vehicle: "Repair and Diagnosis/..."
                        
                        # Check if path starts with what looks like a make (contains a /year/ pattern)
                        import re
                        has_vehicle = bool(re.match(r'.+/\d{4}/', target_path))
                        
                        if has_vehicle:
                            # Full path - just append to base_url
                            from urllib.parse import quote
                            # URL-encode spaces but keep slashes
                            encoded_path = '/'.join(quote(segment, safe='') for segment in target_path.split('/'))
                            target_url = f"{self.base_url}/{encoded_path}"
                        else:
                            # Relative path - need vehicle base
                            current_url = current_state.url.rstrip('/')
                            
                            # Extract vehicle base URL from current path
                            # Pattern: /autodb/{make}/{year}/{model}/
                            vehicle_base = None
                            
                            url_parts = current_url.split('/autodb/')
                            if len(url_parts) > 1:
                                path_after_autodb = url_parts[1]
                                segments = path_after_autodb.split('/')
                                if len(segments) >= 3:
                                    vehicle_base = f"{self.base_url}/{'/'.join(segments[:3])}"
                            
                            if not vehicle_base:
                                # Fallback: construct from vehicle info
                                log.warning("Could not extract vehicle base from URL, using fallback")
                                from urllib.parse import quote
                                make_slug = quote(vehicle.make, safe='')
                                vehicle_base = f"{self.base_url}/{make_slug}/{vehicle.year}/{quote(vehicle.model, safe='')}"
                            
                            from urllib.parse import quote
                            encoded_path = '/'.join(quote(segment, safe='') for segment in target_path.split('/'))
                            target_url = f"{vehicle_base}/{encoded_path}"
                        
                        log.info(f"GOTO navigating to: {target_url}")
                        
                        t0 = time.time()
                        try:
                            new_state = await self.parser.fetch_and_parse(target_url)
                            timing["http_fetches"].append((f"goto_{path[:20]}", time.time() - t0))
                            current_state = new_state
                        except Exception as e:
                            log.error(f"GOTO failed: {e}")
                            path_taken[-1].result_hint = f"→ failed: {e}"
                
                else:
                    log.warning(f"Unknown tool: {tool}")
            
            # Max steps exceeded
            log.warning(f"Max steps ({max_steps}) exceeded")
            return NavigationResult(
                success=False,
                error=f"Could not find {goal} within {max_steps} steps",
                url=current_state.url,
                path_taken=path_taken,
                tokens_used={"total_tokens": self.llm.total_tokens_used},
                steps_taken=max_steps,
            )
        
        except Exception as e:
            log.exception(f"Navigation error: {e}")
            return NavigationResult(
                success=False,
                error=str(e),
                path_taken=path_taken,
                tokens_used={"total_tokens": self.llm.total_tokens_used},
            )
        
        finally:
            await self.close()


async def query_autodb(
    goal: str,
    vehicle: dict,
    model: str = None,
) -> NavigationResult:
    """
    Convenience function to query AutoDB.
    
    Args:
        goal: What to find
        vehicle: {year, make, model, engine?}
        model: LLM model to use (default from config)
    
    Returns:
        NavigationResult
    """
    navigator = AutodbNavigator(model=model)
    return await navigator.navigate(goal, vehicle)
