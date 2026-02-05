"""
OBD-II Integration Module

Provides interface to connect real vehicle data to the physics diagnostic engine.
Supports multiple OBD-II adapters and protocols.

Adapter Support:
- ELM327 (USB, Bluetooth, WiFi)
- OBDLink (MX+, LX, EX, SX)
- Veepeak
- BAFX Products

Protocols:
- SAE J1850 PWM/VPW
- ISO 9141-2
- ISO 14230-4 (KWP2000)
- ISO 15765-4 (CAN)
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
import re

log = logging.getLogger("obd_integration")


class OBDProtocol(Enum):
    """OBD-II protocol types."""
    AUTO = "auto"
    SAE_J1850_PWM = "j1850_pwm"      # Ford
    SAE_J1850_VPW = "j1850_vpw"      # GM
    ISO_9141_2 = "iso9141"           # Chrysler, Asian, European
    ISO_14230_KWP = "kwp2000"        # KWP2000
    ISO_15765_CAN = "can"            # CAN (most modern vehicles)


class ConnectionState(Enum):
    """OBD adapter connection state."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    ERROR = "error"


@dataclass
class OBDReading:
    """A single OBD-II reading."""
    pid: str                           # PID code (e.g., "010C" for RPM)
    name: str                          # Human-readable name
    value: float                       # Decoded value
    unit: str                          # Unit of measurement
    raw_response: str = ""             # Raw hex response
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class VehicleData:
    """Current vehicle data snapshot."""
    # Engine
    rpm: Optional[float] = None
    engine_load_percent: Optional[float] = None
    coolant_temp_c: Optional[float] = None
    intake_air_temp_c: Optional[float] = None
    throttle_position_percent: Optional[float] = None
    
    # Fuel
    fuel_pressure_kpa: Optional[float] = None
    fuel_level_percent: Optional[float] = None
    stft_bank1_percent: Optional[float] = None
    stft_bank2_percent: Optional[float] = None
    ltft_bank1_percent: Optional[float] = None
    ltft_bank2_percent: Optional[float] = None
    afr_commanded: Optional[float] = None
    afr_actual: Optional[float] = None
    
    # Speed/Position
    vehicle_speed_kph: Optional[float] = None
    maf_gs: Optional[float] = None
    timing_advance_deg: Optional[float] = None
    
    # Emissions
    o2_voltage_b1s1: Optional[float] = None
    o2_voltage_b1s2: Optional[float] = None
    catalyst_temp_b1s1_c: Optional[float] = None
    catalyst_temp_b1s2_c: Optional[float] = None
    egr_commanded_percent: Optional[float] = None
    egr_error_percent: Optional[float] = None
    
    # Electrical
    battery_voltage: Optional[float] = None
    control_module_voltage: Optional[float] = None
    
    # Transmission
    transmission_temp_c: Optional[float] = None
    
    # DTCs
    mil_status: bool = False
    dtc_count: int = 0
    dtcs: List[str] = field(default_factory=list)
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    vin: Optional[str] = None


