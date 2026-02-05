"""
OBD2 PID Definitions and Decoders

Standard OBD2 PIDs (Mode 01) with formulas for decoding raw bytes.
"""

from dataclasses import dataclass
from typing import Callable, Optional, List, Dict, Any


@dataclass
class PIDDefinition:
    """Definition of an OBD2 PID."""
    pid: int
    name: str
    description: str
    units: str
    min_value: float
    max_value: float
    bytes_returned: int
    decoder: Callable[[List[int]], float]
    diagnostic_value: str = ""  # Why this PID matters for diagnosis


# Decoder functions
def decode_percent(data: List[int]) -> float:
    """A / 2.55 - percentage (0-100%)"""
    return data[0] / 2.55

def decode_percent_centered(data: List[int]) -> float:
    """(A - 128) * 100/128 - centered percentage (-100 to +100%)"""
    return (data[0] - 128) * 100 / 128

def decode_temp(data: List[int]) -> float:
    """A - 40 - temperature in Celsius"""
    return data[0] - 40

def decode_fuel_pressure(data: List[int]) -> float:
    """A * 3 - fuel pressure in kPa"""
    return data[0] * 3

def decode_rpm(data: List[int]) -> float:
    """((A * 256) + B) / 4 - RPM"""
    return ((data[0] * 256) + data[1]) / 4

def decode_speed(data: List[int]) -> float:
    """A - speed in km/h"""
    return data[0]

def decode_timing(data: List[int]) -> float:
    """(A - 128) / 2 - timing advance in degrees"""
    return (data[0] - 128) / 2

def decode_maf(data: List[int]) -> float:
    """((A * 256) + B) / 100 - MAF in g/s"""
    return ((data[0] * 256) + data[1]) / 100

def decode_throttle(data: List[int]) -> float:
    """A / 2.55 - throttle position percentage"""
    return data[0] / 2.55

def decode_o2_voltage(data: List[int]) -> float:
    """A / 200 - O2 sensor voltage (0-1.275V)"""
    return data[0] / 200

def decode_o2_fuel_trim(data: List[int]) -> float:
    """(B - 128) * 100/128 - O2 sensor short term fuel trim"""
    if len(data) > 1:
        return (data[1] - 128) * 100 / 128
    return 0

def decode_control_voltage(data: List[int]) -> float:
    """((A * 256) + B) / 1000 - voltage"""
    return ((data[0] * 256) + data[1]) / 1000

def decode_runtime(data: List[int]) -> float:
    """(A * 256) + B - seconds since engine start"""
    return (data[0] * 256) + data[1]

def decode_distance(data: List[int]) -> float:
    """(A * 256) + B - distance in km"""
    return (data[0] * 256) + data[1]

def decode_fuel_level(data: List[int]) -> float:
    """A / 2.55 - fuel level percentage"""
    return data[0] / 2.55

def decode_barometric(data: List[int]) -> float:
    """A - barometric pressure in kPa"""
    return data[0]

def decode_catalyst_temp(data: List[int]) -> float:
    """((A * 256) + B) / 10 - 40 - catalyst temp in Celsius"""
    return ((data[0] * 256) + data[1]) / 10 - 40


