"""
Navigation Loop - Systematic Exploration with Golden Thread
============================================================

The AI explores ShopKeyPro systematically:
1. Check memory for known path (replay if found)
2. Plan candidate paths (ranked by common sense)
3. Try one path at a time
4. On success: trace back the "golden thread" and record it
5. On dead-end: backtrack to landing page, try next

The "golden thread" is the clean, replayable path from start to success.
Each step captures: what was clicked, what it said, where we were, what happened.
"""

import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import Page

from .element_extractor import get_page_state, get_visible_text, PageState
from .ai_navigator import AINavigator, NavigationAction, NavigationResult, ActionType
from .action_executor import ActionExecutor
from .navigation_memory import (
    NavigationMemory, NavigationStep, LearnedPath,
    get_memory, record_success, record_failure, get_known_path, get_selectors
)
from .common_sense import rank_candidates, QUICK_ACCESS_BUTTONS
from .timing import DELAY_STEP, DELAY_MODAL, TIMEOUT_CLICK_LONG, TIMEOUT_ACTION, MAX_HISTORY_LOOP
from . import action_log

log = logging.getLogger(__name__)

SCREENSHOT_DIR = Path(os.environ.get("MITCHELL_SCREENSHOT_DIR", "/tmp/ai_navigator_screenshots"))

# Use specific selectors to avoid duplicates
LANDING_PAGE_INDICATORS = [
    "#quickLinkRegion #fluidsQuickAccess",
    "#quickLinkRegion #commonSpecsAccess",
]