# Standard OBD-II PIDs (Mode 01)
OBD_PIDS = {
    # Engine
    "010C": {"name": "engine_rpm", "unit": "RPM", "formula": lambda a, b: ((a * 256) + b) / 4},
    "0104": {"name": "engine_load_percent", "unit": "%", "formula": lambda a: a * 100 / 255},
    "0105": {"name": "coolant_temp_c", "unit": "°C", "formula": lambda a: a - 40},
    "010F": {"name": "intake_air_temp_c", "unit": "°C", "formula": lambda a: a - 40},
    "0111": {"name": "throttle_position_percent", "unit": "%", "formula": lambda a: a * 100 / 255},
    
    # Fuel
    "010A": {"name": "fuel_pressure_kpa", "unit": "kPa", "formula": lambda a: a * 3},
    "012F": {"name": "fuel_level_percent", "unit": "%", "formula": lambda a: a * 100 / 255},
    "0106": {"name": "stft_bank1_percent", "unit": "%", "formula": lambda a: (a - 128) * 100 / 128},
    "0107": {"name": "ltft_bank1_percent", "unit": "%", "formula": lambda a: (a - 128) * 100 / 128},
    "0108": {"name": "stft_bank2_percent", "unit": "%", "formula": lambda a: (a - 128) * 100 / 128},
    "0109": {"name": "ltft_bank2_percent", "unit": "%", "formula": lambda a: (a - 128) * 100 / 128},
    "0144": {"name": "afr_commanded", "unit": "AFR", "formula": lambda a, b: ((a * 256) + b) * 2 / 65536 * 14.7},
    
    # Speed/Position
    "010D": {"name": "vehicle_speed_kph", "unit": "km/h", "formula": lambda a: a},
    "0110": {"name": "maf_gs", "unit": "g/s", "formula": lambda a, b: ((a * 256) + b) / 100},
    "010E": {"name": "timing_advance_deg", "unit": "°", "formula": lambda a: (a - 128) / 2},
    
    # O2 Sensors
    "0114": {"name": "o2_voltage_b1s1", "unit": "V", "formula": lambda a, b: a / 200},
    "0115": {"name": "o2_voltage_b1s2", "unit": "V", "formula": lambda a, b: a / 200},
    
    # Catalyst
    "013C": {"name": "catalyst_temp_b1s1_c", "unit": "°C", "formula": lambda a, b: ((a * 256) + b) / 10 - 40},
    "013E": {"name": "catalyst_temp_b1s2_c", "unit": "°C", "formula": lambda a, b: ((a * 256) + b) / 10 - 40},
    
    # EGR
    "012C": {"name": "egr_commanded_percent", "unit": "%", "formula": lambda a: a * 100 / 255},
    "012D": {"name": "egr_error_percent", "unit": "%", "formula": lambda a: (a - 128) * 100 / 128},
    
    # Electrical
    "0142": {"name": "control_module_voltage", "unit": "V", "formula": lambda a, b: ((a * 256) + b) / 1000},
    
    # Status
    "0101": {"name": "monitor_status", "unit": "", "formula": None},  # Special handling
}


class OBDAdapter(ABC):
    """Abstract base class for OBD-II adapters."""
    
    @abstractmethod
    async def connect(self, port: str, **kwargs) -> bool:
        """Connect to the adapter."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the adapter."""
        pass
    
    @abstractmethod
    async def send_command(self, command: str) -> str:
        """Send a command and get response."""
        pass
    
    @abstractmethod
    async def read_pid(self, pid: str) -> Optional[OBDReading]:
        """Read a specific PID."""
        pass
    
    @abstractmethod
    async def read_dtcs(self) -> List[str]:
        """Read diagnostic trouble codes."""
        pass
    
    @abstractmethod
    async def clear_dtcs(self) -> bool:
        """Clear diagnostic trouble codes."""
        pass
    
    @property
    @abstractmethod
    def state(self) -> ConnectionState:
        """Get current connection state."""
        pass