# PID Definitions - Mode 01
PIDS: Dict[int, PIDDefinition] = {
    0x00: PIDDefinition(
        pid=0x00,
        name="pids_supported_01_20",
        description="PIDs supported [01-20]",
        units="bitmap",
        min_value=0,
        max_value=0xFFFFFFFF,
        bytes_returned=4,
        decoder=lambda d: (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3]
    ),
    0x01: PIDDefinition(
        pid=0x01,
        name="monitor_status",
        description="Monitor status since DTCs cleared",
        units="bitmap",
        min_value=0,
        max_value=0xFFFFFFFF,
        bytes_returned=4,
        decoder=lambda d: (d[0] << 24) | (d[1] << 16) | (d[2] << 8) | d[3],
        diagnostic_value="Shows which monitors are ready/complete"
    ),
    0x03: PIDDefinition(
        pid=0x03,
        name="fuel_system_status",
        description="Fuel system status",
        units="bitmap",
        min_value=0,
        max_value=0xFFFF,
        bytes_returned=2,
        decoder=lambda d: (d[0] << 8) | d[1],
        diagnostic_value="Open/closed loop status"
    ),
    0x04: PIDDefinition(
        pid=0x04,
        name="engine_load",
        description="Calculated engine load",
        units="%",
        min_value=0,
        max_value=100,
        bytes_returned=1,
        decoder=decode_percent,
        diagnostic_value="Engine demand - high at idle indicates issue"
    ),
    0x05: PIDDefinition(
        pid=0x05,
        name="coolant_temp",
        description="Engine coolant temperature",
        units="°C",
        min_value=-40,
        max_value=215,
        bytes_returned=1,
        decoder=decode_temp,
        diagnostic_value="Thermostat operation, overheating"
    ),
    0x06: PIDDefinition(
        pid=0x06,
        name="stft1",
        description="Short term fuel trim - Bank 1",
        units="%",
        min_value=-100,
        max_value=99.2,
        bytes_returned=1,
        decoder=decode_percent_centered,
        diagnostic_value="KEY - Real-time air/fuel correction. >±10% = problem"
    ),
    0x07: PIDDefinition(
        pid=0x07,
        name="ltft1",
        description="Long term fuel trim - Bank 1",
        units="%",
        min_value=-100,
        max_value=99.2,
        bytes_returned=1,
        decoder=decode_percent_centered,
        diagnostic_value="KEY - Learned correction. >±10% = chronic issue"
    ),
    0x08: PIDDefinition(
        pid=0x08,
        name="stft2",
        description="Short term fuel trim - Bank 2",
        units="%",
        min_value=-100,
        max_value=99.2,
        bytes_returned=1,
        decoder=decode_percent_centered,
        diagnostic_value="Compare to Bank 1 - difference indicates bank-specific issue"
    ),
    0x09: PIDDefinition(
        pid=0x09,
        name="ltft2",
        description="Long term fuel trim - Bank 2",
        units="%",
        min_value=-100,
        max_value=99.2,
        bytes_returned=1,
        decoder=decode_percent_centered,
        diagnostic_value="Compare to Bank 1 - difference indicates bank-specific issue"
    ),
    0x0A: PIDDefinition(
        pid=0x0A,
        name="fuel_pressure",
        description="Fuel pressure",
        units="kPa",
        min_value=0,
        max_value=765,
        bytes_returned=1,
        decoder=decode_fuel_pressure,
        diagnostic_value="Fuel pump/regulator health"
    ),
    0x0B: PIDDefinition(
        pid=0x0B,
        name="intake_map",
        description="Intake manifold absolute pressure",
        units="kPa",
        min_value=0,
        max_value=255,
        bytes_returned=1,
        decoder=lambda d: d[0],
        diagnostic_value="Vacuum leaks, turbo boost, engine load"
    ),
    0x0C: PIDDefinition(
        pid=0x0C,
        name="rpm",
        description="Engine RPM",
        units="rpm",
        min_value=0,
        max_value=16383.75,
        bytes_returned=2,
        decoder=decode_rpm,
        diagnostic_value="Idle quality, hunting idle"
    ),
    0x0D: PIDDefinition(
        pid=0x0D,
        name="vehicle_speed",
        description="Vehicle speed",
        units="km/h",
        min_value=0,
        max_value=255,
        bytes_returned=1,
        decoder=decode_speed,
        diagnostic_value="Speed sensor operation"
    ),
    0x0E: PIDDefinition(
        pid=0x0E,
        name="timing_advance",
        description="Timing advance",
        units="°",
        min_value=-64,
        max_value=63.5,
        bytes_returned=1,
        decoder=decode_timing,
        diagnostic_value="Knock sensor activity, timing issues"
    ),
    0x0F: PIDDefinition(
        pid=0x0F,
        name="intake_temp",
        description="Intake air temperature",
        units="°C",
        min_value=-40,
        max_value=215,
        bytes_returned=1,
        decoder=decode_temp,
        diagnostic_value="IAT sensor operation"
    ),
    0x10: PIDDefinition(
        pid=0x10,
        name="maf",
        description="Mass air flow rate",
        units="g/s",
        min_value=0,
        max_value=655.35,
        bytes_returned=2,
        decoder=decode_maf,
        diagnostic_value="KEY - Air metering. Compare to calculated value"
    ),
    0x11: PIDDefinition(
        pid=0x11,
        name="throttle_position",
        description="Throttle position",
        units="%",
        min_value=0,
        max_value=100,
        bytes_returned=1,
        decoder=decode_throttle,
        diagnostic_value="TPS operation, throttle body"
    ),
    0x14: PIDDefinition(
        pid=0x14,
        name="o2_b1s1",
        description="O2 Sensor Bank 1, Sensor 1",
        units="V",
        min_value=0,
        max_value=1.275,
        bytes_returned=2,
        decoder=decode_o2_voltage,
        diagnostic_value="Front O2 - should oscillate 0.1-0.9V in closed loop"
    ),
    0x15: PIDDefinition(
        pid=0x15,
        name="o2_b1s2",
        description="O2 Sensor Bank 1, Sensor 2",
        units="V",
        min_value=0,
        max_value=1.275,
        bytes_returned=2,
        decoder=decode_o2_voltage,
        diagnostic_value="Rear O2 - should be steady ~0.7V if cat is good"
    ),
    0x16: PIDDefinition(
        pid=0x16,
        name="o2_b1s3",
        description="O2 Sensor Bank 1, Sensor 3",
        units="V",
        min_value=0,
        max_value=1.275,
        bytes_returned=2,
        decoder=decode_o2_voltage,
        diagnostic_value="Third O2 if present"
    ),
    0x18: PIDDefinition(
        pid=0x18,
        name="o2_b2s1",
        description="O2 Sensor Bank 2, Sensor 1",
        units="V",
        min_value=0,
        max_value=1.275,
        bytes_returned=2,
        decoder=decode_o2_voltage,
        diagnostic_value="Front O2 Bank 2 - compare to B1S1"
    ),
    0x19: PIDDefinition(
        pid=0x19,
        name="o2_b2s2",
        description="O2 Sensor Bank 2, Sensor 2",
        units="V",
        min_value=0,
        max_value=1.275,
        bytes_returned=2,
        decoder=decode_o2_voltage,
        diagnostic_value="Rear O2 Bank 2"
    ),
    0x1C: PIDDefinition(
        pid=0x1C,
        name="obd_standard",
        description="OBD standards this vehicle conforms to",
        units="enum",
        min_value=1,
        max_value=255,
        bytes_returned=1,
        decoder=lambda d: d[0],
        diagnostic_value="Protocol identification"
    ),
    0x1F: PIDDefinition(
        pid=0x1F,
        name="runtime",
        description="Run time since engine start",
        units="sec",
        min_value=0,
        max_value=65535,
        bytes_returned=2,
        decoder=decode_runtime,
        diagnostic_value="How long engine has been running"
    ),
    0x21: PIDDefinition(
        pid=0x21,
        name="distance_with_mil",
        description="Distance traveled with MIL on",
        units="km",
        min_value=0,
        max_value=65535,
        bytes_returned=2,
        decoder=decode_distance,
        diagnostic_value="How long they've been driving with check engine light"
    ),
    0x2F: PIDDefinition(
        pid=0x2F,
        name="fuel_level",
        description="Fuel tank level input",
        units="%",
        min_value=0,
        max_value=100,
        bytes_returned=1,
        decoder=decode_fuel_level,
        diagnostic_value="Fuel sender operation"
    ),
    0x31: PIDDefinition(
        pid=0x31,
        name="distance_since_cleared",
        description="Distance since codes cleared",
        units="km",
        min_value=0,
        max_value=65535,
        bytes_returned=2,
        decoder=decode_distance,
        diagnostic_value="Readiness status indicator"
    ),
    0x33: PIDDefinition(
        pid=0x33,
        name="barometric_pressure",
        description="Barometric pressure",
        units="kPa",
        min_value=0,
        max_value=255,
        bytes_returned=1,
        decoder=decode_barometric,
        diagnostic_value="Altitude compensation"
    ),
    0x42: PIDDefinition(
        pid=0x42,
        name="control_voltage",
        description="Control module voltage",
        units="V",
        min_value=0,
        max_value=65.535,
        bytes_returned=2,
        decoder=decode_control_voltage,
        diagnostic_value="Charging system health - should be 13.5-14.5V running"
    ),
    0x45: PIDDefinition(
        pid=0x45,
        name="relative_throttle",
        description="Relative throttle position",
        units="%",
        min_value=0,
        max_value=100,
        bytes_returned=1,
        decoder=decode_percent,
        diagnostic_value="Throttle position relative to learned idle"
    ),
    0x46: PIDDefinition(
        pid=0x46,
        name="ambient_temp",
        description="Ambient air temperature",
        units="°C",
        min_value=-40,
        max_value=215,
        bytes_returned=1,
        decoder=decode_temp,
        diagnostic_value="Outside temperature"
    ),
    0x3C: PIDDefinition(
        pid=0x3C,
        name="catalyst_temp_b1s1",
        description="Catalyst temperature Bank 1, Sensor 1",
        units="°C",
        min_value=-40,
        max_value=6513.5,
        bytes_returned=2,
        decoder=decode_catalyst_temp,
        diagnostic_value="Catalyst light-off temperature"
    ),
}

