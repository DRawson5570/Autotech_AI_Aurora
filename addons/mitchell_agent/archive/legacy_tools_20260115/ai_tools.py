"""
AI-Driven Tools Module
=======================

AI-powered tools that use intelligent navigation instead of hardcoded paths.
These tools work alongside the original tools - user can choose which to use.

All AI tools follow the pattern:
1. Deterministic vehicle selection (Python, works well)
2. AI-driven exploration after vehicle is selected
3. AI data extraction and formatting
"""
import asyncio
import os
from typing import Dict, Optional, Any

from .base import MitchellTool, ToolResult, Vehicle


async def _run_ai_navigation(
    browser,
    vehicle: Vehicle,
    goal: str,
    tool_name: str,
    api_key: Optional[str] = None,
    max_steps: int = 15,
    debug_screenshots: bool = False,
    auto_selected_options: Optional[Dict[str, str]] = None,
) -> ToolResult:
    """
    Common AI navigation runner for all AI tools.
    
    Args:
        browser: Browser controller with _page attribute
        vehicle: Vehicle specification (already selected)
        goal: What to find (detailed description for AI)
        tool_name: Name of the calling tool (for logging)
        api_key: Gemini API key
        max_steps: Max navigation steps
        debug_screenshots: Save screenshots for debugging
        auto_selected_options: Any auto-selected vehicle options to include in result
        
    Returns:
        ToolResult
    """
    from ..ai_navigator import NavigationLoop
    
    api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return ToolResult(
            success=False,
            error="GEMINI_API_KEY not configured",
            source=tool_name
        )
    
    try:
        page = browser._page
        
        nav_loop = NavigationLoop(
            page=page,
            api_key=api_key,
            max_steps=max_steps,
            save_screenshots=debug_screenshots,
        )
        
        vehicle_dict = {
            "year": str(vehicle.year),
            "make": vehicle.make,
            "model": vehicle.model,
            "engine": vehicle.engine,
        }
        
        print(f"[{tool_name}] Starting AI navigation: {goal[:80]}...")
        
        result = await nav_loop.navigate(goal=goal, vehicle=vehicle_dict)
        
        if result.success and result.data:
            return ToolResult(
                success=True,
                data=result.data,
                source=tool_name,
                auto_selected_options=auto_selected_options,
            )
        else:
            return ToolResult(
                success=False,
                error=result.message or "AI navigation failed",
                source=tool_name,
                data=result.data,  # Partial data
            )
            
    except Exception as e:
        return ToolResult(
            success=False,
            error=str(e),
            source=tool_name
        )


class FluidCapacitiesAITool(MitchellTool):
    """AI-driven fluid capacities retrieval."""
    
    name = "get_fluid_capacities_ai"
    description = "Get fluid capacities using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        fluid_type: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        # Vehicle selection
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        goal = "Find fluid capacities and specifications (oil capacity, coolant capacity, transmission fluid, differential fluid)"
        if fluid_type:
            goal += f", specifically {fluid_type}"
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 15),
            debug_screenshots=kwargs.get('debug_screenshots', False),
            auto_selected_options=self._auto_selected_options or None,
        )