class ELM327Adapter(OBDAdapter):
    """
    ELM327-based adapter implementation.
    
    Works with most ELM327 clone adapters (USB, Bluetooth, WiFi).
    """
    
    def __init__(self):
        self._state = ConnectionState.DISCONNECTED
        self._protocol = OBDProtocol.AUTO
        self._reader = None
        self._writer = None
        self._timeout = 5.0
    
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    async def connect(
        self,
        port: str,
        baudrate: int = 38400,
        protocol: OBDProtocol = OBDProtocol.AUTO,
        timeout: float = 5.0,
        **kwargs
    ) -> bool:
        """
        Connect to ELM327 adapter.
        
        Args:
            port: Serial port (e.g., "/dev/ttyUSB0", "COM3") or
                  IP:port for WiFi adapters (e.g., "192.168.0.10:35000")
            baudrate: Serial baud rate (ignored for WiFi)
            protocol: OBD protocol to use
            timeout: Command timeout in seconds
        """
        self._state = ConnectionState.CONNECTING
        self._timeout = timeout
        
        try:
            # Check if WiFi adapter (IP:port format)
            if ":" in port and not port.startswith("/dev"):
                # WiFi connection
                host, port_num = port.rsplit(":", 1)
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(host, int(port_num)),
                    timeout=timeout
                )
            else:
                # Serial connection - would use pyserial-asyncio
                # For now, simulate serial as file descriptor
                log.warning("Serial connection not fully implemented - use WiFi adapter")
                self._state = ConnectionState.ERROR
                return False
            
            # Initialize ELM327
            await self._init_elm327(protocol)
            
            self._state = ConnectionState.CONNECTED
            return True
            
        except Exception as e:
            log.error(f"Connection failed: {e}")
            self._state = ConnectionState.ERROR
            return False
    
    async def _init_elm327(self, protocol: OBDProtocol):
        """Initialize ELM327 adapter."""
        # Reset
        await self.send_command("ATZ")
        await asyncio.sleep(1)
        
        # Echo off
        await self.send_command("ATE0")
        
        # Headers off
        await self.send_command("ATH0")
        
        # Spaces off
        await self.send_command("ATS0")
        
        # Line feeds off
        await self.send_command("ATL0")
        
        # Set protocol
        if protocol == OBDProtocol.AUTO:
            await self.send_command("ATSP0")  # Auto
        elif protocol == OBDProtocol.ISO_15765_CAN:
            await self.send_command("ATSP6")  # CAN 11-bit
        elif protocol == OBDProtocol.ISO_9141_2:
            await self.send_command("ATSP3")  # ISO 9141-2
        elif protocol == OBDProtocol.ISO_14230_KWP:
            await self.send_command("ATSP4")  # KWP 5-baud
        elif protocol == OBDProtocol.SAE_J1850_PWM:
            await self.send_command("ATSP1")  # J1850 PWM
        elif protocol == OBDProtocol.SAE_J1850_VPW:
            await self.send_command("ATSP2")  # J1850 VPW
        
        self._protocol = protocol
    
    async def disconnect(self) -> None:
        """Disconnect from adapter."""
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()
        self._reader = None
        self._writer = None
        self._state = ConnectionState.DISCONNECTED
    
    async def send_command(self, command: str) -> str:
        """Send command and get response."""
        if self._state != ConnectionState.CONNECTED and not command.startswith("AT"):
            raise RuntimeError("Not connected")
        
        try:
            # Send command
            self._writer.write(f"{command}\r".encode())
            await self._writer.drain()
            
            # Read response
            response = ""
            while True:
                chunk = await asyncio.wait_for(
                    self._reader.read(1024),
                    timeout=self._timeout
                )
                if not chunk:
                    break
                response += chunk.decode()
                if ">" in response:
                    break
            
            # Clean response
            response = response.replace(">", "").strip()
            return response
            
        except asyncio.TimeoutError:
            log.warning(f"Timeout on command: {command}")
            return ""
    
    async def read_pid(self, pid: str) -> Optional[OBDReading]:
        """Read a specific PID."""
        if pid not in OBD_PIDS:
            log.warning(f"Unknown PID: {pid}")
            return None
        
        pid_info = OBD_PIDS[pid]
        response = await self.send_command(pid)
        
        if not response or "NO DATA" in response or "ERROR" in response:
            return None
        
        try:
            # Parse hex response
            # Response format: "41 0C 1A F8" for RPM
            parts = response.split()
            
            # Find the data bytes (after mode + PID echo)
            if len(parts) < 3:
                return None
            
            data_bytes = [int(b, 16) for b in parts[2:]]
            
            # Apply formula
            formula = pid_info["formula"]
            if formula is None:
                value = 0.0
            elif len(data_bytes) == 1:
                value = formula(data_bytes[0])
            elif len(data_bytes) >= 2:
                value = formula(data_bytes[0], data_bytes[1])
            else:
                return None
            
            return OBDReading(
                pid=pid,
                name=pid_info["name"],
                value=value,
                unit=pid_info["unit"],
                raw_response=response,
            )
            
        except (ValueError, IndexError) as e:
            log.error(f"Failed to parse PID {pid}: {e}")
            return None
    
    async def read_dtcs(self) -> List[str]:
        """Read diagnostic trouble codes (Mode 03)."""
        response = await self.send_command("03")
        
        if not response or "NO DATA" in response:
            return []
        
        dtcs = []
        try:
            # Parse DTC response
            # Format: "43 01 33 02 17" = P0133, P0217
            parts = response.split()
            if len(parts) < 2:
                return []
            
            # Skip mode byte (43)
            for i in range(1, len(parts), 2):
                if i + 1 >= len(parts):
                    break
                
                byte1 = int(parts[i], 16)
                byte2 = int(parts[i + 1], 16)
                
                if byte1 == 0 and byte2 == 0:
                    continue  # No more DTCs
                
                # Decode DTC
                # First nibble = type (0=P0, 1=P1, 2=P2, 3=P3, 4=C0, etc.)
                type_nibble = (byte1 >> 6) & 0x03
                type_char = "PCBU"[type_nibble]
                
                second_nibble = (byte1 >> 4) & 0x03
                
                dtc = f"{type_char}{second_nibble}{byte1 & 0x0F:01X}{byte2:02X}"
                dtcs.append(dtc)
            
        except (ValueError, IndexError) as e:
            log.error(f"Failed to parse DTCs: {e}")
        
        return dtcs
    
    async def clear_dtcs(self) -> bool:
        """Clear diagnostic trouble codes (Mode 04)."""
        response = await self.send_command("04")
        return "44" in response or "OK" in response.upper()


