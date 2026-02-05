"""
PID Specifications and Normal Ranges

This module defines:
1. Standard OBD2 PIDs and their universal normal ranges
2. Vehicle-specific overrides from AutoDB/Mitchell
3. Physics-derived derived expectations

Sources of "normal":
- OBD2 standard: PID definitions
- Universal physics: Fuel trim ±10%, warmup time 5-10 min
- AutoDB: Vehicle-specific specs (primary source, 700GB+ of manuals)
- Mitchell: Vehicle-specific specs (fallback, rate-limited)

The system doesn't LEARN what's normal. We TELL it from these sources.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# OBD2 PID Definitions (Standard Mode 01)
# =============================================================================

class PIDCategory(str, Enum):
    """Categories of PIDs for grouping."""
    ENGINE = "engine"
    FUEL = "fuel"
    COOLING = "cooling"
    AIR_INTAKE = "air_intake"
    IGNITION = "ignition"
    EMISSIONS = "emissions"
    ELECTRICAL = "electrical"
    TRANSMISSION = "transmission"


@dataclass
class PIDSpec:
    """Specification for a single OBD2 PID."""
    pid: int                          # OBD2 PID number (hex)
    name: str                         # Human readable name
    short_name: str                   # Code name for use in signatures
    unit: str                         # Unit of measurement
    category: PIDCategory             # Which system it belongs to
    
    # Universal normal ranges (applies to most vehicles)
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    
    # Physics-derived expectations
    expected_at_idle: Optional[str] = None      # What to expect at idle
    expected_at_load: Optional[str] = None      # What to expect under load
    expected_warmup: Optional[str] = None       # Warmup behavior
    
    # Formula for derived values (if applicable)
    formula: Optional[str] = None
    
    # Related PIDs for cross-validation
    related_pids: List[str] = field(default_factory=list)
    
    # What failures this PID can detect
    detects_failures: List[str] = field(default_factory=list)


# =============================================================================
# STANDARD OBD2 PIDs - Mode 01
# =============================================================================

STANDARD_PIDS: Dict[str, PIDSpec] = {
    # ----- COOLING SYSTEM -----
    "coolant_temp": PIDSpec(
        pid=0x05,
        name="Engine Coolant Temperature",
        short_name="coolant_temp",
        unit="°F",
        category=PIDCategory.COOLING,
        normal_min=195,
        normal_max=220,
        expected_at_idle="Should stabilize at thermostat opening temp",
        expected_warmup="Should reach operating temp in 5-10 minutes",
        detects_failures=[
            "thermostat_stuck_open",      # Slow rise, never reaches normal
            "thermostat_stuck_closed",    # Rises too fast, overheats
            "coolant_leak",               # May fluctuate or overheat
            "cooling_fan_failure",        # Overheats at idle
            "water_pump_failure",         # Rapid overheat
        ],
    ),
    
    # ----- FUEL SYSTEM -----
    "short_term_fuel_trim_b1": PIDSpec(
        pid=0x06,
        name="Short Term Fuel Trim - Bank 1",
        short_name="stft_b1",
        unit="%",
        category=PIDCategory.FUEL,
        normal_min=-10,
        normal_max=10,
        expected_at_idle="Should be near 0% at steady state idle",
        expected_at_load="May swing wider under transient conditions",
        related_pids=["long_term_fuel_trim_b1", "o2_sensor_b1s1"],
        detects_failures=[
            "vacuum_leak",                # Goes positive (lean)
            "injector_clogged",           # Goes positive (lean)
            "injector_leaking",           # Goes negative (rich)
            "maf_sensor_dirty",           # Usually goes positive
            "fuel_pressure_low",          # Goes positive (lean)
            "purge_valve_stuck_open",     # Goes negative (rich)
        ],
    ),
    
    "long_term_fuel_trim_b1": PIDSpec(
        pid=0x07,
        name="Long Term Fuel Trim - Bank 1",
        short_name="ltft_b1",
        unit="%",
        category=PIDCategory.FUEL,
        normal_min=-10,
        normal_max=10,
        expected_at_idle="Represents learned correction, should be stable",
        expected_at_load="Should not vary much with load",
        related_pids=["short_term_fuel_trim_b1"],
        detects_failures=[
            "chronic_vacuum_leak",
            "failing_fuel_pump",
            "maf_sensor_drift",
        ],
    ),
    
    "short_term_fuel_trim_b2": PIDSpec(
        pid=0x08,
        name="Short Term Fuel Trim - Bank 2",
        short_name="stft_b2",
        unit="%",
        category=PIDCategory.FUEL,
        normal_min=-10,
        normal_max=10,
        expected_at_idle="Should match Bank 1 within 5%",
        related_pids=["short_term_fuel_trim_b1"],
        detects_failures=[
            "bank_specific_vacuum_leak",
            "bank_specific_injector_issue",
        ],
    ),
    
    "long_term_fuel_trim_b2": PIDSpec(
        pid=0x09,
        name="Long Term Fuel Trim - Bank 2",
        short_name="ltft_b2",
        unit="%",
        category=PIDCategory.FUEL,
        normal_min=-10,
        normal_max=10,
        related_pids=["long_term_fuel_trim_b1"],
        detects_failures=[
            "bank_2_specific_issue",
        ],
    ),
    
    "fuel_pressure": PIDSpec(
        pid=0x0A,
        name="Fuel Pressure",
        short_name="fuel_press",
        unit="kPa",
        category=PIDCategory.FUEL,
        # Normal varies widely by vehicle - must get from specs
        expected_at_idle="Should be within ±10% of spec",
        expected_at_load="Should rise slightly with demand",
        detects_failures=[
            "fuel_pump_weak",
            "fuel_pressure_regulator_failure",
            "clogged_fuel_filter",
        ],
    ),
    
    # ----- AIR INTAKE -----
    "intake_manifold_pressure": PIDSpec(
        pid=0x0B,
        name="Intake Manifold Absolute Pressure",
        short_name="map",
        unit="kPa",
        category=PIDCategory.AIR_INTAKE,
        # Normal at idle ~30-40 kPa, at WOT ~100 kPa (atmospheric)
        expected_at_idle="Low vacuum (30-40 kPa typical)",
        expected_at_load="Rises toward atmospheric (100 kPa)",
        related_pids=["maf", "throttle_position"],
        detects_failures=[
            "vacuum_leak",                # Higher than normal at idle
            "pcv_valve_stuck",
            "intake_gasket_leak",
        ],
    ),
    
    "rpm": PIDSpec(
        pid=0x0C,
        name="Engine RPM",
        short_name="rpm",
        unit="rpm",
        category=PIDCategory.ENGINE,
        # Normal idle varies by vehicle 600-1000 rpm
        expected_at_idle="Steady at spec (typically 650-850 rpm)",
        expected_at_load="Responsive, no hesitation",
        detects_failures=[
            "idle_air_control_failure",   # High or low idle
            "vacuum_leak",                # High idle
            "misfire",                    # Rough/unstable idle
        ],
    ),
    
    "vehicle_speed": PIDSpec(
        pid=0x0D,
        name="Vehicle Speed",
        short_name="vss",
        unit="mph",
        category=PIDCategory.ENGINE,
        detects_failures=[
            "speed_sensor_failure",
        ],
    ),
    
    "intake_air_temp": PIDSpec(
        pid=0x0F,
        name="Intake Air Temperature",
        short_name="iat",
        unit="°F",
        category=PIDCategory.AIR_INTAKE,
        # Should be close to ambient, rising slightly under hood
        expected_at_idle="Near ambient temp",
        expected_at_load="May rise 10-20°F above ambient",
        detects_failures=[
            "iat_sensor_failure",
            "heat_soak_issue",
        ],
    ),
    
    "maf": PIDSpec(
        pid=0x10,
        name="Mass Air Flow",
        short_name="maf",
        unit="g/s",
        category=PIDCategory.AIR_INTAKE,
        # Varies greatly by engine size
        expected_at_idle="Low, steady (2-8 g/s typical for small engines)",
        expected_at_load="Proportional to load/rpm",
        related_pids=["map", "throttle_position", "rpm"],
        detects_failures=[
            "maf_sensor_dirty",
            "maf_sensor_failure",
            "air_filter_clogged",
            "air_leak_post_maf",          # MAF reads low vs actual
        ],
    ),
    
    "throttle_position": PIDSpec(
        pid=0x11,
        name="Throttle Position",
        short_name="tps",
        unit="%",
        category=PIDCategory.AIR_INTAKE,
        normal_min=0,
        normal_max=100,
        expected_at_idle="Near 0% (closed)",
        expected_at_load="Proportional to pedal input",
        detects_failures=[
            "tps_failure",
            "throttle_body_dirty",        # High idle TPS
            "throttle_body_stuck",
        ],
    ),
    
    # ----- O2 SENSORS -----
    "o2_sensor_b1s1": PIDSpec(
        pid=0x14,
        name="O2 Sensor Voltage - Bank 1 Sensor 1",
        short_name="o2_b1s1",
        unit="V",
        category=PIDCategory.EMISSIONS,
        normal_min=0.1,
        normal_max=0.9,
        expected_at_idle="Should switch between rich (>0.45V) and lean (<0.45V)",
        expected_warmup="Needs to reach operating temp before switching",
        related_pids=["short_term_fuel_trim_b1"],
        detects_failures=[
            "o2_sensor_lazy",             # Slow switching
            "o2_sensor_stuck_lean",       # Always <0.45V
            "o2_sensor_stuck_rich",       # Always >0.45V
            "exhaust_leak_before_sensor", # Erratic readings
        ],
    ),
    
    "o2_sensor_b1s2": PIDSpec(
        pid=0x15,
        name="O2 Sensor Voltage - Bank 1 Sensor 2",
        short_name="o2_b1s2",
        unit="V",
        category=PIDCategory.EMISSIONS,
        normal_min=0.1,
        normal_max=0.9,
        expected_at_idle="Should be relatively steady (post-cat)",
        related_pids=["o2_sensor_b1s1"],
        detects_failures=[
            "catalytic_converter_failure",  # Mirrors upstream sensor
            "o2_sensor_b1s2_failure",
        ],
    ),
    
    # ----- ELECTRICAL -----
    "control_module_voltage": PIDSpec(
        pid=0x42,
        name="Control Module Voltage",
        short_name="voltage",
        unit="V",
        category=PIDCategory.ELECTRICAL,
        normal_min=13.5,
        normal_max=14.7,
        expected_at_idle="Should be 13.5-14.7V with alternator charging",
        expected_at_load="Should remain stable",
        detects_failures=[
            "alternator_failure",         # Low voltage
            "voltage_regulator_failure",  # High or erratic voltage
            "battery_failing",            # May show voltage drops
        ],
    ),
    
    # ----- IGNITION -----
    "timing_advance": PIDSpec(
        pid=0x0E,
        name="Timing Advance",
        short_name="timing",
        unit="°",
        category=PIDCategory.IGNITION,
        # Varies greatly by engine, load, temp
        expected_at_idle="Relatively stable at spec",
        expected_at_load="May retard under load/knock",
        detects_failures=[
            "knock_sensor_failure",
            "timing_issue",
        ],
    ),
    
    # ----- CATALYST -----
    "catalyst_temp_b1s1": PIDSpec(
        pid=0x3C,
        name="Catalyst Temperature - Bank 1 Sensor 1",
        short_name="cat_temp_b1",
        unit="°F",
        category=PIDCategory.EMISSIONS,
        # Should reach 400-800°F during normal operation
        expected_at_idle="Should warm up and stabilize",
        expected_at_load="May rise under sustained load",
        detects_failures=[
            "catalytic_converter_degraded",
            "catalyst_overheat",
        ],
    ),
}


# =============================================================================
# DERIVED METRICS (Calculated from multiple PIDs)
# =============================================================================

@dataclass
class DerivedMetric:
    """A metric calculated from multiple PIDs."""
    name: str
    short_name: str
    formula: str                      # Human-readable formula
    input_pids: List[str]            # PIDs required to calculate
    unit: str
    normal_min: Optional[float] = None
    normal_max: Optional[float] = None
    detects_failures: List[str] = field(default_factory=list)


DERIVED_METRICS: Dict[str, DerivedMetric] = {
    "total_fuel_trim_b1": DerivedMetric(
        name="Total Fuel Trim Bank 1",
        short_name="total_ft_b1",
        formula="STFT_B1 + LTFT_B1",
        input_pids=["short_term_fuel_trim_b1", "long_term_fuel_trim_b1"],
        unit="%",
        normal_min=-15,
        normal_max=15,
        detects_failures=["fuel_system_issue"],
    ),
    
    "fuel_trim_bank_imbalance": DerivedMetric(
        name="Fuel Trim Bank Imbalance",
        short_name="ft_imbalance",
        formula="abs(STFT_B1 - STFT_B2)",
        input_pids=["short_term_fuel_trim_b1", "short_term_fuel_trim_b2"],
        unit="%",
        normal_min=0,
        normal_max=5,
        detects_failures=["bank_specific_leak", "bank_specific_injector"],
    ),
    
    "volumetric_efficiency": DerivedMetric(
        name="Volumetric Efficiency",
        short_name="ve",
        formula="(MAF * 2 * 60) / (RPM * displacement)",
        input_pids=["maf", "rpm"],
        unit="%",
        normal_min=75,
        normal_max=95,
        detects_failures=["intake_restriction", "exhaust_restriction", "cam_timing"],
    ),
    
    "warmup_rate": DerivedMetric(
        name="Coolant Warmup Rate",
        short_name="warmup_rate",
        formula="delta(coolant_temp) / delta(time)",
        input_pids=["coolant_temp"],
        unit="°F/min",
        # Should warm ~15-30°F/min in first few minutes
        normal_min=10,
        normal_max=40,
        detects_failures=["thermostat_stuck_open", "thermostat_stuck_closed"],
    ),
    
    "o2_switching_frequency": DerivedMetric(
        name="O2 Sensor Switching Frequency",
        short_name="o2_switch_freq",
        formula="count(crossings of 0.45V) per 10 seconds",
        input_pids=["o2_sensor_b1s1"],
        unit="Hz",
        normal_min=0.5,
        normal_max=3.0,
        detects_failures=["o2_sensor_lazy", "o2_sensor_stuck"],
    ),
}


# =============================================================================
# VEHICLE-SPECIFIC SPECS (Override from AutoDB/Mitchell)
# =============================================================================

@dataclass
class VehicleSpecs:
    """Vehicle-specific specifications that override universal defaults."""
    year: int
    make: str
    model: str
    engine: Optional[str] = None
    
    # Cooling
    operating_temp_min: Optional[float] = None    # °F
    operating_temp_max: Optional[float] = None    # °F
    thermostat_opens_at: Optional[float] = None   # °F
    
    # Fuel
    fuel_pressure_spec: Optional[float] = None    # kPa
    fuel_pressure_tolerance: Optional[float] = None  # ±%
    
    # Engine
    idle_rpm_spec: Optional[float] = None
    idle_rpm_tolerance: Optional[float] = None    # ±rpm
    
    # Electrical
    charging_voltage_min: Optional[float] = None
    charging_voltage_max: Optional[float] = None
    
    # Capacities (for reference)
    oil_capacity: Optional[str] = None
    coolant_capacity: Optional[str] = None
    
    # Source
    source: str = "unknown"  # "autodb", "mitchell", "manual"
    

async def get_vehicle_specs(
    year: int,
    make: str,
    model: str,
    engine: str = None,
) -> VehicleSpecs:
    """
    Get vehicle-specific specs from AutoDB (preferred) or Mitchell (fallback).
    
    AutoDB is queried first because:
    1. No rate limiting (local static HTML)
    2. 700GB+ of service manuals
    3. Fast (pure HTTP, no browser)
    
    Mitchell is used if AutoDB doesn't have the vehicle or spec.
    """
    specs = VehicleSpecs(year=year, make=make, model=model, engine=engine)
    
    # Try AutoDB first
    try:
        autodb_specs = await _query_autodb_specs(year, make, model, engine)
        if autodb_specs:
            _merge_specs(specs, autodb_specs, source="autodb")
            logger.info(f"Got specs from AutoDB for {year} {make} {model}")
    except Exception as e:
        logger.warning(f"AutoDB query failed: {e}")
    
    # Fill gaps from Mitchell if needed
    if _specs_incomplete(specs):
        try:
            mitchell_specs = await _query_mitchell_specs(year, make, model, engine)
            if mitchell_specs:
                _merge_specs(specs, mitchell_specs, source="mitchell")
                logger.info(f"Filled specs from Mitchell for {year} {make} {model}")
        except Exception as e:
            logger.warning(f"Mitchell query failed: {e}")
    
    # Fall back to universal defaults
    if specs.operating_temp_min is None:
        specs.operating_temp_min = 195
        specs.operating_temp_max = 220
        specs.source = "universal_default"
    
    return specs


async def _query_autodb_specs(year: int, make: str, model: str, engine: str = None) -> Dict[str, Any]:
    """Query AutoDB for vehicle specs via OCR."""
    try:
        from .autodb_ocr import query_autodb_specs_via_ocr
        return await query_autodb_specs_via_ocr(year, make, model, engine)
    except ImportError:
        logger.warning("autodb_ocr module not available")
        return {}
    except Exception as e:
        logger.warning(f"AutoDB OCR query failed: {e}")
        return {}


async def _query_mitchell_specs(year: int, make: str, model: str, engine: str = None) -> Dict[str, Any]:
    """Query Mitchell for vehicle specs (rate-limited!)."""
    # TODO: Implement Mitchell query with rate limiting
    # This should be used sparingly due to rate limits
    logger.debug(f"Mitchell query not yet implemented for {year} {make} {model}")
    return {}


def _merge_specs(target: VehicleSpecs, source: Dict[str, Any], source_name: str):
    """Merge source specs into target, only filling None values."""
    for field_name, value in source.items():
        if hasattr(target, field_name) and getattr(target, field_name) is None:
            setattr(target, field_name, value)
            if target.source == "unknown":
                target.source = source_name


def _specs_incomplete(specs: VehicleSpecs) -> bool:
    """Check if critical specs are still missing."""
    critical_fields = ["operating_temp_min", "idle_rpm_spec"]
    return any(getattr(specs, f) is None for f in critical_fields)


# =============================================================================
# DEVIATION DETECTION
# =============================================================================

@dataclass
class Deviation:
    """A detected deviation from normal."""
    pid_name: str
    actual_value: float
    expected_min: float
    expected_max: float
    deviation_type: str  # "high", "low", "erratic", "stuck"
    severity: float      # 0-1, how far outside normal
    possible_failures: List[str]


def detect_deviations(
    pid_values: Dict[str, float],
    vehicle_specs: VehicleSpecs = None,
) -> List[Deviation]:
    """
    Detect deviations from normal for a set of PID values.
    
    Args:
        pid_values: Dict mapping PID short_name to current value
        vehicle_specs: Optional vehicle-specific specs
        
    Returns:
        List of detected deviations
    """
    deviations = []
    
    for pid_name, value in pid_values.items():
        if pid_name not in STANDARD_PIDS:
            continue
            
        spec = STANDARD_PIDS[pid_name]
        
        # Get expected range (vehicle-specific or universal)
        expected_min = spec.normal_min
        expected_max = spec.normal_max
        
        # Override with vehicle-specific if available
        if vehicle_specs:
            if pid_name == "coolant_temp":
                if vehicle_specs.operating_temp_min:
                    expected_min = vehicle_specs.operating_temp_min
                if vehicle_specs.operating_temp_max:
                    expected_max = vehicle_specs.operating_temp_max
            elif pid_name == "rpm" and vehicle_specs.idle_rpm_spec:
                tolerance = vehicle_specs.idle_rpm_tolerance or 100
                expected_min = vehicle_specs.idle_rpm_spec - tolerance
                expected_max = vehicle_specs.idle_rpm_spec + tolerance
        
        # Skip if we don't have range info
        if expected_min is None or expected_max is None:
            continue
        
        # Check for deviation
        if value < expected_min:
            severity = (expected_min - value) / max(abs(expected_min), 1)
            deviations.append(Deviation(
                pid_name=pid_name,
                actual_value=value,
                expected_min=expected_min,
                expected_max=expected_max,
                deviation_type="low",
                severity=min(severity, 1.0),
                possible_failures=spec.detects_failures,
            ))
        elif value > expected_max:
            severity = (value - expected_max) / max(abs(expected_max), 1)
            deviations.append(Deviation(
                pid_name=pid_name,
                actual_value=value,
                expected_min=expected_min,
                expected_max=expected_max,
                deviation_type="high",
                severity=min(severity, 1.0),
                possible_failures=spec.detects_failures,
            ))
    
    return deviations


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "PIDCategory",
    "PIDSpec",
    "STANDARD_PIDS",
    "DerivedMetric",
    "DERIVED_METRICS",
    "VehicleSpecs",
    "get_vehicle_specs",
    "Deviation",
    "detect_deviations",
]
