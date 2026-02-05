"""
ELM327 Live Diagnostics Integration

AI-directed OBD-II diagnostics with live data monitoring and bidirectional control.

Architecture:
    Open WebUI → Diagnostic Tool → ELM327 Service → Adapter → Vehicle

Capabilities:
    - Tier 1: Standard OBD-II (all vehicles 1996+) - DTCs, PIDs, VIN
    - Tier 2: Enhanced OBD-II - Actuator tests, vehicle info  
    - Tier 3: Manufacturer-specific - Full bidirectional, extended PIDs

Usage:
    from addons.scan_tool import ELM327Service
    
    async with ELM327Service() as elm:
        await elm.connect('bluetooth', '/dev/rfcomm0')
        dtcs = await elm.read_dtcs()
        pids = await elm.read_pids(['RPM', 'COOLANT_TEMP', 'STFT_B1'])
"""

from .service import ELM327Service
from .connection import ELM327Connection, ConnectionType
from .protocol import OBDProtocol
from .pids import PIDRegistry, decode_pid
from .bidirectional import ActuatorControl

__all__ = [
    'ELM327Service',
    'ELM327Connection', 
    'ConnectionType',
    'OBDProtocol',
    'PIDRegistry',
    'decode_pid',
    'ActuatorControl',
]

__version__ = '0.1.0'