class SimulatedAdapter(OBDAdapter):
    """
    Simulated OBD adapter for testing.
    
    Generates realistic vehicle data without real hardware.
    """
    
    def __init__(self):
        self._state = ConnectionState.DISCONNECTED
        self._vehicle_data = VehicleData()
        self._dtcs: List[str] = []
        
        # Simulation parameters
        self._rpm = 800.0
        self._speed = 0.0
        self._coolant_temp = 25.0
        self._running = False
    
    @property
    def state(self) -> ConnectionState:
        return self._state
    
    async def connect(self, port: str, **kwargs) -> bool:
        """Connect (simulated)."""
        self._state = ConnectionState.CONNECTED
        return True
    
    async def disconnect(self) -> None:
        """Disconnect (simulated)."""
        self._state = ConnectionState.DISCONNECTED
    
    async def send_command(self, command: str) -> str:
        """Send command (simulated)."""
        return "OK"
    
    def set_engine_running(self, running: bool, rpm: float = 800.0):
        """Set simulated engine state."""
        self._running = running
        self._rpm = rpm if running else 0.0
    
    def set_vehicle_speed(self, speed_kph: float):
        """Set simulated vehicle speed."""
        self._speed = speed_kph
    
    def set_coolant_temp(self, temp_c: float):
        """Set simulated coolant temperature."""
        self._coolant_temp = temp_c
    
    def add_dtc(self, dtc: str):
        """Add a simulated DTC."""
        if dtc not in self._dtcs:
            self._dtcs.append(dtc)
    
    def clear_simulated_dtcs(self):
        """Clear simulated DTCs."""
        self._dtcs.clear()
    
    async def read_pid(self, pid: str) -> Optional[OBDReading]:
        """Read simulated PID."""
        if self._state != ConnectionState.CONNECTED:
            return None
        
        if pid not in OBD_PIDS:
            return None
        
        pid_info = OBD_PIDS[pid]
        
        # Generate simulated values
        simulated_values = {
            "010C": self._rpm,
            "0104": 30.0 if self._running else 0.0,
            "0105": self._coolant_temp,
            "010D": self._speed,
            "010F": 25.0 + self._rpm * 0.01,
            "0111": 15.0 if self._running else 0.0,
            "010A": 350.0 if self._running else 0.0,
            "0106": 0.0,  # STFT
            "0107": 0.0,  # LTFT
            "0110": 10.0 + self._rpm * 0.01 if self._running else 0.0,
            "010E": 15.0 if self._running else 0.0,
            "0114": 0.5,  # O2 B1S1
            "0115": 0.45,  # O2 B1S2
            "0142": 14.2 if self._running else 12.6,
        }
        
        value = simulated_values.get(pid, 0.0)
        
        return OBDReading(
            pid=pid,
            name=pid_info["name"],
            value=value,
            unit=pid_info["unit"],
            raw_response="SIMULATED",
        )
    
    async def read_dtcs(self) -> List[str]:
        """Read simulated DTCs."""
        return self._dtcs.copy()
    
    async def clear_dtcs(self) -> bool:
        """Clear simulated DTCs."""
        self._dtcs.clear()
        return True


