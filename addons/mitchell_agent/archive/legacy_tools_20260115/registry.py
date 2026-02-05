"""
Tool Registry - discovers and manages available Mitchell tools.
"""
import asyncio
from typing import Dict, List, Optional, Type, Any
from pathlib import Path
from datetime import datetime
import json

from .base import MitchellTool, ToolResult, Vehicle, TOOL_TIMEOUT_SECONDS


class ToolRegistry:
    """
    Registry of available Mitchell Agent tools.
    
    Provides tool discovery, execution, and fallback handling.
    All tool executions are wrapped with a 2-minute timeout.
    """
    
    def __init__(self):
        self._tools: Dict[str, MitchellTool] = {}
        self._browser = None
        self._unmapped_log_path: Optional[Path] = None
    
    def register(self, tool: MitchellTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
    
    def register_class(self, tool_class: Type[MitchellTool]) -> None:
        """Register a tool class (instantiates it)."""
        tool = tool_class(browser_controller=self._browser)
        self.register(tool)
    
    def set_browser(self, browser_controller) -> None:
        """Set browser controller for all registered tools."""
        self._browser = browser_controller
        for tool in self._tools.values():
            tool.browser = browser_controller
    
    def set_unmapped_log_path(self, path: Path) -> None:
        """Set path for logging unmapped queries."""
        self._unmapped_log_path = path
    
    def get_tool(self, name: str) -> Optional[MitchellTool]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all registered tools with metadata."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "tier": tool.tier
            }
            for tool in self._tools.values()
        ]
    
    def get_tools_by_tier(self, tier: int) -> List[MitchellTool]:
        """Get all tools of a specific tier."""
        return [t for t in self._tools.values() if t.tier == tier]
    
    async def execute_tool(
        self,
        tool_name: str,
        vehicle: Vehicle,
        timeout: int = TOOL_TIMEOUT_SECONDS,
        **kwargs
    ) -> ToolResult:
        """
        Execute a specific tool with timeout protection.
        
        Args:
            tool_name: Name of the tool to execute
            vehicle: Vehicle specification
            timeout: Timeout in seconds (default: 120 = 2 minutes)
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult from tool execution
        """
        tool = self.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool '{tool_name}' not found",
                source="registry"
            )
        
        try:
            # Use run_with_timeout for automatic timeout handling
            return await tool.run_with_timeout(vehicle, timeout=timeout, **kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                error=str(e),
                source=tool_name
            )
    
    async def execute_with_fallback(
        self,
        query: str,
        vehicle: Vehicle,
        preferred_tool: Optional[str] = None,
        timeout: int = TOOL_TIMEOUT_SECONDS,
        **kwargs
    ) -> ToolResult:
        """
        Execute a query with automatic tool selection and fallback.
        
        All tool executions are wrapped with a timeout (default 2 minutes).
        
        Tries tools in order:
        1. Preferred tool (if specified)
        2. Tier 1 high-level tools (if query matches)
        3. Tier 2 search fallback
        4. Logs unmapped query
        
        Args:
            query: User query string
            vehicle: Vehicle specification
            preferred_tool: Optional specific tool to try first
            timeout: Timeout in seconds (default: 120 = 2 minutes)
            **kwargs: Additional parameters
            
        Returns:
            ToolResult from successful tool or fallback
        """
        # Try preferred tool first
        if preferred_tool:
            tool = self.get_tool(preferred_tool)
            if tool:
                result = await tool.run_with_timeout(vehicle, timeout=timeout, **kwargs)
                if result.success:
                    return result
        
        # Try matching Tier 1 tools based on query
        query_lower = query.lower()
        tool_matches = self._match_query_to_tools(query_lower)
        
        for tool_name in tool_matches:
            tool = self.get_tool(tool_name)
            if tool:
                result = await tool.run_with_timeout(vehicle, timeout=timeout, query=query, **kwargs)
                if result.success:
                    return result
        
        # Fallback to Tier 2 search
        search_tool = self.get_tool("search_mitchell")
        if search_tool:
            result = await search_tool.run_with_timeout(vehicle, timeout=timeout, query=query, **kwargs)
            if result.success:
                return result
        
        # Log unmapped query
        await self._log_unmapped_query(query, vehicle, kwargs)
        
        return ToolResult(
            success=False,
            error="No tool could handle this query. It has been logged for future development.",
            source="fallback"
        )
    
    def _match_query_to_tools(self, query: str) -> List[str]:
        """Match a query string to potential tools."""
        matches = []
        
        # DTC patterns
        if any(p in query for p in ["dtc", "code", "p0", "p1", "p2", "b0", "c0", "u0"]):
            matches.append("get_dtc_info")
        
        # Fluid patterns
        if any(p in query for p in ["fluid", "oil", "coolant", "transmission fluid", "capacity", "capacities"]):
            matches.append("get_fluid_capacities")
        
        # Torque patterns
        if any(p in query for p in ["torque", "ft-lb", "nm", "tighten"]):
            matches.append("get_torque_specs")
        
        # Reset patterns
        if any(p in query for p in ["reset", "oil life", "tpms", "relearn"]):
            matches.append("get_reset_procedure")
        
        # Wiring patterns
        if any(p in query for p in ["wiring", "diagram", "schematic", "connector", "pinout"]):
            matches.append("get_wiring_diagram")
        
        # TSB patterns
        if any(p in query for p in ["tsb", "bulletin", "recall", "campaign"]):
            matches.append("get_tsb_list")
        
        # ADAS patterns
        if any(p in query for p in ["adas", "calibration", "calibrate", "camera", "sensor"]):
            matches.append("get_adas_calibration")
        
        # Location patterns
        if any(p in query for p in ["location", "where", "locate", "find"]):
            matches.append("get_component_location")
        
        # Tire patterns
        if any(p in query for p in ["tire", "tyre", "pressure", "size", "fitment"]):
            matches.append("get_tire_specs")
        
        return matches
    
    async def _log_unmapped_query(
        self,
        query: str,
        vehicle: Vehicle,
        params: Dict[str, Any]
    ) -> None:
        """Log an unmapped query for future development."""
        if not self._unmapped_log_path:
            return
        
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "vehicle": str(vehicle),
            "vehicle_data": vehicle.to_selector_format(),
            "params": {k: str(v) for k, v in params.items()},
            "matched_tools": self._match_query_to_tools(query.lower())
        }
        
        try:
            # Append to log file
            self._unmapped_log_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self._unmapped_log_path, "a") as f:
                f.write(json.dumps(log_entry) + "\n")
            
            print(f"Logged unmapped query: {query}")
        except Exception as e:
            print(f"Error logging unmapped query: {e}")


