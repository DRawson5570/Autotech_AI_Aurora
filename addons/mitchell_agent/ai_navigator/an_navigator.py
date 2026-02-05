"""
Autonomous Navigator - Main navigator class.

AI navigates ShopKeyPro using a cheat sheet (system prompt with navigation paths).
"""

import asyncio
import json

from playwright.async_api import Page

from .logging_config import get_logger, log_trace, log_step, log_navigation_start, log_navigation_end
from .an_models import ModelClient, ToolResult, TokenUsage
from .an_prompts import build_system_prompt, build_user_message
from .an_tools import execute_tool
from .element_extractor import get_page_state
from .an_config import DEFAULT_MODEL
from .timing import DELAY_MEDIUM, DELAY_SHORT, TIMEOUT_CLICK_SHORT

logger = get_logger(__name__)


class AutonomousNavigator:
    """
    Navigator that gives AI full control.
    Navigation paths are in the system prompt.
    
    Supports both Gemini (default) and Ollama models.
    - Gemini: gemini-2.5-flash, gemini-2.5-pro
    - Ollama: llama3.1:8b, llama3.1:70b
    """
    
    def __init__(self, model: str = None):
        """
        Initialize navigator with specified model.
        
        Args:
            model: Model name. If None, uses DEFAULT_MODEL (gemini-2.5-flash).
                   Set AN_MODEL env var to override default.
        """
        self.model = model or DEFAULT_MODEL
        self.max_steps = 50  # With memory hints, shouldn't need more than this
        self.model_client = ModelClient(self.model)
        self._captured_images = []
        self._token_usage = TokenUsage()  # Track cumulative token usage
        
        logger.info(f"AutonomousNavigator initialized with model: {self.model}")
    
    async def _return_to_landing_page(self, page) -> None:
        """
        Return to ShopKeyPro landing page (Quick Lookups / tile menu).
        Called after task completion to leave UI in clean state.
        """
        try:
            # Check if we're already on landing page
            page_text = await page.evaluate('() => document.body.innerText.substring(0, 1000)')
            if 'Wiring Diagrams' in page_text and 'Fluid Capacities' in page_text and 'Common Specs' in page_text:
                logger.info("    [cleanup] Already on landing page")
                return
            
            # Try clicking 1SEARCH PLUS link to get back to landing
            onesearch = page.locator('a:has-text("1SEARCH"), #oneSearchPlusAccess, a:text-is("1SEARCH PLUS")')
            if await onesearch.count() > 0:
                await onesearch.first.click(timeout=TIMEOUT_CLICK_SHORT)
                await page.wait_for_timeout(DELAY_MEDIUM)
                logger.info("    [cleanup] Clicked 1SEARCH PLUS to return to landing page")
                return
            
            # Fallback: look for the Home or Quick Lookups link
            home_link = page.locator('a:text-is("Home"), a:has-text("Quick Lookups")')
            if await home_link.count() > 0:
                await home_link.first.click(timeout=TIMEOUT_CLICK_SHORT)
                await page.wait_for_timeout(DELAY_MEDIUM)
                logger.info("    [cleanup] Clicked Home/Quick Lookups to return to landing page")
                return
                
            logger.warning("    [cleanup] Could not find navigation to landing page")
        except Exception as e:
            logger.warning(f"    [cleanup] Error returning to landing page: {e}")
    
    async def navigate(self, page: Page, goal: str, vehicle: dict, context: str = "") -> dict:
        """
        Let the AI autonomously navigate to find the goal.
        Returns the extracted data or failure info.
        
        Args:
            context: Optional conversation context from prior messages
        """
        # Log navigation start
        log_navigation_start(goal, vehicle)
        if context:
            logger.debug(f"Conversation context provided: {len(context)} chars")
        
        system_prompt = build_system_prompt(goal, vehicle, context=context)
        log_trace("SYSTEM_PROMPT", system_prompt)
        
        conversation = []
        path_taken = []
        click_history = []  # Track all clicks for loop detection
        self._captured_images = []  # Reset captured images
        self._collected_data = []  # Reset collected data for multi-step collection
        self._token_usage = TokenUsage()  # Reset token counter
        
        for step in range(self.max_steps):
            # Get current page state
            page_state = await get_page_state(page)
            
            # Check if modal is open
            modal_open = await page.locator('.modalDialogView').count() > 0
            
            # Get relevant text - prioritize modal content if modal is open
            if modal_open:
                page_text = await page.evaluate('''() => {
                    const modal = document.querySelector('.modalDialogView');
                    return modal ? modal.innerText : document.body.innerText;
                }''')
            else:
                page_text = await page.evaluate('() => document.body.innerText')
            
            user_message = build_user_message(page_state, page_text, modal_open, path_taken, goal, click_history, self._collected_data)
            
            # Log step info
            log_step(step + 1, self.max_steps, "PAGE_STATE", 
                     f"Modal: {'OPEN' if modal_open else 'closed'}, Elements: {len(page_state.elements)}")
            log_trace("USER_MESSAGE", user_message)
            
            # IMPORTANT: Don't accumulate full conversation history!
            # Just send current state + path summary. Otherwise prompt explodes to 200K tokens
            # and AI can't find the instructions anymore.
            conversation = [{"role": "user", "content": user_message}]
            
            # Ask AI what to do
            result = await self.model_client.call(system_prompt, conversation)
            
            # Track token usage (cumulative across all steps)
            step_usage = result.get('usage')
            if step_usage:
                self._token_usage = self._token_usage.add(step_usage)
                logger.debug(f"Tokens: +{step_usage.total_tokens} (cumulative: {self._token_usage.total_tokens})")
            else:
                logger.warning(f"Step {step+1}: No token usage returned from model")
            
            message = result.get('message', {})
            tool_calls = message.get('tool_calls', [])
            
            # Log AI response
            ai_content = message.get('content', '')
            log_trace("AI_RESPONSE", ai_content)
            
            if tool_calls:
                tool_names = [tc['function']['name'] for tc in tool_calls]
                logger.debug(f"AI tools: {tool_names}")
            
            if not tool_calls:
                # AI responded with text instead of tool call
                logger.info(f"Step {step + 1}: AI text response: {ai_content[:100]}...")
                
                # Check if it's giving up or confused
                if any(word in ai_content.lower() for word in ['cannot', "can't", 'unable', 'sorry']):
                    log_navigation_end(False, step + 1)
                    return {
                        "success": False,
                        "reason": "AI gave up",
                        "message": content,
                        "path": path_taken,
                        "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
                    }
                continue
            
            # MULTI-TOOL HANDLING: Process collect → capture_diagram → done in order
            # AI often wants to collect data AND capture images AND finish in one step
            tool_names = [tc['function']['name'] for tc in tool_calls]
            has_collect = 'collect' in tool_names
            has_capture = 'capture_diagram' in tool_names
            has_done = 'done' in tool_names or 'extract' in tool_names
            
            # If AI is trying to finish with multiple tools, process them in order
            if (has_collect or has_capture) and (has_done or len(tool_calls) > 1):
                logger.info(f"    [multi-tool] Processing: {tool_names}")
                
                # Step 1: Process ALL collect calls first
                for tc in tool_calls:
                    if tc['function']['name'] == 'collect':
                        tc_args = tc['function'].get('arguments', {})
                        if isinstance(tc_args, str):
                            tc_args = json.loads(tc_args)
                        collect_result = await execute_tool(
                            'collect', tc_args, page, page_state, goal,
                            path_taken=path_taken, modal_open=modal_open,
                            captured_images=self._captured_images,
                            collected_data=self._collected_data
                        )
                        if collect_result.success:
                            logger.info(f"    [multi-tool] Collected: {tc_args.get('label', 'data')[:40]}")
                            path_taken.append({
                                "tool": "collect",
                                "args": tc_args,
                                "result_hint": f"STORED: {tc_args.get('label', 'data')[:30]}"
                            })
                
                # Step 2: Process capture_diagram calls (captures ALL diagrams on page)
                capture_calls = [tc for tc in tool_calls if tc['function']['name'] == 'capture_diagram']
                if capture_calls:
                    descriptions = []
                    for cap_call in capture_calls:
                        cap_args = cap_call['function'].get('arguments', {})
                        if isinstance(cap_args, str):
                            cap_args = json.loads(cap_args)
                        desc = cap_args.get('description', '')
                        if desc:
                            descriptions.append(desc)
                    
                    combined_desc = "; ".join(descriptions) if descriptions else "diagram"
                    logger.info(f">>> CAPTURE DIAGRAM(S): {combined_desc[:80]}")
                    
                    cap_result = await execute_tool(
                        'capture_diagram', {'description': combined_desc}, page, page_state, goal,
                        path_taken=path_taken, modal_open=modal_open,
                        captured_images=self._captured_images
                    )
                    
                    step_record = {"tool": "capture_diagram", "args": {"description": combined_desc}}
                    if cap_result.success:
                        step_record["result_hint"] = f"CAPTURED {len(self._captured_images)} DIAGRAM(S)"
                    else:
                        step_record["result_hint"] = f"FAILED: {cap_result.result[:30]}"
                    path_taken.append(step_record)
                    logger.debug(f"Tool result: {cap_result.success}")
                    logger.info(f"  → {cap_result.result}")
                
                # Step 3: If done/extract was requested, finish up and return
                if has_done:
                    finish_call = next((tc for tc in tool_calls if tc['function']['name'] in ('done', 'extract')), None)
                    if finish_call:
                        finish_name = finish_call['function']['name']
                        finish_args = finish_call['function'].get('arguments', {})
                        if isinstance(finish_args, str):
                            finish_args = json.loads(finish_args)
                        
                        finish_result = await execute_tool(
                            finish_name, finish_args, page, page_state, goal,
                            path_taken=path_taken, modal_open=modal_open,
                            captured_images=self._captured_images,
                            collected_data=self._collected_data
                        )
                        
                        # Clean up and return
                        try:
                            close_btn = page.locator('.modalDialogView .close')
                            if await close_btn.count() > 0:
                                await close_btn.first.click(timeout=TIMEOUT_CLICK_SHORT)
                                await page.wait_for_timeout(DELAY_MEDIUM)
                                logger.info("    [cleanup] Closed modal")
                        except Exception as e:
                            logger.warning(f"    [cleanup] Could not close modal: {e}")
                        
                        await self._return_to_landing_page(page)
                        
                        result = {
                            "success": True,
                            "data": finish_result.result,
                            "path": path_taken,
                            "steps": step + 1,
                            "collected_items": len(self._collected_data),
                            "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
                        }
                        
                        if self._captured_images:
                            result["images"] = self._captured_images
                            logger.info(f"    [result] Including {len(self._captured_images)} image(s)")
                        
                        logger.info(f"    [done] Returning {len(self._collected_data)} collected items")
                        log_navigation_end(True, step + 1, len(self._collected_data), len(self._captured_images))
                        return result
                
                # Step 4: If AI wants to continue navigating (prior_page, click, etc.) after collecting,
                # RESET CONTEXT and go back to landing page for fresh start
                has_navigation = any(tc['function']['name'] in ('prior_page', 'click', 'click_text', 'go_back') for tc in tool_calls)
                if has_navigation and has_collect:
                    # AI collected an item and wants to navigate to next one
                    # RESET: Go back to landing page with clean context
                    collected_count = len(self._collected_data)
                    logger.info(f"    [multi-tool] Item collected + navigation requested. Resetting context for next item.")
                    
                    # Close any modals
                    try:
                        close_btn = page.locator('.modalDialogView .close')
                        if await close_btn.count() > 0:
                            await close_btn.first.click(timeout=TIMEOUT_CLICK_SHORT)
                            await page.wait_for_timeout(DELAY_MEDIUM)
                            logger.info("    [multi-tool] Closed modal")
                    except Exception as e:
                        logger.debug(f"    [multi-tool] No modal to close: {e}")
                    
                    # Return to landing page
                    await self._return_to_landing_page(page)
                    
                    # RESET PATH - keep only a note about what we collected
                    path_taken.clear()
                    path_taken.append({
                        "tool": "collect",
                        "args": {"label": "previous item(s)"},
                        "result_hint": f"✓ {collected_count} item(s) collected so far - find the next one!"
                    })
                    click_history.clear()
                    
                    logger.info(f"    [multi-tool] Context reset - ready for next item")
                    continue
                elif has_navigation:
                    # Navigation without collect - just execute it normally
                    nav_call = next((tc for tc in tool_calls if tc['function']['name'] in ('prior_page', 'click', 'click_text', 'go_back')), None)
                    if nav_call:
                        nav_name = nav_call['function']['name']
                        nav_args = nav_call['function'].get('arguments', {})
                        if isinstance(nav_args, str):
                            nav_args = json.loads(nav_args)
                        
                        logger.info(f"    [multi-tool] Executing navigation: {nav_name}")
                        nav_result = await execute_tool(
                            nav_name, nav_args, page, page_state, goal,
                            path_taken=path_taken, modal_open=modal_open,
                            captured_images=self._captured_images,
                            collected_data=self._collected_data
                        )
                        
                        path_taken.append({
                            "tool": nav_name,
                            "args": nav_args,
                            "result_hint": nav_result.result[:50] if nav_result.result else "navigated"
                        })
                        logger.info(f"  → {nav_result.result}")
                        # Continue the loop to process next step
                        continue
                
                # If we had capture but no done and no navigation, return now
                if has_capture and self._captured_images:
                    try:
                        close_btn = page.locator('.modalDialogView .close')
                        if await close_btn.count() > 0:
                            await close_btn.first.click(timeout=TIMEOUT_CLICK_SHORT)
                            await page.wait_for_timeout(DELAY_MEDIUM)
                    except:
                        pass
                    await self._return_to_landing_page(page)
                    
                    result = {
                        "success": True,
                        "data": f"Captured {len(self._captured_images)} image(s)",
                        "path": path_taken,
                        "steps": step + 1,
                        "images": self._captured_images,
                        "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
                    }
                    log_navigation_end(True, step + 1, len(self._collected_data), len(self._captured_images))
                    return result
            
            # SINGLE TOOL: Execute the first tool call
            tool_call = tool_calls[0]
            tool_name = tool_call['function']['name']
            tool_args = tool_call['function'].get('arguments', {})
            
            if isinstance(tool_args, str):
                tool_args = json.loads(tool_args)
            
            # Log the action
            reason = tool_args.get('reason', '')
            elem_text = None
            if tool_name == "click":
                elem_id = tool_args.get('element_id')
                # Handle string IDs from LLM - may include brackets like "[22]"
                if isinstance(elem_id, str):
                    elem_id = elem_id.strip('[]')
                    elem_id = int(elem_id)
                elem = next((e for e in page_state.elements if e.id == elem_id), None)
                elem_text = elem.text if elem and elem.text else '?'
                logger.info(f">>> CLICK [{elem_id}] '{elem_text[:50]}'  ({reason})")
            elif tool_name == "click_text":
                logger.info(f">>> CLICK TEXT: '{tool_args.get('text', '')[:50]}'  ({tool_args.get('reason', '')})")
            elif tool_name == "go_back":
                logger.info(f">>> GO BACK / CLOSE MODAL  ({reason})")
            elif tool_name == "extract":
                data_val = tool_args.get('data', '')
                if isinstance(data_val, str):
                    logger.info(f">>> EXTRACT DATA: {data_val[:60]}")
                else:
                    logger.info(f">>> EXTRACT DATA: {str(data_val)[:60]}")
            elif tool_name == "search":
                logger.info(f">>> SEARCH: '{tool_args.get('text', '')}'")
            elif tool_name == "capture_diagram":
                logger.info(f">>> CAPTURE DIAGRAM: {tool_args.get('description', '')[:40]}")
            elif tool_name == "expand_all":
                logger.info(f">>> EXPAND ALL")
            elif tool_name == "where_am_i":
                logger.info(f">>> WHERE AM I?")
            elif tool_name == "how_did_i_get_here":
                logger.info(f">>> HOW DID I GET HERE?")
            else:
                logger.info(f">>> {tool_name}({tool_args})")
            
            # Store clicked_text for breadcrumbs
            step_record = {"tool": tool_name, "args": tool_args.copy()}
            if elem_text:
                step_record["args"]["clicked_text"] = elem_text
            path_taken.append(step_record)
            
            # Track clicks for loop detection
            if tool_name in ("click", "click_text"):
                clicked_text = elem_text or tool_args.get("text", "")
                if clicked_text:
                    click_history.append(clicked_text)
            
            # Execute it
            tool_result = await execute_tool(
                tool_name, tool_args, page, page_state, goal,
                path_taken=path_taken, modal_open=modal_open,
                captured_images=self._captured_images,
                collected_data=self._collected_data
            )
            
            # Log tool result
            logger.debug(f"Tool result: {tool_name} success={tool_result.success}")
            
            # Handle 'ask_user' tool - return question to caller
            if tool_name == "ask_user" and tool_result.needs_user_input:
                logger.info(f"    [ask_user] Returning question to user: {tool_result.question}")
                return {
                    "success": True,
                    "needs_user_input": True,
                    "question": tool_result.question,
                    "options": tool_result.options,
                    "path": path_taken,
                    "steps": step + 1,
                    "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
                }
            
            logger.info(f"    Result: {tool_result.result[:80]}")
            
            # Add result hint to memory - tell him WHAT HAPPENED after clicking
            clicked_text = (elem_text or tool_args.get("text", "")).lower()
            if tool_result.success:
                if tool_name == "extract":
                    step_record["result_hint"] = f"EXTRACTED: {tool_result.result[:60]}..."
                elif tool_name == "collect":
                    # Hint will be set later with correct count
                    pass
                elif tool_name == "done":
                    step_record["result_hint"] = "DONE - returning all collected data!"
                elif tool_name == "capture_diagram":
                    step_record["result_hint"] = "DIAGRAM CAPTURED - task complete!"
                elif tool_name == "expand_all":
                    # Use the tool's result which includes what was found
                    step_record["result_hint"] = tool_result.result
                elif tool_name == "go_back":
                    step_record["result_hint"] = "closed modal, back to main page"
                elif tool_name == "prior_page":
                    # Check which section was just tried, suggest next
                    last_section = None
                    for prev in reversed(path_taken[:-1]):  # Exclude current step
                        prev_text = prev.get("args", {}).get("clicked_text", "").lower()
                        if "1 of 3" in prev_text:
                            last_section = 1
                            break
                        elif "2 of 3" in prev_text:
                            last_section = 2
                            break
                        elif "3 of 3" in prev_text:
                            last_section = 3
                            break
                    
                    if last_section == 1:
                        step_record["result_hint"] = "BACK to section list. You already tried SECTION 1 - now click SECTION 2 OF 3!"
                    elif last_section == 2:
                        step_record["result_hint"] = "BACK to section list. You tried 1 and 2 - now click SECTION 3 OF 3!"
                    elif last_section == 3:
                        step_record["result_hint"] = "BACK to section list. You tried all 3 sections - item may not exist!"
                    else:
                        step_record["result_hint"] = "returned to previous view"
                elif tool_name in ("click", "click_text"):
                    if "wiring diagram" in clicked_text:
                        step_record["result_hint"] = "modal opened with diagram options"
                    elif "dtc" in clicked_text or "diagnostic trouble" in clicked_text:
                        step_record["result_hint"] = "DTC INDEX opened - content is COLLAPSED! Use expand_all() to reveal all DTC codes, then click on your specific code."
                    elif "engine controls" in clicked_text or "transmission" in clicked_text or "body" in clicked_text:
                        step_record["result_hint"] = "DTC list loaded - scan PAGE TEXT for your code (P0171, etc) and click on it!"
                    elif "inline harness" in clicked_text:
                        step_record["result_hint"] = "NOW SHOWING CONNECTOR INDEX - click on your specific connector (X310, X200, etc)!"
                    elif "component" in clicked_text and "connector" in clicked_text:
                        step_record["result_hint"] = "NOW SHOWING COMPONENT INDEX - click on your specific component (A11, K20, etc)!"
                    elif "index" in clicked_text:
                        step_record["result_hint"] = "INDEX page loaded - click on specific item from the list!"
                    # Inline harness connector (X followed by numbers)
                    elif clicked_text.startswith("x") and any(c.isdigit() for c in clicked_text):
                        step_record["result_hint"] = "CONNECTOR DETAIL PAGE - extract the 'Description:' field (e.g. '20-Way F...')!"
                    # Component connector (A/B/C/K followed by numbers, like A11, K20, B100)
                    elif len(clicked_text) > 1 and clicked_text[0].isalpha() and any(c.isdigit() for c in clicked_text[:5]):
                        step_record["result_hint"] = "CONNECTOR DETAIL PAGE - extract the 'Description:' field (e.g. '1-Way F Coax...')!"
                    # TSB detail page - clicked on a TSB title (all caps, long title)
                    elif "tsb" in goal.lower() and len(clicked_text) > 20 and clicked_text.isupper():
                        step_record["result_hint"] = "TSB DETAIL PAGE LOADED - extract() the bulletin content NOW! Don't go back!"
                    else:
                        step_record["result_hint"] = "page updated"
            elif not tool_result.success:
                # Make failed hints more actionable
                if tool_name == "extract":
                    # Count how many failed extracts we've done
                    step_record["result_hint"] = f"FAILED: {tool_result.result}"
                else:
                    step_record["result_hint"] = f"FAILED: {tool_result.result}"
            
            # Add tool result to conversation
            conversation.append({
                "role": "tool",
                "content": tool_result.result,
            })
            
            logger.info(f"  → {tool_result.result}")
            
            # Check if capture_diagram succeeded - if so, we're done
            if tool_name == "capture_diagram" and tool_result.success:
                # Normal case: exit after first success
                try:
                    close_btn = page.locator('.modalDialogView .close')
                    if await close_btn.count() > 0:
                        await close_btn.first.click(timeout=TIMEOUT_CLICK_SHORT)
                        await page.wait_for_timeout(DELAY_MEDIUM)
                        logger.info("    [cleanup] Closed modal")
                except Exception as e:
                    logger.warning(f"    [cleanup] Could not close modal: {e}")
                
                # Return to landing page after task completion
                await self._return_to_landing_page(page)
                
                result = {
                    "success": True,
                    "data": tool_result.result,
                    "path": path_taken,
                    "steps": step + 1,
                    "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
                }
                
                # Include captured images if any
                if self._captured_images:
                    result["images"] = self._captured_images
                    logger.info(f"    [result] Including {len(self._captured_images)} image(s)")
                
                if self._token_usage.total_tokens > 0:
                    logger.info(f"    [tokens] {self._token_usage.total_tokens} total ({self._token_usage.prompt_tokens} prompt, {self._token_usage.completion_tokens} completion)")
                
                log_navigation_end(True, step + 1, len(self._collected_data), len(self._captured_images))
                return result
            
            # Handle 'collect' tool - just log it, don't reset
            # AI might want to capture_diagram on next step
            # Context reset only happens in multi-tool path when AI explicitly navigates away
            if tool_name == "collect" and tool_result.success:
                collected_count = len(self._collected_data)
                label = tool_args.get('label', 'data')[:30]
                step_record["result_hint"] = f"✓ STORED '{label}' (item #{collected_count})"
                logger.info(f"    [collect] ✓ Stored item #{collected_count}: {label}")
            
            # Handle 'done' tool - exit with all collected data
            if tool_name == "done" and tool_result.success:
                # Clean up modals
                try:
                    close_btn = page.locator('.modalDialogView .close')
                    if await close_btn.count() > 0:
                        await close_btn.first.click(timeout=TIMEOUT_CLICK_SHORT)
                        await page.wait_for_timeout(DELAY_MEDIUM)
                        logger.info("    [cleanup] Closed modal")
                except Exception as e:
                    logger.warning(f"    [cleanup] Could not close modal: {e}")
                
                # Return to landing page after task completion
                await self._return_to_landing_page(page)
                
                result = {
                    "success": True,
                    "data": tool_result.result,  # Combined collected data
                    "path": path_taken,
                    "steps": step + 1,
                    "collected_items": len(self._collected_data),
                    "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
                }
                
                # Include captured images if any
                if self._captured_images:
                    result["images"] = self._captured_images
                    logger.info(f"    [result] Including {len(self._captured_images)} image(s)")
                
                logger.info(f"    [done] Returning {len(self._collected_data)} collected items")
                
                log_navigation_end(True, step + 1, len(self._collected_data), len(self._captured_images))
                return result
        
        # Ran out of steps - clean up ALL modals (may be nested)
        try:
            for _ in range(5):  # Handle up to 5 nested modals
                close_btn = page.locator('.modalDialogView .close')
                if await close_btn.count() > 0:
                    await close_btn.first.click(timeout=TIMEOUT_CLICK_SHORT)
                    await page.wait_for_timeout(DELAY_SHORT)
                    logger.debug("Closed modal after max steps")
                else:
                    break
        except Exception as e:
            logger.warning(f"Error closing modals: {e}")
        
        # Return to landing page even on failure
        await self._return_to_landing_page(page)
        
        log_navigation_end(False, self.max_steps)
        logger.warning(f"MAX STEPS REACHED: goal='{goal}'")
        
        return {
            "success": False,
            "reason": "Max steps reached",
            "path": path_taken,
            "tokens_used": self._token_usage.to_dict() if self._token_usage.total_tokens > 0 else None,
        }