class NavigationLoop:
    """
    Systematic navigation with golden thread tracking.
    
    When the AI finds data:
    1. Walks back through exploration history
    2. Extracts the clean path (selector + context + result)
    3. Records it for future replay
    """
    
    def __init__(
        self,
        page: Page,
        api_key: str,
        model: str = "gemini-2.0-flash",
        max_steps_per_path: int = 8,
        max_candidates: int = 5,
        action_timeout: float = 10.0,
        save_screenshots: bool = True,
    ):
        self.page = page
        self.max_steps_per_path = max_steps_per_path
        self.max_candidates = max_candidates
        self.save_screenshots = save_screenshots
        
        self.ai = AINavigator(api_key=api_key, model=model)
        self.executor = ActionExecutor(page=page, action_timeout=action_timeout)
        self.memory = get_memory()
        
        # Golden thread tracking
        self.current_steps: List[NavigationStep] = []  # Steps in current path attempt
        self.total_steps = 0
        self.history: List[str] = []  # Human-readable history
        
        if save_screenshots:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    
    def _record_step(
        self,
        action: str,
        selector: str,
        element_text: str = "",
        context: str = "",
        result: str = ""
    ) -> None:
        """Record a step in the golden thread."""
        step = NavigationStep(
            action=action,
            selector=selector,
            element_text=element_text,
            context=context,
            result=result
        )
        self.current_steps.append(step)
        log.debug(f"Step recorded: {action} → {selector} ({result})")
    
    def _clear_steps(self) -> None:
        """Clear current path steps (for backtracking)."""
        self.current_steps = []
    
    async def _get_element_text(self, selector: str) -> str:
        """Get the text content of an element."""
        try:
            elem = self.page.locator(selector).first
            if await elem.is_visible(timeout=1000):
                text = await elem.text_content()
                return (text or "").strip()[:50]
        except:
            pass
        return ""
    
    async def _get_current_context(self) -> str:
        """Determine current page context (landing, modal, etc.)."""
        try:
            # Check if modal is open
            modal = self.page.locator(".modalDialogView")
            if await modal.is_visible(timeout=500):
                # Try to get modal title
                title = await modal.locator("h1, h2, .title, .header").first.text_content()
                return f"in {(title or 'modal').strip()[:30]} modal"
        except:
            pass
        
        # Check if at landing page
        if await self.is_at_landing_page():
            return "landing page"
        
        return "unknown page"
    
    async def is_at_landing_page(self) -> bool:
        """Check if at landing page with Quick Access buttons AND no modal open."""
        # First check if a modal is open - if so, we're NOT at landing page
        try:
            modal = self.page.locator(".modalDialogView")
            if await modal.is_visible(timeout=300):
                return False  # Modal is open, not truly at landing
        except:
            pass
        
        # Now check for Quick Access buttons
        for selector in LANDING_PAGE_INDICATORS:
            try:
                elem = self.page.locator(selector)
                if await elem.is_visible(timeout=1000):
                    return True
            except:
                pass
        return False
    
    async def backtrack_to_landing(self) -> bool:
        """Return to landing page by closing modals. NEVER uses browser back."""
        log.info("Backtracking to landing page...")
        
        # Only close modals - browser back is too dangerous
        for _ in range(5):
            # Check if we're there
            if await self.is_at_landing_page():
                log.info("✓ Back at landing (closed modal)")
                return True
            
            # Try to close any modal
            closed = False
            for close_sel in [".modalDialogView .close", ".modalDialogView span.close", "input[data-action='Cancel']"]:
                try:
                    close_btn = self.page.locator(close_sel).first
                    if await close_btn.is_visible(timeout=500):
                        await close_btn.click()
                        await asyncio.sleep(DELAY_MODAL)
                        closed = True
                        break
                except:
                    pass
            
            if not closed:
                break  # No more modals to close
        
        if await self.is_at_landing_page():
            log.info("✓ Back at landing")
            return True
        
        log.warning("Could not backtrack to landing page")
        return False
    
    async def _return_to_landing_page(self) -> None:
        """
        Return to landing page after completing a task.
        Leaves browser in clean state for next query.
        Only closes modals - NEVER does browser back (too dangerous).
        """
        log.info("🏠 Returning to landing page...")
        
        # Keep closing modals until none are visible
        for attempt in range(5):
            # First check if any modal is open - close it regardless of landing page state
            modal_closed = False
            for close_sel in [".modalDialogView .close", ".modalDialogView span.close", "span.close"]:
                try:
                    close_btn = self.page.locator(close_sel).first
                    if await close_btn.is_visible(timeout=500):
                        log.info(f"  Closing modal (attempt {attempt + 1})...")
                        await close_btn.click()
                        await asyncio.sleep(DELAY_MODAL)
                        modal_closed = True
                        break
                except:
                    pass
            
            # If no modal was closed, check if we're at landing page
            if not modal_closed:
                if await self.is_at_landing_page():
                    log.info("✓ At landing page (no modals)")
                    return
                else:
                    log.warning("No modal to close but not at landing page")
                    break
        
        # Final verification
        if await self.is_at_landing_page():
            log.info("✓ At landing page")
        else:
            log.warning("Could not return to landing page (non-fatal)")
    
    async def try_known_path(
        self,
        path: LearnedPath,
        goal: str,
        vehicle: Dict[str, str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Replay a known successful path.
        
        Args:
            path: The LearnedPath to replay
            goal: What we're looking for
            vehicle: Vehicle info
            
        Returns:
            (success, extracted_data)
        """
        log.info(f"🔄 Replaying known path: {path.human_readable}")
        self._clear_steps()
        
        for i, selector in enumerate(path.selectors):
            context = await self._get_current_context()
            elem_text = await self._get_element_text(selector)
            
            try:
                elem = self.page.locator(selector)
                
                # Handle duplicates
                count = await elem.count()
                if count > 1:
                    for j in range(count):
                        nth = elem.nth(j)
                        if await nth.is_visible():
                            elem = nth
                            break
                    else:
                        elem = elem.first
                
                await elem.wait_for(state="visible", timeout=TIMEOUT_CLICK_LONG)
                await elem.click()
                
                self._record_step(
                    action="click",
                    selector=selector,
                    element_text=elem_text,
                    context=context,
                    result="clicked"
                )
                
                self.total_steps += 1
                self.history.append(f"Replay: {selector}")
                await asyncio.sleep(DELAY_MODAL)
                
            except Exception as e:
                log.warning(f"Replay failed at step {i+1}: {e}")
                return False, None
        
        # Now check if data is here
        data = await self._extract_data_from_page(goal, vehicle)
        
        if data:
            # Update step result
            if self.current_steps:
                self.current_steps[-1].result = f"FOUND: {data[:30]}..."
            return True, data
        
        return False, None
    
    async def _extract_data_from_page(
        self,
        goal: str,
        vehicle: Dict[str, str],
    ) -> Optional[str]:
        """Let AI check if target data is on current page."""
        page_state = await get_page_state(self.page)
        page_text = await get_visible_text(self.page)
        
        # Ask AI to check for data
        action = await self.ai.decide_action(
            page_state=page_state,
            page_text=page_text,
            goal=goal,
            vehicle=vehicle,
            history=["Checking if data is visible on this page..."],
        )
        
        if action.action_type == ActionType.EXTRACT_DATA:
            return action.text
        
        return None
    
    async def try_candidate(
        self,
        selector: str,
        name: str,
        goal: str,
        vehicle: Dict[str, str],
    ) -> Tuple[bool, Optional[str], List[NavigationStep]]:
        """
        Try a candidate path from landing page.
        
        Args:
            selector: The Quick Access button selector
            name: Human-readable name
            goal: What we're looking for
            vehicle: Vehicle info
            
        Returns:
            (success, extracted_data, steps_taken)
        """
        log.info(f">>> Trying: {name} ({selector}) <<<")
        self._clear_steps()
        
        # Get context before clicking
        context = await self._get_current_context()
        elem_text = await self._get_element_text(selector)
        
        # Click the candidate
        try:
            elem = self.page.locator(selector)
            
            # Handle duplicates
            count = await elem.count()
            if count > 1:
                for i in range(count):
                    nth = elem.nth(i)
                    if await nth.is_visible():
                        elem = nth
                        break
                else:
                    elem = elem.first
            
            await elem.wait_for(state="visible", timeout=TIMEOUT_CLICK_LONG)
            await elem.click()
            
            self._record_step(
                action="click",
                selector=selector,
                element_text=elem_text or name,
                context=context,
                result="opened section"
            )
            
            self.total_steps += 1
            self.history.append(f"Click: {name}")
            await asyncio.sleep(DELAY_MODAL)
            
        except Exception as e:
            log.warning(f"Click failed on {selector}: {e}")
            return False, None, self.current_steps
        
        # Now let AI explore for data
        data = await self._explore_for_data(goal, vehicle)
        
        if data:
            # Update last step with success
            if self.current_steps:
                self.current_steps[-1].result = f"FOUND: {data[:50]}..."
            return True, data, self.current_steps
        
        return False, None, self.current_steps
    
    async def _explore_for_data(
        self,
        goal: str,
        vehicle: Dict[str, str],
    ) -> Optional[str]:
        """
        Let AI explore current section for data.
        
        Returns:
            Extracted data if found, None otherwise
        """
        steps_here = 0
        extracted_data = None
        last_selectors = []  # Track recent clicks to detect loops
        consecutive_failures = 0
        last_page_state_hash = ""
        
        while steps_here < self.max_steps_per_path:
            steps_here += 1
            self.total_steps += 1
            
            log.info(f"  Exploration step {steps_here}/{self.max_steps_per_path}")
            
            # Get page state
            page_state = await get_page_state(self.page)
            page_text = await get_visible_text(self.page)
            
            # Detect if page actually changed (simple hash of element IDs)
            current_hash = str(len(page_state.elements)) + "_" + str(page_state.has_modal)
            if current_hash == last_page_state_hash and consecutive_failures > 0:
                log.warning("  Page state unchanged after failed click - possible stuck state")
                consecutive_failures += 1
            else:
                consecutive_failures = 0 if last_page_state_hash else consecutive_failures
            last_page_state_hash = current_hash
            
            # Break if stuck
            if consecutive_failures >= 3:
                log.warning("  Breaking out - stuck in loop (3 consecutive failures, no state change)")
                return extracted_data
            
            # Screenshot
            if self.save_screenshots:
                ts = datetime.now().strftime("%H%M%S")
                ss = SCREENSHOT_DIR / f"explore_{self.total_steps:02d}_{ts}.png"
                try:
                    await self.page.screenshot(path=str(ss))
                except:
                    pass
            
            # Ask AI
            action = await self.ai.decide_action(
                page_state=page_state,
                page_text=page_text,
                goal=goal,
                vehicle=vehicle,
                history=self.history[-MAX_HISTORY_LOOP:],
            )
            
            # Handle response
            if action.action_type == ActionType.EXTRACT_DATA:
                extracted_data = action.text
                is_complete = "complete=true" in (action.reason or "").lower()
                log.info(f"  ✓ Data found: {extracted_data[:80]}... (complete={is_complete})")
                
                # If AI says complete=true, trust it and return
                # Also return if we have substantial data (>50 chars)
                if is_complete or (extracted_data and len(extracted_data) > 50):
                    return extracted_data
            
            elif action.action_type == ActionType.DONE:
                return action.text or extracted_data
            
            elif action.action_type == ActionType.FAIL:
                log.info(f"  Dead-end: {action.reason}")
                return extracted_data
            
            elif action.action_type in (ActionType.CLOSE_MODAL, ActionType.BACK):
                log.info("  AI wants to backtrack - dead end")
                return extracted_data
            
            elif action.action_type == ActionType.CLICK:
                # Check for click loop (same selector 3+ times)
                if action.selector in last_selectors[-2:]:
                    log.warning(f"  Loop detected: clicking {action.selector} again")
                    consecutive_failures += 1
                    if consecutive_failures >= 2:
                        log.warning("  Breaking out - repeated same click")
                        return extracted_data
                
                last_selectors.append(action.selector)
                if len(last_selectors) > 5:
                    last_selectors.pop(0)
                
                # Continue exploring deeper
                context = await self._get_current_context()
                elem_text = await self._get_element_text(action.selector)
                
                success = await self.executor.execute(action)
                
                if success:
                    consecutive_failures = 0  # Reset on success
                    self._record_step(
                        action="click",
                        selector=action.selector,
                        element_text=elem_text,
                        context=context,
                        result=action.reason[:30] if action.reason else "clicked"
                    )
                    self.history.append(f"Click: {action.selector[:40]}")
                else:
                    consecutive_failures += 1
                    self.history.append(f"Click FAILED: {action.selector[:40]}")
                    if consecutive_failures >= 3:
                        log.warning("  Breaking out - 3 consecutive click failures")
                        return extracted_data
            
            elif action.action_type == ActionType.SCROLL:
                await self.executor.execute(action)
            
            await asyncio.sleep(DELAY_STEP)
        
        log.info("  Max exploration steps reached")
        return extracted_data
    
    async def navigate_pure_ai(
        self,
        goal: str,
        vehicle: Dict[str, str],
    ) -> NavigationResult:
        """
        Pure AI navigation - no hand-holding.
        
        Just shows AI the page and goal, lets it figure out everything.
        No candidate ranking, no keyword matching.
        
        Args:
            goal: What to find
            vehicle: Vehicle info
            
        Returns:
            NavigationResult
        """
        log.info(f"{'='*50}")
        log.info(f"PURE AI Navigation (no hand-holding)")
        log.info(f"Goal: {goal}")
        log.info(f"Vehicle: {vehicle}")
        log.info(f"{'='*50}")
        
        # Log session start to action log
        action_log.log_session_start(goal, vehicle)
        
        self.total_steps = 0
        self.history = []
        self.current_steps = []
        
        # Ensure we're at landing page
        if not await self.is_at_landing_page():
            await self.backtrack_to_landing()
        
        # Let AI explore from scratch
        data = await self._explore_for_data(goal, vehicle)
        
        if data:
            log.info(f"✓ AI found data in {self.total_steps} steps")
            
            # Log session end
            action_log.log_session_end(success=True, result=data, steps=self.total_steps)
            
            # Record the golden thread
            record_success(goal, self.current_steps, data)
            
            # Return to landing page
            await self._return_to_landing_page()
            
            return NavigationResult(
                success=True,
                data=data,
                message=f"Found via pure AI navigation",
                steps_taken=self.total_steps,
                history=self.history,
            )
        
        log.warning(f"✗ AI failed to find data in {self.total_steps} steps")
        action_log.log_session_end(success=False, steps=self.total_steps)
        await self._return_to_landing_page()
        
        return NavigationResult(
            success=False,
            data=None,
            message="AI could not find the requested data",
            steps_taken=self.total_steps,
            history=self.history,
        )
    
    async def navigate(
        self,
        goal: str,
        vehicle: Dict[str, str],
    ) -> NavigationResult:
        """
        Navigate to find the requested data.
        
        Strategy:
        1. Check memory for known path → replay if found
        2. Plan candidates by common sense
        3. Try each candidate, backtracking between attempts
        4. On success: record golden thread
        
        Args:
            goal: What to find
            vehicle: Vehicle info
            
        Returns:
            NavigationResult
        """
        log.info(f"{'='*50}")
        log.info(f"AI Navigation Start")
        log.info(f"Goal: {goal}")
        log.info(f"Vehicle: {vehicle}")
        log.info(f"{'='*50}")
        
        # Log session start to action log
        action_log.log_session_start(goal, vehicle)
        
        self.total_steps = 0
        self.history = []
        
        # Step 1: Check memory
        known = get_known_path(goal)
        if known:
            log.info(f"🧠 Found known path: {known.human_readable}")
            
            success, data = await self.try_known_path(known, goal, vehicle)
            
            if success and data:
                log.info("✓ Known path succeeded!")
                # Reinforce the path
                record_success(goal, self.current_steps, data)
                
                # Log session success
                action_log.log_session_end(success=True, result=data, steps=self.total_steps)
                
                # Return to landing page - leave browser clean for next query
                await self._return_to_landing_page()
                
                return NavigationResult(
                    success=True,
                    data=data,
                    message=f"Found via known path: {known.human_readable}",
                    steps_taken=self.total_steps,
                    history=self.history,
                )
            else:
                log.info("Known path failed, exploring alternatives")
                await self.backtrack_to_landing()
        
        # Step 2: Plan candidates
        candidates = rank_candidates(goal)
        log.info(f"Planned {len(candidates)} candidates:")
        for sel, name, score in candidates[:self.max_candidates]:
            log.info(f"  {score:.2f} - {name}")
        
        # Step 3: Try each candidate
        failed_selectors = self.memory.get_failed_paths(goal)
        
        for selector, name, score in candidates[:self.max_candidates]:
            # Skip previously failed
            if [selector] in failed_selectors:
                log.info(f"Skipping {name} - previously failed")
                continue
            
            # Ensure at landing
            if not await self.is_at_landing_page():
                if not await self.backtrack_to_landing():
                    log.warning("Cannot backtrack, trying anyway")
            
            success, data, steps = await self.try_candidate(selector, name, goal, vehicle)
            
            if success and data:
                log.info(f"✓ SUCCESS via {name}!")
                
                # Record the golden thread
                record_success(goal, steps, data)
                
                # Log session success
                action_log.log_session_end(success=True, result=data, steps=self.total_steps)
                
                # Export readable summary
                mem = get_memory()
                export_path = SCREENSHOT_DIR / f"path_{goal.replace(' ', '_')[:20]}.md"
                mem.export_markdown(export_path)
                log.info(f"Exported path to {export_path}")
                
                # Return to landing page - leave browser clean for next query
                await self._return_to_landing_page()
                
                return NavigationResult(
                    success=True,
                    data=data,
                    message=f"Found in {name}",
                    steps_taken=self.total_steps,
                    history=self.history,
                )
            else:
                log.info(f"✗ Dead end at {name}")
                record_failure(goal, [selector])
                await self.backtrack_to_landing()
        
        # All exhausted
        log.warning("All candidates exhausted")
        action_log.log_session_end(success=False, steps=self.total_steps)
        return NavigationResult(
            success=False,
            data=None,
            message="Explored all likely paths without finding data",
            steps_taken=self.total_steps,
            history=self.history,
        )


async def ai_navigate(
    page: Page,
    goal: str,
    vehicle: Dict[str, str],
    api_key: Optional[str] = None,
    model: str = "gemini-2.0-flash",
    max_steps_per_path: int = 8,
) -> NavigationResult:
    """Convenience function for AI navigation."""
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return NavigationResult(
            success=False,
            message="GEMINI_API_KEY not set",
            steps_taken=0,
        )
    
    loop = NavigationLoop(
        page=page,
        api_key=api_key,
        model=model,
        max_steps_per_path=max_steps_per_path,
    )
    
    return await loop.navigate(goal=goal, vehicle=vehicle)


async def ai_navigate_with_vehicle(
    navigator,
    goal: str,
    year: str,
    make: str,
    model: str,
    engine: str,
    api_key: Optional[str] = None,
    gemini_model: str = "gemini-2.0-flash",
    max_steps_per_path: int = 8,
    llm_backend: str = "gemini",  # "gemini" or "ollama"
    ollama_model: str = "llama3.1:8b",
    ollama_host: str = "http://localhost:11434",
) -> NavigationResult:
    """
    Full AI navigation flow with guaranteed logout.
    
    Handles:
    1. Vehicle selection (deterministic)
    2. AI navigation with learning
    3. ALWAYS logs out, even on error
    
    Args:
        llm_backend: "gemini" for cloud Gemini API, "ollama" for local Ollama
        ollama_model: Which Ollama model to use (e.g. "llama3.1:8b")
        ollama_host: Ollama server URL
    """
    if llm_backend == "gemini":
        api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            return NavigationResult(
                success=False,
                message="GEMINI_API_KEY not set",
                steps_taken=0,
            )
    
    result = None
    try:
        # Select vehicle
        log.info(f"Selecting vehicle: {year} {make} {model} {engine}")
        selected = await navigator.select_vehicle(year, make, model, engine)
        
        if not selected:
            return NavigationResult(
                success=False,
                message="Failed to select vehicle",
                steps_taken=0,
            )
        
        log.info(f"Vehicle selected, starting AI navigation with {llm_backend}")
        
        # AI navigation - use appropriate backend
        if llm_backend == "ollama":
            from .ollama_navigator import OllamaNavigator
            ai_navigator = OllamaNavigator(
                model=ollama_model,
                host=ollama_host,
            )
            log.info(f"Using Ollama: {ollama_model}")
        else:
            ai_navigator = AINavigator(
                api_key=api_key,
                model=gemini_model,
            )
            log.info(f"Using Gemini: {gemini_model}")
        
        loop = NavigationLoop(
            page=navigator.page,
            api_key=api_key or "",
            model=gemini_model,
            max_steps_per_path=max_steps_per_path,
        )
        # Inject the AI navigator
        loop.ai = ai_navigator
        
        vehicle_dict = {
            "year": year,
            "make": make,
            "model": model,
            "engine": engine,
        }
        
        result = await loop.navigate(goal=goal, vehicle=vehicle_dict)
        return result
        
    except Exception as e:
        log.error(f"AI navigation error: {e}", exc_info=True)
        return NavigationResult(
            success=False,
            message=f"Error: {str(e)}",
            steps_taken=result.steps_taken if result else 0,
            history=result.history if result else [],
        )
    
    # NOTE: Caller is responsible for logout!
    # Do NOT logout here - it causes orphaned sessions when tests crash/cancel