# Essential PIDs for diagnosis - read these first
ESSENTIAL_PIDS = [
    0x04,  # Engine load
    0x05,  # Coolant temp
    0x06,  # STFT1
    0x07,  # LTFT1
    0x08,  # STFT2
    0x09,  # LTFT2
    0x0B,  # MAP
    0x0C,  # RPM
    0x0D,  # Speed
    0x0E,  # Timing
    0x0F,  # IAT
    0x10,  # MAF
    0x11,  # Throttle
    0x14,  # O2 B1S1
    0x15,  # O2 B1S2
    0x42,  # Control voltage
]


def get_pid_name(pid: int) -> str:
    """Get human-readable name for a PID."""
    if pid in PIDS:
        return PIDS[pid].name
    return f"pid_{pid:02x}"


def decode_pid(pid: int, data: List[int]) -> Optional[float]:
    """Decode raw PID data to value."""
    if pid in PIDS:
        try:
            return PIDS[pid].decoder(data)
        except (IndexError, ValueError):
            return None
    return None


def format_pid_value(pid: int, value: float) -> str:
    """Format a PID value with units."""
    if pid in PIDS:
        definition = PIDS[pid]
        if definition.units == "%":
            return f"{value:+.1f}%" if "trim" in definition.name else f"{value:.1f}%"
        elif definition.units == "°C":
            return f"{value:.0f}°C"
        elif definition.units == "rpm":
            return f"{value:.0f} RPM"
        elif definition.units == "V":
            return f"{value:.3f}V"
        elif definition.units == "g/s":
            return f"{value:.2f} g/s"
        elif definition.units == "kPa":
            return f"{value:.0f} kPa"
        elif definition.units == "km/h":
            return f"{value:.0f} km/h"
        elif definition.units == "°":
            return f"{value:.1f}°"
        elif definition.units == "sec":
            return f"{value:.0f} sec"
        elif definition.units == "km":
            return f"{value:.0f} km"
        else:
            return f"{value}"
    return f"{value}"
