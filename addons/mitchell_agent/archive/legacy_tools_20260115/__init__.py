"""
Mitchell Agent Tools
=====================
High-level tools for retrieving automotive data from ShopKeyPro.

Tool Tiers:
- Tier 1: High-level tools (get_dtc_info, get_fluid_capacities, etc.)
- Tier 2: search_mitchell() - 1Search fallback
- Tier 3: browse_manual() - Service Manual tree traversal
- Tier 4: Unmapped query logging
"""

from .base import MitchellTool, ToolResult, Vehicle
from .registry import ToolRegistry, get_registry

# Tool classes
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
from .vin_plate_lookup import VINPlateLookupTool

__all__ = [
    # Base classes
    'MitchellTool',
    'ToolResult', 
    'Vehicle',
    'ToolRegistry',
    'get_registry',
    # Tier 1 tools
    'FluidCapacitiesTool',
    'DTCInfoTool',
    'TorqueSpecsTool',
    'ResetProcedureTool',
    'TSBListTool',
    'ADASCalibrationTool',
    'TireSpecsTool',
    'WiringDiagramTool',
    'SpecsProceduresTool',
    'VINPlateLookupTool',
    # Tier 2 fallback
    'SearchMitchellTool',
    # Tier 3 manual browser
    'BrowseManualTool',
]