async def query_mitchell_autonomous(
    page: Page,
    goal: str,
    vehicle: dict,
    model: str = None,
    context: str = ""
) -> dict:
    """
    Execute a query using the autonomous navigator.
    
    This is the main entry point for the agent service.
    The page should already be logged in and vehicle selected.
    
    Args:
        page: Playwright page (logged in, vehicle selected, at landing page)
        goal: User's query (e.g., "What is DTC P0455", "engine oil capacity")
        vehicle: Vehicle dict with year, make, model, engine
        model: Model to use (gemini-2.5-flash default, or llama3.1:8b for Ollama)
        context: Conversation context from prior messages (optional)
        
    Returns:
        dict with:
            success: bool
            data: str (the extracted data)
            error: str (if failed)
            path: list (navigation path taken)
            steps: int (number of steps)
    """
    navigator = AutonomousNavigator(model=model)
    result = await navigator.navigate(page, goal, vehicle, context=context)
    
    # Normalize result format for agent service
    normalized = {
        "success": result.get("success", False),
        "data": result.get("data"),
        "error": result.get("reason") if not result.get("success") else None,
        "path": result.get("path", []),
        "steps": result.get("steps", 0),
    }
    
    # Include images if captured
    if result.get("images"):
        normalized["images"] = result["images"]
    
    # Include token usage for billing
    if result.get("tokens_used"):
        normalized["tokens_used"] = result["tokens_used"]
    
    return normalized


