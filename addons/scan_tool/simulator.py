"""
ELM327 Simulator

Simulates an ELM327 adapter for testing without real hardware.

Features:
- Responds to all AT commands
- Generates realistic PID values
- Simulates configurable vehicle states (normal, overheating, lean, etc.)
- Can inject DTCs based on vehicle state
- Supports TCP server mode for network testing

Usage:
    # As a mock connection
    from addons.scan_tool.simulator import SimulatedELM327
    
    sim = SimulatedELM327(vehicle_state='overheating')
    response = await sim.send_command('0105')  # Coolant temp
    
    # As a TCP server (for testing real connection code)
    python -m addons.scan_tool.simulator --port 35000 --state overheating
"""

import asyncio
import logging
import random
import struct
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger(__name__)


class VehicleState(Enum):
    """Predefined vehicle states for simulation."""
    NORMAL = "normal"
    OVERHEATING = "overheating"           # Stuck thermostat
    RUNNING_COLD = "running_cold"         # Thermostat stuck open
    LEAN_BOTH_BANKS = "lean_both_banks"   # Vacuum leak
    LEAN_BANK1 = "lean_bank1"             # Bank 1 specific
    RICH_BOTH_BANKS = "rich_both_banks"   # Over-fueling
    MISFIRE_CYL3 = "misfire_cyl3"         # Cylinder 3 misfire
    RANDOM_MISFIRE = "random_misfire"     # Multiple cylinder
    CAT_DEGRADED = "cat_degraded"         # P0420 condition
    O2_SENSOR_LAZY = "o2_sensor_lazy"     # Slow O2 response
    MAF_DIRTY = "maf_dirty"               # Contaminated MAF


@dataclass
class VehicleProfile:
    """Simulated vehicle characteristics."""
    vin: str = "1HGCM82633A004352"  # Example Honda VIN
    year: int = 2015
    make: str = "Honda"
    model: str = "Accord"
    engine: str = "2.4L I4"
    
    # Base operating parameters
    idle_rpm: int = 750
    coolant_temp_normal: float = 195.0  # °F
    ambient_temp: float = 72.0  # °F
    
    # Fuel trim baselines
    stft_b1_base: float = 0.0
    ltft_b1_base: float = 2.0
    stft_b2_base: float = 0.0
    ltft_b2_base: float = 1.5


@dataclass
class SimulatedState:
    """Current simulated vehicle state."""
    engine_running: bool = True
    rpm: float = 750.0
    speed_mph: float = 0.0
    coolant_temp_f: float = 195.0
    intake_temp_f: float = 85.0
    throttle_pos: float = 15.0
    engine_load: float = 20.0
    
    # Fuel trims (%)
    stft_b1: float = 0.0
    ltft_b1: float = 2.0
    stft_b2: float = 0.0
    ltft_b2: float = 1.5
    
    # MAF (g/s)
    maf: float = 4.5
    
    # MAP (kPa)
    map_kpa: float = 35.0
    
    # O2 sensors (V)
    o2_b1s1: float = 0.45
    o2_b1s2: float = 0.65
    o2_b2s1: float = 0.45
    o2_b2s2: float = 0.65
    
    # Timing
    timing_advance: float = 12.0
    
    # Battery
    voltage: float = 14.2
    
    # Timestamps for dynamic simulation
    start_time: float = field(default_factory=time.time)
    
    # Active DTCs
    stored_dtcs: List[str] = field(default_factory=list)
    pending_dtcs: List[str] = field(default_factory=list)