# Global registry instance
_registry: Optional[ToolRegistry] = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _register_default_tools(_registry)
    return _registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """Register all default tools."""
    # Import tools here to avoid circular imports
    from .fluids import FluidCapacitiesTool
    from .dtc import DTCInfoTool
    from .search import SearchMitchellTool
    from .torque import TorqueSpecsTool
    from .reset import ResetProcedureTool
    from .tsb import TSBListTool
    from .adas import ADASCalibrationTool
    from .tire import TireSpecsTool
    from .manual import BrowseManualTool
    from .wiring import WiringDiagramTool
    from .specs_procedures import SpecsProceduresTool
    from .component_location import ComponentLocationTool
    from .component_tests import ComponentTestsTool
    from .vin_plate_lookup import VINPlateLookupTool
    
    registry.register_class(FluidCapacitiesTool)
    registry.register_class(DTCInfoTool)
    registry.register_class(SearchMitchellTool)
    registry.register_class(TorqueSpecsTool)
    registry.register_class(ResetProcedureTool)
    registry.register_class(TSBListTool)
    registry.register_class(ADASCalibrationTool)
    registry.register_class(TireSpecsTool)
    registry.register_class(BrowseManualTool)
    registry.register_class(WiringDiagramTool)
    registry.register_class(SpecsProceduresTool)
    registry.register_class(ComponentLocationTool)
    registry.register_class(ComponentTestsTool)
    registry.register_class(VINPlateLookupTool)