async def test_autonomous_navigation(goal: str = None, model: str = None):
    """Test the autonomous navigator."""
    import os
    from playwright.async_api import async_playwright
    
    vehicle = {"year": "2014", "make": "Chevrolet", "model": "Cruze", "engine": "1.4L Eco"}
    if not goal:
        goal = "alternator wiring diagram"
    
    cdp_url = os.environ.get("CHROME_CDP_URL", "http://127.0.0.1:9222")
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.pages[0]
        
        navigator = AutonomousNavigator(model=model)
        
        print("=" * 60)
        print(f"AUTONOMOUS NAVIGATION TEST")
        print(f"Goal: {goal}")
        print(f"Vehicle: {vehicle}")
        print(f"Model: {navigator.model}")
        print("=" * 60)
        
        result = await navigator.navigate(page, goal, vehicle)
        
        print("\n" + "=" * 60)
        print("RESULT:")
        print(json.dumps(result, indent=2))
        return result


if __name__ == "__main__":
    import sys
    import argparse
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s'  # Clean output, no timestamps
    )
    
    parser = argparse.ArgumentParser(description='Autonomous Navigator Test')
    parser.add_argument('goal', nargs='*', help='Navigation goal (e.g., "alternator wiring diagram")')
    parser.add_argument('--model', '-m', default=None, 
                        help=f'Model to use (default: {DEFAULT_MODEL}). '
                             'Gemini: gemini-2.5-flash, gemini-2.5-pro. '
                             'Ollama: llama3.1:8b, llama3.1:70b')
    args = parser.parse_args()
    
    goal_text = " ".join(args.goal) if args.goal else None
    asyncio.run(test_autonomous_navigation(goal=goal_text, model=args.model))