class SimulatedELM327:
    """
    Simulated ELM327 adapter.
    
    Responds to AT and OBD commands with realistic data based on
    the configured vehicle state.
    """
    
    def __init__(
        self,
        vehicle_state: str = "normal",
        profile: VehicleProfile = None,
        noise_level: float = 0.05,  # 5% random variation
    ):
        """
        Initialize simulator.
        
        Args:
            vehicle_state: One of VehicleState values or 'normal'
            profile: Vehicle characteristics
            noise_level: Random variation (0-1)
        """
        self.profile = profile or VehicleProfile()
        self.noise_level = noise_level
        self.state = SimulatedState()
        self._echo_enabled = True
        self._spaces_enabled = True
        self._linefeeds_enabled = True
        
        # Set up state
        self._set_vehicle_state(vehicle_state)
        
        # PID handlers: pid_number -> handler function
        self._pid_handlers: Dict[int, Callable[[], bytes]] = {
            0x00: self._pid_00_supported,
            0x01: self._pid_01_monitor_status,
            0x04: self._pid_04_engine_load,
            0x05: self._pid_05_coolant_temp,
            0x06: self._pid_06_stft_b1,
            0x07: self._pid_07_ltft_b1,
            0x08: self._pid_08_stft_b2,
            0x09: self._pid_09_ltft_b2,
            0x0C: self._pid_0c_rpm,
            0x0D: self._pid_0d_speed,
            0x0E: self._pid_0e_timing,
            0x0F: self._pid_0f_intake_temp,
            0x10: self._pid_10_maf,
            0x11: self._pid_11_throttle,
            0x14: self._pid_14_o2_b1s1,
            0x15: self._pid_15_o2_b1s2,
            0x18: self._pid_18_o2_b2s1,
            0x19: self._pid_19_o2_b2s2,
            0x1C: self._pid_1c_obd_standard,
            0x1F: self._pid_1f_runtime,
            0x20: self._pid_20_supported,
            0x21: self._pid_21_distance_mil,
            0x2F: self._pid_2f_fuel_level,
            0x33: self._pid_33_baro,
            0x42: self._pid_42_voltage,
            0x46: self._pid_46_ambient_temp,
        }
        
        logger.info(f"Simulator initialized: state={vehicle_state}, vehicle={self.profile.year} {self.profile.make} {self.profile.model}")
    
    def _set_vehicle_state(self, state_name: str) -> None:
        """Configure simulation for a specific vehicle state."""
        state_name = state_name.lower()
        
        # Reset to normal first
        self.state = SimulatedState()
        self.state.stored_dtcs = []
        self.state.pending_dtcs = []
        
        if state_name == "normal":
            pass  # Default values are normal
            
        elif state_name == "overheating":
            self.state.coolant_temp_f = 245.0
            self.state.stored_dtcs = ["P0217"]
            self.state.pending_dtcs = []
            # Engine retards timing when hot
            self.state.timing_advance = 5.0
            
        elif state_name == "running_cold":
            self.state.coolant_temp_f = 140.0
            self.state.stored_dtcs = ["P0128"]
            # Rich mixture due to cold enrichment
            self.state.stft_b1 = -5.0
            self.state.stft_b2 = -4.5
            
        elif state_name == "lean_both_banks":
            self.state.stft_b1 = 12.0
            self.state.ltft_b1 = 18.0
            self.state.stft_b2 = 10.0
            self.state.ltft_b2 = 16.0
            self.state.stored_dtcs = ["P0171", "P0174"]
            
        elif state_name == "lean_bank1":
            self.state.stft_b1 = 15.0
            self.state.ltft_b1 = 20.0
            self.state.stored_dtcs = ["P0171"]
            
        elif state_name == "rich_both_banks":
            self.state.stft_b1 = -10.0
            self.state.ltft_b1 = -15.0
            self.state.stft_b2 = -8.0
            self.state.ltft_b2 = -12.0
            self.state.stored_dtcs = ["P0172", "P0175"]
            
        elif state_name == "misfire_cyl3":
            self.state.stored_dtcs = ["P0303"]
            self.state.pending_dtcs = ["P0300"]
            # Slightly lean on affected bank
            self.state.stft_b1 = 5.0
            
        elif state_name == "random_misfire":
            self.state.stored_dtcs = ["P0300"]
            self.state.pending_dtcs = ["P0301", "P0302", "P0304"]
            self.state.stft_b1 = 8.0
            self.state.stft_b2 = 7.0
            
        elif state_name == "cat_degraded":
            self.state.stored_dtcs = ["P0420"]
            # Downstream O2 mimics upstream
            self.state.o2_b1s2 = 0.45  # Should be steady ~0.6-0.7V
            
        elif state_name == "o2_sensor_lazy":
            self.state.stored_dtcs = ["P0133"]
            self.state.stft_b1 = 6.0
            self.state.ltft_b1 = 5.0
            
        elif state_name == "maf_dirty":
            self.state.maf = 3.5  # Reading low
            self.state.ltft_b1 = 15.0
            self.state.ltft_b2 = 12.0
            self.state.stored_dtcs = ["P0171", "P0174"]
            self.state.pending_dtcs = ["P0101"]
        
        logger.debug(f"Vehicle state set to: {state_name}, DTCs: {self.state.stored_dtcs}")
    
    def _add_noise(self, value: float, magnitude: float = None) -> float:
        """Add random noise to a value."""
        mag = magnitude if magnitude is not None else self.noise_level
        noise = random.gauss(0, value * mag)
        return value + noise
    
    async def send_command(self, command: str, timeout: float = 5.0) -> str:
        """
        Process a command and return response.
        
        Args:
            command: AT or OBD command
            timeout: Not used in simulator
            
        Returns:
            Response string
        """
        command = command.strip().upper()
        
        # AT commands
        if command.startswith("AT"):
            return self._handle_at_command(command)
        
        # OBD commands (hex digits)
        if all(c in '0123456789ABCDEF' for c in command):
            return self._handle_obd_command(command)
        
        return "?"
    
    def _handle_at_command(self, command: str) -> str:
        """Handle AT commands."""
        cmd = command[2:] if command.startswith("AT") else command
        
        if cmd == "Z":
            # Reset
            return "ELM327 v2.1 (Simulated)"
        
        elif cmd == "E0":
            self._echo_enabled = False
            return "OK"
        
        elif cmd == "E1":
            self._echo_enabled = True
            return "OK"
        
        elif cmd == "L0":
            self._linefeeds_enabled = False
            return "OK"
        
        elif cmd == "L1":
            self._linefeeds_enabled = True
            return "OK"
        
        elif cmd == "S0":
            self._spaces_enabled = False
            return "OK"
        
        elif cmd == "S1":
            self._spaces_enabled = True
            return "OK"
        
        elif cmd == "SP0" or cmd.startswith("SP"):
            # Set/auto protocol
            return "OK"
        
        elif cmd == "DPN":
            # Describe protocol number
            return "6"  # ISO 15765-4 CAN
        
        elif cmd == "DP":
            # Describe protocol
            return "ISO 15765-4 (CAN 11/500)"
        
        elif cmd == "RV":
            # Read voltage
            return f"{self.state.voltage:.1f}V"
        
        elif cmd == "I":
            # Identity
            return "ELM327 v2.1 (Simulated)"
        
        elif cmd == "@1":
            # Device description
            return "ELM327 Simulator for Autotech AI"
        
        elif cmd == "H0" or cmd == "H1":
            # Headers off/on
            return "OK"
        
        elif cmd == "CAF0" or cmd == "CAF1":
            # CAN auto formatting
            return "OK"
        
        return "OK"
    
    def _handle_obd_command(self, command: str) -> str:
        """Handle OBD-II commands."""
        if len(command) < 2:
            return "?"
        
        mode = int(command[0:2], 16)
        pid = int(command[2:4], 16) if len(command) >= 4 else 0
        
        # Mode 01: Current data
        if mode == 0x01:
            return self._handle_mode_01(pid)
        
        # Mode 03: Stored DTCs
        elif mode == 0x03:
            return self._format_dtcs(self.state.stored_dtcs, 0x43)
        
        # Mode 04: Clear DTCs
        elif mode == 0x04:
            self.state.stored_dtcs = []
            self.state.pending_dtcs = []
            return "44"
        
        # Mode 07: Pending DTCs
        elif mode == 0x07:
            return self._format_dtcs(self.state.pending_dtcs, 0x47)
        
        # Mode 09: Vehicle info
        elif mode == 0x09:
            return self._handle_mode_09(pid)
        
        # Mode 0A: Permanent DTCs
        elif mode == 0x0A:
            return self._format_dtcs([], 0x4A)  # None for simulation
        
        return "NO DATA"
    
    def _handle_mode_01(self, pid: int) -> str:
        """Handle Mode 01 (current data) requests."""
        handler = self._pid_handlers.get(pid)
        
        if handler:
            data = handler()
            # Format: 41 PP DD DD...
            response_bytes = [0x41, pid] + list(data)
            if self._spaces_enabled:
                return ' '.join(f'{b:02X}' for b in response_bytes)
            else:
                return ''.join(f'{b:02X}' for b in response_bytes)
        
        return "NO DATA"
    
    def _handle_mode_09(self, pid: int) -> str:
        """Handle Mode 09 (vehicle info) requests."""
        if pid == 0x02:
            # VIN
            vin_bytes = self.profile.vin.encode('ascii')
            # Multi-line response format
            lines = []
            for i in range(0, len(vin_bytes), 4):
                chunk = vin_bytes[i:i+4]
                line_num = i // 4 + 1
                line_bytes = [0x49, 0x02, line_num] + list(chunk)
                if self._spaces_enabled:
                    lines.append(' '.join(f'{b:02X}' for b in line_bytes))
                else:
                    lines.append(''.join(f'{b:02X}' for b in line_bytes))
            return '\n'.join(lines)
        
        return "NO DATA"
    
    def _format_dtcs(self, dtcs: List[str], response_mode: int) -> str:
        """Format DTCs for response (ELM327 format)."""
        if not dtcs:
            # No DTCs: just return header with 00 00 00 (padding)
            if self._spaces_enabled:
                return f"{response_mode:02X} 00 00 00"
            return f"{response_mode:02X}000000"
        
        # Real ELM327 format: 43 XX XX XX XX ... (no count byte, just DTCs)
        result = [response_mode]
        
        for dtc in dtcs:
            # Parse DTC: P0217 -> bytes
            # Format: First byte = [type:2][digit1:2][digit2:4], Second byte = [digit3:4][digit4:4]
            type_char = dtc[0]
            type_map = {'P': 0, 'C': 1, 'B': 2, 'U': 3}
            type_nibble = type_map.get(type_char.upper(), 0)
            
            digit1 = int(dtc[1], 16)  # 0-3 (or higher for manufacturer codes)
            digit2 = int(dtc[2], 16)
            digit3 = int(dtc[3], 16)
            digit4 = int(dtc[4], 16)
            
            byte1 = (type_nibble << 6) | (digit1 << 4) | digit2
            byte2 = (digit3 << 4) | digit4
            
            result.extend([byte1, byte2])
        
        # Pad to ensure complete DTCs (multiples of 2 bytes)
        while (len(result) - 1) % 2 != 0:
            result.append(0x00)
        
        if self._spaces_enabled:
            return ' '.join(f'{b:02X}' for b in result)
        else:
            return ''.join(f'{b:02X}' for b in result)
    
    # -------------------------------------------------------------------------
    # PID Handlers - Return raw data bytes
    # -------------------------------------------------------------------------
    
    def _pid_00_supported(self) -> bytes:
        """PIDs 01-20 supported bitmap."""
        # Support common PIDs
        supported = [0x01, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0C, 0x0D, 0x0E, 
                     0x0F, 0x10, 0x11, 0x14, 0x15, 0x1C, 0x1F, 0x20]
        bitmap = 0
        for pid in supported:
            if 1 <= pid <= 32:
                bitmap |= (1 << (32 - pid))
        return struct.pack('>I', bitmap)
    
    def _pid_20_supported(self) -> bytes:
        """PIDs 21-40 supported bitmap."""
        supported = [0x21, 0x2F, 0x33]
        bitmap = 0
        for pid in supported:
            if 0x21 <= pid <= 0x40:
                bitmap |= (1 << (0x40 - pid))
        return struct.pack('>I', bitmap)
    
    def _pid_01_monitor_status(self) -> bytes:
        """Monitor status since DTCs cleared."""
        mil_on = 1 if self.state.stored_dtcs else 0
        dtc_count = len(self.state.stored_dtcs)
        # Byte A: MIL + DTC count
        byte_a = (mil_on << 7) | (dtc_count & 0x7F)
        return bytes([byte_a, 0x07, 0xE5, 0x00])  # Common monitor status
    
    def _pid_04_engine_load(self) -> bytes:
        """Calculated engine load (%)."""
        load = self._add_noise(self.state.engine_load, 0.03)
        load = max(0, min(100, load))
        return bytes([int(load * 255 / 100)])
    
    def _pid_05_coolant_temp(self) -> bytes:
        """Coolant temperature (°C, encoded)."""
        # Simulate gradual warmup or cooling
        runtime = time.time() - self.state.start_time
        
        # Skip warmup simulation for fault states (already at operating temp)
        if self.state.coolant_temp_f > 200 or self.state.coolant_temp_f < 160:
            # Fault condition - return the target temp directly
            current_c = (self.state.coolant_temp_f - 32) * 5/9
        elif runtime < 180:  # First 3 minutes
            # Normal warmup
            target = self.state.coolant_temp_f
            ambient_c = (self.profile.ambient_temp - 32) * 5/9
            progress = min(1.0, runtime / 180)
            current_c = ambient_c + ((target - 32) * 5/9 - ambient_c) * progress
        else:
            current_c = (self.state.coolant_temp_f - 32) * 5/9
        
        current_c = self._add_noise(current_c, 0.01)
        # Formula: value = °C + 40
        encoded = int(current_c + 40)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_06_stft_b1(self) -> bytes:
        """Short term fuel trim bank 1 (%)."""
        value = self._add_noise(self.state.stft_b1, 0.1)
        # Formula: % = (value - 128) * 100 / 128
        encoded = int((value * 128 / 100) + 128)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_07_ltft_b1(self) -> bytes:
        """Long term fuel trim bank 1 (%)."""
        value = self._add_noise(self.state.ltft_b1, 0.02)  # Less noise on LTFT
        encoded = int((value * 128 / 100) + 128)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_08_stft_b2(self) -> bytes:
        """Short term fuel trim bank 2 (%)."""
        value = self._add_noise(self.state.stft_b2, 0.1)
        encoded = int((value * 128 / 100) + 128)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_09_ltft_b2(self) -> bytes:
        """Long term fuel trim bank 2 (%)."""
        value = self._add_noise(self.state.ltft_b2, 0.02)
        encoded = int((value * 128 / 100) + 128)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_0c_rpm(self) -> bytes:
        """Engine RPM."""
        rpm = self._add_noise(self.state.rpm, 0.02)
        rpm = max(0, rpm)
        # Formula: RPM = ((A*256)+B)/4
        encoded = int(rpm * 4)
        return struct.pack('>H', min(65535, encoded))
    
    def _pid_0d_speed(self) -> bytes:
        """Vehicle speed (km/h)."""
        speed_kmh = self.state.speed_mph * 1.60934
        speed_kmh = self._add_noise(speed_kmh, 0.02)
        return bytes([int(max(0, min(255, speed_kmh)))])
    
    def _pid_0e_timing(self) -> bytes:
        """Timing advance (degrees)."""
        timing = self._add_noise(self.state.timing_advance, 0.05)
        # Formula: degrees = (value - 128) / 2
        encoded = int(timing * 2 + 128)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_0f_intake_temp(self) -> bytes:
        """Intake air temperature (°C)."""
        temp_c = (self.state.intake_temp_f - 32) * 5/9
        temp_c = self._add_noise(temp_c, 0.02)
        encoded = int(temp_c + 40)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_10_maf(self) -> bytes:
        """MAF air flow rate (g/s)."""
        maf = self._add_noise(self.state.maf, 0.03)
        # Formula: g/s = ((A*256)+B)/100
        encoded = int(maf * 100)
        return struct.pack('>H', min(65535, max(0, encoded)))
    
    def _pid_11_throttle(self) -> bytes:
        """Throttle position (%)."""
        throttle = self._add_noise(self.state.throttle_pos, 0.02)
        encoded = int(throttle * 255 / 100)
        encoded = max(0, min(255, encoded))
        return bytes([encoded])
    
    def _pid_14_o2_b1s1(self) -> bytes:
        """O2 sensor B1S1 (voltage, STFT)."""
        voltage = self._add_noise(self.state.o2_b1s1, 0.15)  # More variation
        voltage = max(0, min(1.275, voltage))
        encoded_v = int(voltage / 0.005)  # 0.005V per bit
        stft = self._add_noise(self.state.stft_b1, 0.1)
        encoded_stft = int((stft * 128 / 100) + 128)
        return bytes([encoded_v, encoded_stft])
    
    def _pid_15_o2_b1s2(self) -> bytes:
        """O2 sensor B1S2 (downstream, voltage)."""
        voltage = self._add_noise(self.state.o2_b1s2, 0.05)  # Less variation downstream
        voltage = max(0, min(1.275, voltage))
        encoded_v = int(voltage / 0.005)
        return bytes([encoded_v, 128])  # STFT not applicable
    
    def _pid_18_o2_b2s1(self) -> bytes:
        """O2 sensor B2S1."""
        voltage = self._add_noise(self.state.o2_b2s1, 0.15)
        voltage = max(0, min(1.275, voltage))
        encoded_v = int(voltage / 0.005)
        stft = self._add_noise(self.state.stft_b2, 0.1)
        encoded_stft = int((stft * 128 / 100) + 128)
        return bytes([encoded_v, encoded_stft])
    
    def _pid_19_o2_b2s2(self) -> bytes:
        """O2 sensor B2S2 (downstream)."""
        voltage = self._add_noise(self.state.o2_b2s2, 0.05)
        voltage = max(0, min(1.275, voltage))
        encoded_v = int(voltage / 0.005)
        return bytes([encoded_v, 128])
    
    def _pid_1c_obd_standard(self) -> bytes:
        """OBD standards compliance."""
        return bytes([0x06])  # ISO 15765-4 (CAN)
    
    def _pid_1f_runtime(self) -> bytes:
        """Run time since engine start (seconds)."""
        runtime = int(time.time() - self.state.start_time)
        return struct.pack('>H', min(65535, runtime))
    
    def _pid_21_distance_mil(self) -> bytes:
        """Distance traveled with MIL on (km)."""
        if self.state.stored_dtcs:
            return struct.pack('>H', 150)  # 150 km with CEL
        return struct.pack('>H', 0)
    
    def _pid_2f_fuel_level(self) -> bytes:
        """Fuel tank level (%)."""
        return bytes([int(65 * 255 / 100)])  # 65% fuel
    
    def _pid_33_baro(self) -> bytes:
        """Barometric pressure (kPa)."""
        return bytes([101])  # ~1 atm
    
    def _pid_42_voltage(self) -> bytes:
        """Control module voltage."""
        voltage = self._add_noise(self.state.voltage, 0.01)
        # Formula: V = ((A*256)+B)/1000
        encoded = int(voltage * 1000)
        return struct.pack('>H', min(65535, max(0, encoded)))
    
    def _pid_46_ambient_temp(self) -> bytes:
        """Ambient air temperature (°C)."""
        temp_c = (self.profile.ambient_temp - 32) * 5/9
        encoded = int(temp_c + 40)
        return bytes([encoded])

    # -------------------------------------------------------------------------
    # Dynamic simulation methods
    # -------------------------------------------------------------------------
    
    def accelerate(self, target_rpm: float = 3000, duration: float = 5.0) -> None:
        """Simulate acceleration."""
        self.state.rpm = target_rpm
        self.state.throttle_pos = 60.0
        self.state.engine_load = 70.0
        self.state.maf = 25.0
        self.state.speed_mph = 45.0
    
    def decelerate(self) -> None:
        """Simulate deceleration to idle."""
        self.state.rpm = self.profile.idle_rpm
        self.state.throttle_pos = 15.0
        self.state.engine_load = 20.0
        self.state.maf = 4.5
        self.state.speed_mph = 0.0
    
    def set_state(self, state_name: str) -> None:
        """Change vehicle state dynamically."""
        self._set_vehicle_state(state_name)