class OBDInterface:
    """
    High-level OBD-II interface.
    
    Provides easy access to vehicle data and integrates with
    the physics diagnostic engine.
    """
    
    def __init__(self, adapter: Optional[OBDAdapter] = None):
        self.adapter = adapter or SimulatedAdapter()
        self._vehicle_data = VehicleData()
        self._callbacks: List[Callable[[VehicleData], None]] = []
        self._monitoring = False
        self._monitor_task: Optional[asyncio.Task] = None
    
    async def connect(self, port: str, **kwargs) -> bool:
        """Connect to vehicle."""
        return await self.adapter.connect(port, **kwargs)
    
    async def disconnect(self) -> None:
        """Disconnect from vehicle."""
        await self.stop_monitoring()
        await self.adapter.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self.adapter.state == ConnectionState.CONNECTED
    
    async def read_all_data(self) -> VehicleData:
        """Read all available vehicle data."""
        data = VehicleData()
        data.timestamp = datetime.now()
        
        # Read standard PIDs
        pid_map = {
            "010C": "rpm",
            "0104": "engine_load_percent",
            "0105": "coolant_temp_c",
            "010F": "intake_air_temp_c",
            "0111": "throttle_position_percent",
            "010A": "fuel_pressure_kpa",
            "012F": "fuel_level_percent",
            "0106": "stft_bank1_percent",
            "0107": "ltft_bank1_percent",
            "010D": "vehicle_speed_kph",
            "0110": "maf_gs",
            "010E": "timing_advance_deg",
            "0114": "o2_voltage_b1s1",
            "0115": "o2_voltage_b1s2",
            "0142": "control_module_voltage",
        }
        
        for pid, attr in pid_map.items():
            reading = await self.adapter.read_pid(pid)
            if reading:
                setattr(data, attr, reading.value)
        
        # Map control module voltage to battery voltage
        if data.control_module_voltage:
            data.battery_voltage = data.control_module_voltage
        
        # Read DTCs
        data.dtcs = await self.adapter.read_dtcs()
        data.dtc_count = len(data.dtcs)
        data.mil_status = data.dtc_count > 0
        
        self._vehicle_data = data
        return data
    
    async def get_diagnostic_input(self) -> Dict[str, Any]:
        """
        Get data formatted for the physics diagnostic engine.
        
        Returns dict suitable for DiagnosticEngine.diagnose()
        """
        data = await self.read_all_data()
        
        pids = {}
        
        # Map VehicleData to diagnostic engine PID names
        if data.coolant_temp_c is not None:
            pids["coolant_temp_c"] = data.coolant_temp_c
        if data.rpm is not None:
            pids["rpm"] = data.rpm
        if data.vehicle_speed_kph is not None:
            pids["vehicle_speed_kph"] = data.vehicle_speed_kph
        if data.battery_voltage is not None:
            pids["battery_voltage"] = data.battery_voltage
        if data.fuel_pressure_kpa is not None:
            # Convert kPa to PSI for diagnostic engine
            pids["fuel_pressure_psi"] = data.fuel_pressure_kpa * 0.145038
        if data.stft_bank1_percent is not None:
            pids["stft_percent"] = data.stft_bank1_percent
        if data.ltft_bank1_percent is not None:
            pids["ltft_percent"] = data.ltft_bank1_percent
        if data.maf_gs is not None:
            pids["maf_gs"] = data.maf_gs
        if data.o2_voltage_b1s1 is not None:
            pids["o2_voltage"] = data.o2_voltage_b1s1
        
        return {
            "dtcs": data.dtcs,
            "pids": pids,
            "complaints": [],  # Would be added by user
        }
    
    def register_callback(self, callback: Callable[[VehicleData], None]):
        """Register callback for data updates."""
        self._callbacks.append(callback)
    
    async def start_monitoring(self, interval_ms: int = 250):
        """Start continuous data monitoring."""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop(interval_ms))
    
    async def stop_monitoring(self):
        """Stop continuous monitoring."""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
    
    async def _monitor_loop(self, interval_ms: int):
        """Internal monitoring loop."""
        while self._monitoring:
            try:
                data = await self.read_all_data()
                for callback in self._callbacks:
                    try:
                        callback(data)
                    except Exception as e:
                        log.error(f"Callback error: {e}")
                await asyncio.sleep(interval_ms / 1000.0)
            except Exception as e:
                log.error(f"Monitor error: {e}")
                await asyncio.sleep(1.0)