class TorqueSpecsAITool(MitchellTool):
    """AI-driven torque specifications retrieval."""
    
    name = "get_torque_specs_ai"
    description = "Get torque specifications using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        component: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        # Vehicle selection
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        goal = "Find torque specifications"
        if component:
            goal += f" for {component}"
        goal += ". Look for fastener torque values, tightening sequences, and bolt specs."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 15),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class DTCInfoAITool(MitchellTool):
    """AI-driven DTC (Diagnostic Trouble Code) information retrieval."""
    
    name = "get_dtc_info_ai"
    description = "Get DTC code information using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        dtc_code: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        if dtc_code:
            goal = f"Find information about DTC code {dtc_code}. Look for code description, possible causes, diagnostic procedures, and repair information."
        else:
            goal = "Find the DTC (Diagnostic Trouble Code) index or code list for this vehicle."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 18),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class TSBListAITool(MitchellTool):
    """AI-driven Technical Service Bulletin retrieval."""
    
    name = "get_tsb_list_ai"
    description = "Get Technical Service Bulletins using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        category: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        goal = "Find Technical Service Bulletins (TSBs)"
        if category:
            goal += f" related to {category}"
        goal += ". List the TSB numbers, titles, and publication dates."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 15),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class ResetProcedureAITool(MitchellTool):
    """AI-driven reset procedure retrieval."""
    
    name = "get_reset_procedure_ai"
    description = "Get reset procedures using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        reset_type: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        if reset_type:
            goal = f"Find the {reset_type} reset procedure"
        else:
            goal = "Find reset procedures (oil life reset, TPMS reset, maintenance reset)"
        goal += " with step-by-step instructions."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 15),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class WiringDiagramAITool(MitchellTool):
    """AI-driven wiring diagram retrieval."""
    
    name = "get_wiring_diagram_ai"
    description = "Get wiring diagrams using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        system: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        if system:
            goal = f"Find wiring diagrams for the {system} system"
        else:
            goal = "Find the wiring diagrams section and list available system diagrams"
        goal += ". Navigate to the diagrams and extract the circuit information."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 40),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class TireSpecsAITool(MitchellTool):
    """AI-driven tire specifications retrieval."""
    
    name = "get_tire_specs_ai"
    description = "Get tire specs and TPMS info using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        goal = "Find tire specifications, tire pressure (PSI), tire sizes, TPMS sensor information, and wheel specifications."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 15),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class ADASCalibrationAITool(MitchellTool):
    """AI-driven ADAS calibration requirements retrieval."""
    
    name = "get_adas_calibration_ai"
    description = "Get ADAS calibration requirements using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        system: Optional[str] = None,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        goal = "Find ADAS (Advanced Driver Assistance Systems) calibration requirements"
        if system:
            goal += f" for the {system}"
        goal += ". Include calibration procedures, required equipment, and precautions."
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 18),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


class GeneralQueryAITool(MitchellTool):
    """
    AI-driven general query tool.
    
    This is the most flexible tool - handles any automotive query
    by letting the AI navigate to find the answer.
    """
    
    name = "query_mitchell_ai"
    description = "Ask any automotive question using AI navigation"
    tier = 1
    
    async def execute(
        self,
        vehicle: Vehicle,
        query: str,
        **kwargs
    ) -> ToolResult:
        if not self.browser:
            return ToolResult(success=False, error="No browser", source=self.name)
        
        if not query:
            return ToolResult(success=False, error="No query provided", source=self.name)
        
        if not kwargs.get('skip_vehicle_selection'):
            if not await self.ensure_vehicle_selected(vehicle):
                return ToolResult(success=False, error="Vehicle selection failed", source=self.name)
        
        # Use the query directly as the goal
        goal = query
        
        return await _run_ai_navigation(
            self.browser, vehicle, goal, self.name,
            api_key=kwargs.get('gemini_api_key'),
            max_steps=kwargs.get('max_steps', 40),
            debug_screenshots=kwargs.get('debug_screenshots', False),
        )


# Registry of AI tools
AI_TOOLS = {
    "fluids": FluidCapacitiesAITool,
    "torque": TorqueSpecsAITool,
    "dtc": DTCInfoAITool,
    "tsb": TSBListAITool,
    "reset": ResetProcedureAITool,
    "wiring": WiringDiagramAITool,
    "tire": TireSpecsAITool,
    "adas": ADASCalibrationAITool,
    "query": GeneralQueryAITool,
}


def get_ai_tool(tool_type: str, browser) -> Optional[MitchellTool]:
    """
    Get an AI tool by type.
    
    Args:
        tool_type: One of: fluids, torque, dtc, tsb, reset, wiring, tire, adas, query
        browser: Browser controller
        
    Returns:
        Initialized tool or None
    """
    tool_class = AI_TOOLS.get(tool_type.lower())
    if tool_class:
        return tool_class(browser_controller=browser)
    return None
