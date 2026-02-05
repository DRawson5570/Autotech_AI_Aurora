"""
ELM327 Protocol Handler

Handles communication with ELM327-compatible OBD2 adapters.
Supports both serial (USB) and Bluetooth connections.
"""

import asyncio
import logging
import re
from typing import Optional, List, Dict, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("elm327")


class OBDProtocol(Enum):
    """OBD2 protocols supported by ELM327."""
    AUTO = 0
    SAE_J1850_PWM = 1
    SAE_J1850_VPW = 2
    ISO_9141_2 = 3
    ISO_14230_4_KWP_5BAUD = 4
    ISO_14230_4_KWP_FAST = 5
    ISO_15765_4_CAN_11BIT_500K = 6
    ISO_15765_4_CAN_29BIT_500K = 7
    ISO_15765_4_CAN_11BIT_250K = 8
    ISO_15765_4_CAN_29BIT_250K = 9
    SAE_J1939_CAN = 10


@dataclass
class DTCInfo:
    """Diagnostic Trouble Code information."""
    code: str
    status: str  # "current", "pending", "permanent"
    description: str = ""


@dataclass
class FreezeFrameData:
    """Freeze frame data captured when DTC was set."""
    dtc: str
    data: Dict[str, float] = field(default_factory=dict)


@dataclass
class ELM327Response:
    """Response from ELM327."""
    success: bool
    data: List[int] = field(default_factory=list)
    raw: str = ""
    error: str = ""