def run_tests():
    """Run OBD-II integration tests."""
    import asyncio
    
    print("=" * 60)
    print("OBD-II INTEGRATION MODULE TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {name} PASSED {detail}")
            passed += 1
        else:
            print(f"❌ {name} FAILED {detail}")
            failed += 1
    
    async def run_async_tests():
        nonlocal passed, failed
        
        # Test 1: Simulated adapter connection
        print("\n--- Test 1: Simulated Adapter ---")
        adapter = SimulatedAdapter()
        connected = await adapter.connect("SIM")
        check("Connect to simulated adapter", connected)
        check("State is connected", adapter.state == ConnectionState.CONNECTED)
        
        # Test 2: Read simulated PIDs
        print("\n--- Test 2: Read PIDs ---")
        adapter.set_engine_running(True, rpm=2000)
        adapter.set_coolant_temp(85)
        adapter.set_vehicle_speed(60)
        
        rpm_reading = await adapter.read_pid("010C")
        check(
            "Read RPM",
            rpm_reading is not None and rpm_reading.value == 2000,
            f"(RPM={rpm_reading.value if rpm_reading else 'None'})"
        )
        
        temp_reading = await adapter.read_pid("0105")
        check(
            "Read coolant temp",
            temp_reading is not None and temp_reading.value == 85,
            f"(temp={temp_reading.value if temp_reading else 'None'}°C)"
        )
        
        # Test 3: Simulated DTCs
        print("\n--- Test 3: DTCs ---")
        adapter.add_dtc("P0217")
        adapter.add_dtc("P0171")
        dtcs = await adapter.read_dtcs()
        check(
            "Read DTCs",
            len(dtcs) == 2 and "P0217" in dtcs,
            f"(DTCs={dtcs})"
        )
        
        cleared = await adapter.clear_dtcs()
        dtcs_after = await adapter.read_dtcs()
        check(
            "Clear DTCs",
            cleared and len(dtcs_after) == 0,
            f"(cleared={cleared}, count={len(dtcs_after)})"
        )
        
        # Test 4: OBDInterface
        print("\n--- Test 4: OBDInterface ---")
        interface = OBDInterface(adapter)
        adapter.set_engine_running(True, rpm=1500)
        adapter.add_dtc("P0128")
        
        diag_input = await interface.get_diagnostic_input()
        check(
            "Get diagnostic input",
            "dtcs" in diag_input and "pids" in diag_input,
            f"(keys={list(diag_input.keys())})"
        )
        check(
            "DTCs in diagnostic input",
            "P0128" in diag_input["dtcs"],
            f"(dtcs={diag_input['dtcs']})"
        )
        check(
            "PIDs in diagnostic input",
            "rpm" in diag_input["pids"],
            f"(pids={list(diag_input['pids'].keys())})"
        )
        
        # Test 5: Disconnect
        print("\n--- Test 5: Disconnect ---")
        await interface.disconnect()
        check(
            "Disconnect",
            adapter.state == ConnectionState.DISCONNECTED
        )
    
    asyncio.run(run_async_tests())
    
    # Summary
    print("\n" + "=" * 60)
    print(f"  Total: {passed}/{passed+failed} tests passed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! OBD-II integration is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review output above.")
    
    return failed == 0


if __name__ == "__main__":
    run_tests()