class SimulatorServer:
    """
    TCP server that simulates an ELM327 WiFi adapter.
    
    Allows testing the real WiFi connection code against a simulator.
    """
    
    def __init__(
        self, 
        host: str = "0.0.0.0",
        port: int = 35000,
        vehicle_state: str = "normal"
    ):
        self.host = host
        self.port = port
        self.elm = SimulatedELM327(vehicle_state=vehicle_state)
        self._server = None
    
    async def start(self) -> None:
        """Start the TCP server."""
        self._server = await asyncio.start_server(
            self._handle_client,
            self.host,
            self.port
        )
        
        addr = self._server.sockets[0].getsockname()
        logger.info(f"ELM327 Simulator listening on {addr[0]}:{addr[1]}")
        print(f"🔌 ELM327 Simulator running on {addr[0]}:{addr[1]}")
        print(f"   Vehicle state: {self.elm.state.stored_dtcs or 'Normal (no DTCs)'}")
        print(f"   Connect with: nc {addr[0]} {addr[1]}")
        print(f"   Or use the scan_tool with WiFi address: {addr[0]}:{addr[1]}")
    
    async def serve_forever(self) -> None:
        """Run server until cancelled."""
        await self.start()
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self) -> None:
        """Stop the server."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
    
    async def _handle_client(
        self, 
        reader: asyncio.StreamReader, 
        writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection."""
        addr = writer.get_extra_info('peername')
        logger.info(f"Client connected: {addr}")
        print(f"📱 Client connected: {addr}")
        
        # Send initial prompt
        writer.write(b">")
        await writer.drain()
        
        buffer = b""
        
        try:
            while True:
                # Read data (ELM327 uses \r as line terminator)
                chunk = await reader.read(1024)
                if not chunk:
                    break
                
                buffer += chunk
                
                # Process all complete commands in buffer
                while b'\r' in buffer or b'\n' in buffer:
                    # Find first line terminator
                    cr_pos = buffer.find(b'\r')
                    lf_pos = buffer.find(b'\n')
                    
                    if cr_pos == -1:
                        end_pos = lf_pos
                    elif lf_pos == -1:
                        end_pos = cr_pos
                    else:
                        end_pos = min(cr_pos, lf_pos)
                    
                    command = buffer[:end_pos].decode('ascii', errors='ignore').strip()
                    buffer = buffer[end_pos + 1:]
                    
                    # Skip \n after \r if present
                    if buffer.startswith(b'\n'):
                        buffer = buffer[1:]
                    
                    if not command:
                        writer.write(b">")
                        await writer.drain()
                        continue
                    
                    logger.debug(f"Received: {command}")
                    
                    # Process command
                    response = await self.elm.send_command(command)
                    
                    # Send response with prompt
                    response_bytes = f"{response}\r\n>".encode('ascii')
                    writer.write(response_bytes)
                    await writer.drain()
                    
                    logger.debug(f"Sent: {response}")
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            logger.info(f"Client disconnected: {addr}")
            print(f"📴 Client disconnected: {addr}")
            writer.close()
            await writer.wait_closed()