class ELM327:
    """
    ELM327 OBD2 adapter interface.
    
    This class handles the low-level communication with ELM327 adapters.
    It can be used with different transport layers (serial, bluetooth, websocket).
    """
    
    def __init__(self):
        self.connected = False
        self.protocol: Optional[OBDProtocol] = None
        self.vin: Optional[str] = None
        self._send_func: Optional[Callable[[str], asyncio.Future]] = None
        self._receive_func: Optional[Callable[[], asyncio.Future]] = None
        self._supported_pids: set = set()
    
    def set_transport(
        self, 
        send_func: Callable[[str], asyncio.Future],
        receive_func: Callable[[], asyncio.Future]
    ):
        """Set the transport functions for sending/receiving data."""
        self._send_func = send_func
        self._receive_func = receive_func
    
    async def _send_command(self, command: str, timeout: float = 5.0) -> ELM327Response:
        """Send a command and wait for response."""
        if not self._send_func or not self._receive_func:
            return ELM327Response(success=False, error="Transport not configured")
        
        try:
            # Send command with carriage return
            await self._send_func(command + "\r")
            
            # Read response (wait for prompt '>')
            response = ""
            start_time = asyncio.get_event_loop().time()
            
            while True:
                if asyncio.get_event_loop().time() - start_time > timeout:
                    return ELM327Response(success=False, error="Timeout", raw=response)
                
                chunk = await asyncio.wait_for(self._receive_func(), timeout=1.0)
                response += chunk
                
                if ">" in response:
                    break
            
            # Parse response
            return self._parse_response(response)
            
        except asyncio.TimeoutError:
            return ELM327Response(success=False, error="Timeout")
        except Exception as e:
            return ELM327Response(success=False, error=str(e))
    
    def _parse_response(self, response: str) -> ELM327Response:
        """Parse ELM327 response into data bytes."""
        # Clean up response
        response = response.replace("\r", "").replace("\n", " ").replace(">", "").strip()
        
        # Check for errors
        error_patterns = [
            "NO DATA",
            "UNABLE TO CONNECT", 
            "BUS INIT",
            "CAN ERROR",
            "ERROR",
            "?",
        ]
        
        for pattern in error_patterns:
            if pattern in response.upper():
                return ELM327Response(success=False, error=response, raw=response)
        
        # Extract hex bytes
        hex_pattern = re.compile(r'[0-9A-Fa-f]{2}')
        hex_bytes = hex_pattern.findall(response)
        
        if not hex_bytes:
            return ELM327Response(success=True, data=[], raw=response)
        
        # Convert to integers
        data = [int(b, 16) for b in hex_bytes]
        
        return ELM327Response(success=True, data=data, raw=response)
    
    async def initialize(self) -> bool:
        """Initialize ELM327 adapter."""
        logger.info("Initializing ELM327...")
        
        # Reset adapter
        resp = await self._send_command("ATZ", timeout=3.0)
        if not resp.success:
            logger.error(f"Reset failed: {resp.error}")
            return False
        
        await asyncio.sleep(1.0)  # Wait for reset
        
        # Turn off echo
        resp = await self._send_command("ATE0")
        if not resp.success:
            logger.error(f"Echo off failed: {resp.error}")
            return False
        
        # Turn off line feeds
        await self._send_command("ATL0")
        
        # Turn off headers (we just want data)
        await self._send_command("ATH0")
        
        # Set timeout (default ~200ms per response)
        await self._send_command("ATST32")
        
        # Auto-detect protocol
        resp = await self._send_command("ATSP0")
        if not resp.success:
            logger.warning(f"Protocol auto-detect failed: {resp.error}")
        
        # Try to connect by reading PIDs supported
        resp = await self._send_command("0100", timeout=10.0)
        if not resp.success:
            logger.error(f"Failed to connect to vehicle: {resp.error}")
            return False
        
        self.connected = True
        logger.info("ELM327 initialized successfully")
        
        # Get supported PIDs
        await self._get_supported_pids()
        
        return True
    
    async def _get_supported_pids(self):
        """Query which PIDs are supported."""
        self._supported_pids = set()
        
        # PID 0x00 returns bitmap of PIDs 01-20
        resp = await self._send_command("0100")
        if resp.success and len(resp.data) >= 6:
            # Skip mode and pid bytes (41 00), get bitmap
            bitmap = (resp.data[2] << 24) | (resp.data[3] << 16) | (resp.data[4] << 8) | resp.data[5]
            for i in range(32):
                if bitmap & (1 << (31 - i)):
                    self._supported_pids.add(i + 1)
            
            # If PID 0x20 is supported, query next range
            if 0x20 in self._supported_pids:
                resp = await self._send_command("0120")
                if resp.success and len(resp.data) >= 6:
                    bitmap = (resp.data[2] << 24) | (resp.data[3] << 16) | (resp.data[4] << 8) | resp.data[5]
                    for i in range(32):
                        if bitmap & (1 << (31 - i)):
                            self._supported_pids.add(0x20 + i + 1)
        
        logger.info(f"Supported PIDs: {sorted(self._supported_pids)}")
    
    def is_pid_supported(self, pid: int) -> bool:
        """Check if a PID is supported by this vehicle."""
        return pid in self._supported_pids
    
    async def read_pid(self, pid: int) -> Optional[List[int]]:
        """Read a single PID value."""
        if not self.connected:
            return None
        
        command = f"01{pid:02X}"
        resp = await self._send_command(command)
        
        if not resp.success:
            logger.debug(f"PID {pid:02X} read failed: {resp.error}")
            return None
        
        # Response format: 41 XX YY [ZZ...]
        # 41 = mode 01 response, XX = PID, YY+ = data
        if len(resp.data) >= 3 and resp.data[0] == 0x41 and resp.data[1] == pid:
            return resp.data[2:]
        
        return None
    
    async def read_multiple_pids(self, pids: List[int]) -> Dict[int, List[int]]:
        """Read multiple PIDs."""
        results = {}
        
        for pid in pids:
            if self.is_pid_supported(pid):
                data = await self.read_pid(pid)
                if data is not None:
                    results[pid] = data
        
        return results
    
    async def read_dtcs(self) -> List[DTCInfo]:
        """Read current Diagnostic Trouble Codes (Mode 03)."""
        dtcs = []
        
        # Mode 03 - Current DTCs
        resp = await self._send_command("03")
        if resp.success:
            dtcs.extend(self._parse_dtcs(resp.data, "current"))
        
        # Mode 07 - Pending DTCs
        resp = await self._send_command("07")
        if resp.success:
            dtcs.extend(self._parse_dtcs(resp.data, "pending"))
        
        # Mode 0A - Permanent DTCs (if supported)
        resp = await self._send_command("0A")
        if resp.success:
            dtcs.extend(self._parse_dtcs(resp.data, "permanent"))
        
        return dtcs
    
    def _parse_dtcs(self, data: List[int], status: str) -> List[DTCInfo]:
        """Parse DTC data into codes."""
        dtcs = []
        
        if len(data) < 2:
            return dtcs
        
        # Skip first byte (number of DTCs or mode response)
        i = 1 if data[0] in [0x43, 0x47, 0x4A] else 0
        
        while i + 1 < len(data):
            byte1 = data[i]
            byte2 = data[i + 1]
            
            if byte1 == 0 and byte2 == 0:
                i += 2
                continue
            
            # Decode DTC
            # First 2 bits = category (P, C, B, U)
            # Next 2 bits = first digit
            # Remaining 12 bits = other digits
            category = ["P", "C", "B", "U"][(byte1 >> 6) & 0x03]
            digit1 = (byte1 >> 4) & 0x03
            digit2 = byte1 & 0x0F
            digit3 = (byte2 >> 4) & 0x0F
            digit4 = byte2 & 0x0F
            
            code = f"{category}{digit1}{digit2:X}{digit3:X}{digit4:X}"
            dtcs.append(DTCInfo(code=code, status=status))
            
            i += 2
        
        return dtcs
    
    async def clear_dtcs(self) -> bool:
        """Clear Diagnostic Trouble Codes (Mode 04)."""
        resp = await self._send_command("04")
        return resp.success
    
    async def read_freeze_frame(self, frame: int = 0) -> Optional[FreezeFrameData]:
        """Read freeze frame data (Mode 02)."""
        # Read common freeze frame PIDs
        freeze_pids = [0x02, 0x04, 0x05, 0x06, 0x07, 0x0C, 0x0D, 0x0E, 0x11]
        
        data = {}
        dtc = None
        
        for pid in freeze_pids:
            command = f"02{pid:02X}{frame:02X}"
            resp = await self._send_command(command)
            
            if resp.success and len(resp.data) >= 3:
                if pid == 0x02:
                    # This is the DTC that caused the freeze frame
                    dtc_data = resp.data[2:4] if len(resp.data) >= 4 else [0, 0]
                    # Parse DTC (simplified)
                    dtc = f"P{dtc_data[0]:02X}{dtc_data[1]:02X}"
                else:
                    from . import obd2_pids
                    value = obd2_pids.decode_pid(pid, resp.data[2:])
                    if value is not None:
                        data[obd2_pids.get_pid_name(pid)] = value
        
        if data:
            return FreezeFrameData(dtc=dtc or "Unknown", data=data)
        return None
    
    async def read_vin(self) -> Optional[str]:
        """Read Vehicle Identification Number (Mode 09, PID 02)."""
        resp = await self._send_command("0902")
        
        if not resp.success:
            return None
        
        # VIN is returned as ASCII characters
        # Skip header bytes and extract VIN
        try:
            # Different formats depending on protocol
            # Try to extract 17 ASCII characters
            vin_bytes = [b for b in resp.data if 0x20 <= b <= 0x7E]
            if len(vin_bytes) >= 17:
                self.vin = "".join(chr(b) for b in vin_bytes[:17])
                return self.vin
        except Exception:
            pass
        
        return None
    
    async def get_protocol(self) -> Optional[str]:
        """Get the detected OBD protocol."""
        resp = await self._send_command("ATDP")
        if resp.success:
            return resp.raw
        return None