# =============================================================================
# CLI
# =============================================================================

async def main():
    """Run simulator as standalone TCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="ELM327 Simulator")
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=35000,
        help="TCP port to listen on (default: 35000)"
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--state", "-s",
        default="normal",
        choices=[s.value for s in VehicleState],
        help="Vehicle state to simulate"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    
    print("=" * 50)
    print("ELM327 Simulator for Autotech AI")
    print("=" * 50)
    print(f"Vehicle State: {args.state}")
    print()
    
    server = SimulatorServer(
        host=args.host,
        port=args.port,
        vehicle_state=args.state
    )
    
    try:
        await server.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        await server.stop()


# =============================================================================
# Simulated Connection for Service Layer Testing
# =============================================================================

class SimulatedConnection:
    """
    A mock ELM327Connection that uses SimulatedELM327 internally.
    
    This allows testing the full ELM327Service stack without any
    network or serial connections.
    
    Usage:
        from addons.scan_tool.simulator import SimulatedConnection
        from addons.scan_tool.service import ELM327Service
        
        # Create service with simulated connection
        service = ELM327Service()
        service._connection = SimulatedConnection(vehicle_state='lean_both_banks')
        service._connected = True
        
        # Now use service normally
        dtcs = await service.read_dtcs()
    """
    
    def __init__(self, vehicle_state: str = "normal"):
        """Initialize with a vehicle state."""
        self.elm = SimulatedELM327(vehicle_state=vehicle_state)
        self._connected = True
    
    @property
    def connected(self) -> bool:
        return self._connected
    
    async def connect(self) -> bool:
        """Simulate connection."""
        self._connected = True
        return True
    
    async def disconnect(self) -> None:
        """Simulate disconnection."""
        self._connected = False
    
    async def send_command(self, command: str, timeout: float = None) -> str:
        """Send command to simulator."""
        return await self.elm.send_command(command, timeout or 5.0)


async def test_with_service():
    """
    Test the full service layer using the simulator.
    
    This demonstrates end-to-end testing without hardware.
    """
    from .service import ELM327Service
    from .protocol import OBDProtocol
    
    print("=" * 60)
    print("Full Service Layer Test with Simulator")
    print("=" * 60)
    
    # Test 1: Normal vehicle
    print("\n📗 Test 1: Normal Vehicle")
    print("-" * 40)
    
    service = ELM327Service()
    sim_conn = SimulatedConnection(vehicle_state='normal')
    service._connection = sim_conn
    service._protocol = OBDProtocol(sim_conn)
    service._connected = True
    
    dtcs = await service.read_all_dtcs()
    print(f"  Stored DTCs: {len(dtcs['stored'])}")
    print(f"  Pending DTCs: {len(dtcs['pending'])}")
    
    trims = await service.read_fuel_trims()
    if trims:
        print(f"  STFT B1: {trims.get('STFT_B1', 'N/A')}")
        print(f"  LTFT B1: {trims.get('LTFT_B1', 'N/A')}")
    
    # Test 2: Overheating vehicle  
    print("\n📕 Test 2: Overheating Vehicle")
    print("-" * 40)
    
    service2 = ELM327Service()
    sim_conn2 = SimulatedConnection(vehicle_state='overheating')
    service2._connection = sim_conn2
    service2._protocol = OBDProtocol(sim_conn2)
    service2._connected = True
    
    dtcs2 = await service2.read_all_dtcs()
    print(f"  Stored DTCs: {[d.code for d in dtcs2['stored']]}")
    
    # Test 3: Lean condition
    print("\n📙 Test 3: Lean Both Banks")
    print("-" * 40)
    
    service3 = ELM327Service()
    sim_conn3 = SimulatedConnection(vehicle_state='lean_both_banks')
    service3._connection = sim_conn3
    service3._protocol = OBDProtocol(sim_conn3)
    service3._connected = True
    
    dtcs3 = await service3.read_all_dtcs()
    print(f"  Stored DTCs: {[d.code for d in dtcs3['stored']]}")
    
    trims3 = await service3.read_fuel_trims()
    if trims3:
        for name, reading in trims3.items():
            print(f"  {name}: {reading.value:.1f}%")
    
    print("\n✅ All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