# Diagnostic analysis helpers

def analyze_fuel_trims(stft1: float, ltft1: float, stft2: float = None, ltft2: float = None) -> Dict:
    """
    Analyze fuel trim data for diagnostic insights.
    
    Returns analysis with probable causes.
    """
    analysis = {
        "status": "normal",
        "bank1_total": stft1 + ltft1,
        "bank2_total": (stft2 + ltft2) if stft2 is not None and ltft2 is not None else None,
        "issues": [],
        "likely_causes": [],
    }
    
    b1_total = analysis["bank1_total"]
    b2_total = analysis["bank2_total"]
    
    # Check Bank 1
    if abs(b1_total) > 25:
        analysis["status"] = "critical"
        analysis["issues"].append(f"Bank 1 fuel trim critical: {b1_total:+.1f}%")
    elif abs(b1_total) > 10:
        analysis["status"] = "warning"
        analysis["issues"].append(f"Bank 1 fuel trim elevated: {b1_total:+.1f}%")
    
    # Check Bank 2 if present
    if b2_total is not None:
        if abs(b2_total) > 25:
            analysis["status"] = "critical"
            analysis["issues"].append(f"Bank 2 fuel trim critical: {b2_total:+.1f}%")
        elif abs(b2_total) > 10:
            if analysis["status"] != "critical":
                analysis["status"] = "warning"
            analysis["issues"].append(f"Bank 2 fuel trim elevated: {b2_total:+.1f}%")
    
    # Determine likely causes
    if b1_total > 10:
        if b2_total is None or b2_total > 10:
            # Both banks lean or single bank vehicle
            analysis["likely_causes"].extend([
                "Vacuum leak (intake manifold, hoses)",
                "Weak fuel pump",
                "Clogged fuel filter",
                "Dirty/failing MAF sensor",
            ])
        else:
            # Only Bank 1 lean
            analysis["likely_causes"].extend([
                "Vacuum leak - Bank 1 side only",
                "Injector issue - Bank 1",
                "Intake manifold gasket - Bank 1 side",
            ])
    elif b1_total < -10:
        if b2_total is None or b2_total < -10:
            # Both banks rich
            analysis["likely_causes"].extend([
                "Leaking fuel injector(s)",
                "High fuel pressure",
                "Faulty O2 sensor reporting lean",
                "EVAP purge valve stuck open",
            ])
        else:
            # Only Bank 1 rich
            analysis["likely_causes"].extend([
                "Leaking injector - Bank 1",
                "Faulty O2 sensor - Bank 1",
            ])
    
    # Check for bank imbalance (V6/V8)
    if b2_total is not None:
        bank_diff = abs(b1_total - b2_total)
        if bank_diff > 10:
            analysis["issues"].append(f"Bank imbalance detected: {bank_diff:.1f}% difference")
            if b1_total > b2_total:
                analysis["likely_causes"].append("Issue isolated to Bank 1 side")
            else:
                analysis["likely_causes"].append("Issue isolated to Bank 2 side")
    
    return analysis
