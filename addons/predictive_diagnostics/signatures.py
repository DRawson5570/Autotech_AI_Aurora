"""
Signal Signatures for Failure Mode Detection

This module maps failure modes to observable signal patterns.
These signatures are used to:
1. Generate synthetic training data
2. Match real-time scanner data to potential faults
3. Determine which PIDs/signals to monitor

Each signature describes:
- Primary signals that directly indicate the failure
- Secondary signals that correlate with the failure
- Associated DTCs
- Threshold values for detection
"""

from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from dataclasses import dataclass, field


class SignalType(str, Enum):
    """Types of observable signals."""
    VOLTAGE = "voltage"
    CURRENT = "current"
    RESISTANCE = "resistance"
    FREQUENCY = "frequency"
    DUTY_CYCLE = "duty_cycle"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    FLOW_RATE = "flow_rate"
    POSITION = "position"
    SPEED = "speed"
    TIME = "time"
    RATIO = "ratio"


class PatternType(str, Enum):
    """Pattern types for signal behavior."""
    CONSTANT_MIN = "constant_minimum"
    CONSTANT_MAX = "constant_maximum"
    ZERO = "zero"
    VERY_LOW = "very_low"
    VERY_HIGH = "very_high"
    ERRATIC = "erratic"
    SLOW_RESPONSE = "slow_response"
    NO_RESPONSE = "no_response"
    RISING = "rising"
    FALLING = "falling"
    OSCILLATING = "oscillating"
    INTERMITTENT = "intermittent"
    NORMAL = "normal"
    OFFSET_HIGH = "offset_high"
    OFFSET_LOW = "offset_low"
    INVERTED = "inverted"
    STUCK = "stuck"
    DROPPING = "dropping"


@dataclass
class SignalPattern:
    """Describes an expected pattern for a signal."""
    signal_name: str              # Generic name like "{sensor}_output" or specific like "MAP_sensor"
    signal_type: SignalType
    pattern: PatternType
    threshold_low: Optional[float] = None
    threshold_high: Optional[float] = None
    unit: Optional[str] = None
    description: str = ""
    
    def matches(self, value: float, context: Dict[str, float] = None) -> Tuple[bool, float]:
        """
        Check if a value matches this pattern.
        Returns (matches, confidence) where confidence is 0.0 to 1.0
        """
        if self.pattern == PatternType.ZERO:
            if abs(value) < 0.1:
                return True, 0.95
            elif abs(value) < 1.0:
                return True, 0.7
            return False, 0.0
            
        elif self.pattern == PatternType.VERY_LOW:
            if self.threshold_low is not None and value < self.threshold_low:
                return True, 0.9
            return False, 0.0
            
        elif self.pattern == PatternType.VERY_HIGH:
            if self.threshold_high is not None and value > self.threshold_high:
                return True, 0.9
            return False, 0.0
            
        elif self.pattern == PatternType.CONSTANT_MIN:
            # Would need historical data to detect "constant"
            if self.threshold_low is not None and value <= self.threshold_low:
                return True, 0.8
            return False, 0.0
            
        elif self.pattern == PatternType.CONSTANT_MAX:
            if self.threshold_high is not None and value >= self.threshold_high:
                return True, 0.8
            return False, 0.0
            
        # Default: can't evaluate pattern without more context
        return False, 0.0


@dataclass
class FailureSignature:
    """Complete signature for identifying a failure mode."""
    failure_mode_id: str
    primary_signals: List[SignalPattern]
    secondary_signals: List[SignalPattern] = field(default_factory=list)
    associated_dtcs: List[str] = field(default_factory=list)  # Regex patterns for DTC matching
    diagnostic_test: str = ""
    confidence_base: float = 0.5  # Base confidence when primary signals match
    
    def calculate_match_score(
        self, 
        signal_values: Dict[str, float],
        active_dtcs: List[str] = None
    ) -> Tuple[float, List[str]]:
        """
        Calculate how well the observed signals match this signature.
        Returns (score, evidence) where score is 0.0 to 1.0.
        """
        evidence = []
        total_score = 0.0
        total_weight = 0.0
        
        # Check primary signals (weighted more heavily)
        for pattern in self.primary_signals:
            weight = 2.0  # Primary signals count double
            signal_key = pattern.signal_name.lower()
            
            # Try to find matching signal in values
            matched_value = None
            for key, value in signal_values.items():
                if signal_key in key.lower() or key.lower() in signal_key:
                    matched_value = value
                    break
            
            if matched_value is not None:
                matches, confidence = pattern.matches(matched_value)
                if matches:
                    total_score += weight * confidence
                    evidence.append(f"Primary: {pattern.signal_name} = {matched_value} matches {pattern.pattern.value}")
                total_weight += weight
        
        # Check secondary signals
        for pattern in self.secondary_signals:
            weight = 1.0
            signal_key = pattern.signal_name.lower()
            
            matched_value = None
            for key, value in signal_values.items():
                if signal_key in key.lower() or key.lower() in signal_key:
                    matched_value = value
                    break
            
            if matched_value is not None:
                matches, confidence = pattern.matches(matched_value)
                if matches:
                    total_score += weight * confidence
                    evidence.append(f"Secondary: {pattern.signal_name} = {matched_value} matches {pattern.pattern.value}")
                total_weight += weight
        
        # Check DTCs (strong evidence)
        if active_dtcs:
            import re
            for dtc_pattern in self.associated_dtcs:
                for dtc in active_dtcs:
                    if re.match(dtc_pattern, dtc):
                        total_score += 3.0  # DTCs are strong evidence
                        total_weight += 3.0
                        evidence.append(f"DTC match: {dtc} matches pattern {dtc_pattern}")
                        break
        
        # Normalize score
        final_score = total_score / total_weight if total_weight > 0 else 0.0
        
        # Apply base confidence
        final_score = self.confidence_base + (1 - self.confidence_base) * final_score
        
        return min(1.0, final_score), evidence


# =============================================================================
# FAILURE SIGNATURES DATABASE
# =============================================================================

FAILURE_SIGNATURES: Dict[str, FailureSignature] = {
    
    # -------------------------------------------------------------------------
    # SENSOR SIGNATURES
    # -------------------------------------------------------------------------
    
    "sensor_stuck_low": FailureSignature(
        failure_mode_id="sensor_stuck_low",
        primary_signals=[
            SignalPattern(
                signal_name="{sensor}_output",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.CONSTANT_MIN,
                threshold_low=0.1,
                unit="V",
                description="Signal stuck at minimum (near 0V)"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="{sensor}_supply",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.NORMAL,
                threshold_low=4.8,
                threshold_high=5.2,
                unit="V",
                description="Supply voltage should be normal"
            ),
        ],
        associated_dtcs=[
            r"P0\d{2}[0-7]",  # Various sensor low circuit codes
            r"P0\d{3}.*low",
            r"P0\d{3}.*range.*low",
        ],
        diagnostic_test="Verify supply voltage present. Apply known stimulus to sensor. "
                       "If no response, sensor or signal wire is bad.",
        confidence_base=0.6,
    ),
    
    "sensor_stuck_high": FailureSignature(
        failure_mode_id="sensor_stuck_high",
        primary_signals=[
            SignalPattern(
                signal_name="{sensor}_output",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.CONSTANT_MAX,
                threshold_high=4.9,
                unit="V",
                description="Signal stuck at maximum (near 5V reference)"
            ),
        ],
        associated_dtcs=[
            r"P0\d{2}[89]",  # Various sensor high circuit codes
            r"P0\d{3}.*high",
            r"P0\d{3}.*range.*high",
        ],
        diagnostic_test="Disconnect sensor - if signal drops, sensor is shorted internally. "
                       "If signal stays high, short to voltage in wiring.",
        confidence_base=0.6,
    ),
    
    "sensor_erratic": FailureSignature(
        failure_mode_id="sensor_erratic",
        primary_signals=[
            SignalPattern(
                signal_name="{sensor}_output",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.ERRATIC,
                description="Signal jumping randomly"
            ),
        ],
        associated_dtcs=[
            r"P0\d{3}.*intermittent",
            r"P0\d{3}.*erratic",
        ],
        diagnostic_test="Check connector for corrosion or looseness. Wiggle test wiring. "
                       "Check for electromagnetic interference sources.",
        confidence_base=0.5,
    ),
    
    "sensor_open": FailureSignature(
        failure_mode_id="sensor_open",
        primary_signals=[
            SignalPattern(
                signal_name="{sensor}_output",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.CONSTANT_MAX,  # Open = pulled high by ECU
                threshold_high=4.9,
                description="Open circuit shows as high voltage (internal pullup)"
            ),
        ],
        associated_dtcs=[
            r"P0\d{3}.*open",
            r"P0\d{3}.*circuit",
        ],
        diagnostic_test="Check continuity from ECU to sensor. Verify connector engagement. "
                       "Measure resistance of sensor (should not be infinite).",
        confidence_base=0.7,
    ),
    
    # -------------------------------------------------------------------------
    # RELAY SIGNATURES
    # -------------------------------------------------------------------------
    
    "relay_coil_open": FailureSignature(
        failure_mode_id="relay_coil_open",
        primary_signals=[
            SignalPattern(
                signal_name="{relay}_coil_current",
                signal_type=SignalType.CURRENT,
                pattern=PatternType.ZERO,
                threshold_low=0.01,
                unit="A",
                description="No current through coil"
            ),
            SignalPattern(
                signal_name="{controlled_load}_status",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.ZERO,
                description="Load never receives power"
            ),
        ],
        diagnostic_test="Apply 12V directly to relay coil terminals. "
                       "No click = coil open. Measure coil resistance (should be 50-100Ω).",
        confidence_base=0.6,
    ),
    
    "relay_contacts_welded": FailureSignature(
        failure_mode_id="relay_contacts_welded",
        primary_signals=[
            SignalPattern(
                signal_name="{controlled_load}_status",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.STUCK,
                threshold_high=11.0,
                description="Load always has power even when command is off"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="battery_drain",
                signal_type=SignalType.CURRENT,
                pattern=PatternType.VERY_HIGH,
                threshold_high=0.5,
                unit="A",
                description="Parasitic draw from stuck-on load"
            ),
        ],
        diagnostic_test="Remove relay. If load stops, relay contacts were welded. "
                       "If load still runs, there's a wiring bypass.",
        confidence_base=0.7,
    ),
    
    "relay_contacts_pitted": FailureSignature(
        failure_mode_id="relay_contacts_pitted",
        primary_signals=[
            SignalPattern(
                signal_name="{relay}_voltage_drop",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.VERY_HIGH,
                threshold_high=0.5,
                unit="V",
                description="Excessive voltage drop across relay contacts"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="{controlled_load}_performance",
                signal_type=SignalType.RATIO,
                pattern=PatternType.OFFSET_LOW,
                description="Load operates but weaker than normal"
            ),
        ],
        diagnostic_test="Measure voltage drop across relay contacts under load. "
                       "Should be <0.2V. Higher indicates contact resistance.",
        confidence_base=0.5,
    ),
    
    # -------------------------------------------------------------------------
    # MOTOR/PUMP SIGNATURES
    # -------------------------------------------------------------------------
    
    "motor_open_winding": FailureSignature(
        failure_mode_id="motor_open_winding",
        primary_signals=[
            SignalPattern(
                signal_name="{motor}_current",
                signal_type=SignalType.CURRENT,
                pattern=PatternType.ZERO,
                threshold_low=0.05,
                unit="A",
                description="Motor draws no current"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="{pumped_fluid}_pressure",
                signal_type=SignalType.PRESSURE,
                pattern=PatternType.DROPPING,
                description="System pressure falling (if pump-related)"
            ),
        ],
        diagnostic_test="Measure resistance across motor terminals. "
                       "Should be a few ohms, not infinite. Check for 12V at motor.",
        confidence_base=0.7,
    ),
    
    "motor_seized": FailureSignature(
        failure_mode_id="motor_seized",
        primary_signals=[
            SignalPattern(
                signal_name="{motor}_current",
                signal_type=SignalType.CURRENT,
                pattern=PatternType.VERY_HIGH,
                threshold_high=10.0,  # Stall current
                unit="A",
                description="Motor draws stall current (locked rotor)"
            ),
        ],
        associated_dtcs=[
            r".*motor.*overcurrent",
            r".*pump.*fault",
        ],
        diagnostic_test="Disconnect motor and try to rotate shaft by hand. "
                       "If seized, inspect for bearing failure or contamination.",
        confidence_base=0.7,
    ),
    
    "motor_weak": FailureSignature(
        failure_mode_id="motor_weak",
        primary_signals=[
            SignalPattern(
                signal_name="{motor}_current",
                signal_type=SignalType.CURRENT,
                pattern=PatternType.VERY_LOW,
                unit="A",
                description="Motor draws less current than spec"
            ),
            SignalPattern(
                signal_name="{motor}_speed",
                signal_type=SignalType.SPEED,
                pattern=PatternType.OFFSET_LOW,
                description="Motor runs slower than normal"
            ),
        ],
        diagnostic_test="Check supply voltage at motor under load. "
                       "Check for voltage drop in wiring. Inspect brushes if accessible.",
        confidence_base=0.5,
    ),
    
    # -------------------------------------------------------------------------
    # CONNECTOR/WIRING SIGNATURES
    # -------------------------------------------------------------------------
    
    "connector_high_resistance": FailureSignature(
        failure_mode_id="connector_high_resistance",
        primary_signals=[
            SignalPattern(
                signal_name="{connector}_voltage_drop",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.VERY_HIGH,
                threshold_high=0.5,
                unit="V",
                description="Voltage drop across connector exceeds 0.5V"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="{connector}_temperature",
                signal_type=SignalType.TEMPERATURE,
                pattern=PatternType.VERY_HIGH,
                description="Connector warm/hot due to I²R heating"
            ),
            SignalPattern(
                signal_name="{load}_performance",
                signal_type=SignalType.RATIO,
                pattern=PatternType.OFFSET_LOW,
                description="Load runs but with reduced performance"
            ),
        ],
        diagnostic_test="Voltage drop test across connector under load. "
                       ">0.5V indicates high resistance. Inspect terminals for corrosion.",
        confidence_base=0.6,
    ),
    
    "connector_open": FailureSignature(
        failure_mode_id="connector_open",
        primary_signals=[
            SignalPattern(
                signal_name="{circuit}_continuity",
                signal_type=SignalType.RESISTANCE,
                pattern=PatternType.VERY_HIGH,
                description="No continuity through connector"
            ),
        ],
        associated_dtcs=[
            r"P0\d{3}.*open",
            r".*circuit.*open",
        ],
        diagnostic_test="Continuity check through connector. "
                       "Wiggle test while checking. Inspect for backed-out terminal.",
        confidence_base=0.7,
    ),
    
    "connector_intermittent": FailureSignature(
        failure_mode_id="connector_intermittent",
        primary_signals=[
            SignalPattern(
                signal_name="{circuit}_signal",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.INTERMITTENT,
                description="Signal drops out intermittently"
            ),
        ],
        associated_dtcs=[
            r".*intermittent",
        ],
        diagnostic_test="Wiggle test connector while monitoring signal. "
                       "Tap test harness. Check during road test over bumps.",
        confidence_base=0.4,  # Hard to diagnose with certainty
    ),
    
    "wiring_short_ground": FailureSignature(
        failure_mode_id="wiring_short_ground",
        primary_signals=[
            SignalPattern(
                signal_name="{wire}_to_ground",
                signal_type=SignalType.RESISTANCE,
                pattern=PatternType.ZERO,
                description="Wire shows continuity to ground"
            ),
            SignalPattern(
                signal_name="{circuit}_voltage",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.ZERO,
                description="Circuit voltage at 0V"
            ),
        ],
        associated_dtcs=[
            r"P0\d{3}.*low",
            r".*short.*ground",
        ],
        diagnostic_test="Disconnect both ends of wire. "
                       "Check isolation to ground. Inspect for chafing.",
        confidence_base=0.7,
    ),

    # Tesla / EV HV isolation signature
    "tesla_hv_isolation_fault": FailureSignature(
        failure_mode_id="tesla_hv_isolation_fault",
        primary_signals=[
            SignalPattern(
                signal_name="insulation_resistance",
                signal_type=SignalType.RESISTANCE,
                pattern=PatternType.VERY_LOW,
                threshold_low=1.0,
                unit="MOhm",
                description="Insulation resistance between HV rails and chassis (MΩ)"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="hv_voltage",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.OFFSET_LOW,
                description="HV system voltage abnormal or missing"
            ),
        ],
        associated_dtcs=[
            r"BMS_f035",
            r"BMS_u018",
            r".*iso.*",
            r"P0AA1",
        ],
        diagnostic_test="Use 1kV insulation tester (megohmmeter) to measure resistance to chassis. "
                       "Sequentially disconnect suspect modules (PTC heater, drive unit) and re-test.",
        confidence_base=0.8,
    ),
    
    # -------------------------------------------------------------------------
    # IGNITION SYSTEM SIGNATURES
    # -------------------------------------------------------------------------
    
    "coil_open_primary": FailureSignature(
        failure_mode_id="coil_open_primary",
        primary_signals=[
            SignalPattern(
                signal_name="{coil}_primary_resistance",
                signal_type=SignalType.RESISTANCE,
                pattern=PatternType.VERY_HIGH,
                description="Primary winding resistance infinite"
            ),
            SignalPattern(
                signal_name="{cylinder}_spark",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.ZERO,
                description="No spark on this cylinder"
            ),
        ],
        associated_dtcs=[
            r"P030[0-9]",  # Misfire codes
            r"P035[0-9]",  # Ignition coil codes
        ],
        diagnostic_test="Measure primary resistance (typically 0.5-2Ω). "
                       "Infinite = open. Swap with known-good coil to verify.",
        confidence_base=0.7,
    ),
    
    "coil_weak": FailureSignature(
        failure_mode_id="coil_weak",
        primary_signals=[
            SignalPattern(
                signal_name="{cylinder}_spark_intensity",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.OFFSET_LOW,
                description="Weak spark (orange instead of blue)"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="{cylinder}_misfire_rate",
                signal_type=SignalType.RATIO,
                pattern=PatternType.VERY_HIGH,
                threshold_high=0.02,  # 2% misfire rate
                description="Misfire rate elevated under load"
            ),
        ],
        associated_dtcs=[
            r"P030[0-9]",  # Misfire codes
        ],
        diagnostic_test="Use spark tester rated for COP systems. "
                       "Compare spark intensity to known-good cylinder.",
        confidence_base=0.5,
    ),
    
    # -------------------------------------------------------------------------
    # FUEL SYSTEM SIGNATURES
    # -------------------------------------------------------------------------
    
    "injector_clogged": FailureSignature(
        failure_mode_id="injector_clogged",
        primary_signals=[
            SignalPattern(
                signal_name="{cylinder}_fuel_trim",
                signal_type=SignalType.RATIO,
                pattern=PatternType.VERY_HIGH,
                threshold_high=15.0,
                unit="%",
                description="High fuel trim indicating lean condition"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="{cylinder}_O2_voltage",
                signal_type=SignalType.VOLTAGE,
                pattern=PatternType.OFFSET_LOW,
                description="O2 sensor showing lean"
            ),
        ],
        associated_dtcs=[
            r"P017[0-5]",  # Fuel trim codes
            r"P0300",      # Random misfire (often clogged injector)
        ],
        diagnostic_test="Injector balance test or flow test. "
                       "Compare fuel delivery rate between cylinders.",
        confidence_base=0.5,
    ),
    
    "injector_leaking": FailureSignature(
        failure_mode_id="injector_leaking",
        primary_signals=[
            SignalPattern(
                signal_name="{cylinder}_fuel_trim",
                signal_type=SignalType.RATIO,
                pattern=PatternType.VERY_LOW,
                threshold_low=-10.0,
                unit="%",
                description="Negative fuel trim indicating rich"
            ),
        ],
        secondary_signals=[
            SignalPattern(
                signal_name="fuel_pressure_decay",
                signal_type=SignalType.PRESSURE,
                pattern=PatternType.DROPPING,
                description="Fuel pressure drops with engine off"
            ),
        ],
        associated_dtcs=[
            r"P017[0-5]",  # Fuel trim codes
            r"P0172",      # System too rich
        ],
        diagnostic_test="Fuel pressure leak-down test with key off. "
                       "Pressure should hold for several minutes.",
        confidence_base=0.6,
    ),
    
    "injector_stuck_open": FailureSignature(
        failure_mode_id="injector_stuck_open",
        primary_signals=[
            SignalPattern(
                signal_name="{cylinder}_fuel_delivery",
                signal_type=SignalType.RATIO,
                pattern=PatternType.VERY_HIGH,
                description="Cylinder receives fuel continuously"
            ),
        ],
        associated_dtcs=[
            r"P0172",  # System too rich
            r"P030[1-8]",  # Cylinder-specific misfire
        ],
        diagnostic_test="WARNING: Hydro-lock risk. Disable injector and check for improvement. "
                       "Inspect for fuel in oil.",
        confidence_base=0.8,  # Serious issue, diagnose quickly
    ),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_signature(failure_mode_id: str) -> Optional[FailureSignature]:
    """Get signature for a failure mode."""
    return FAILURE_SIGNATURES.get(failure_mode_id)


def get_signatures_for_dtc(dtc_code: str) -> List[FailureSignature]:
    """Find all signatures that might match a DTC."""
    import re
    matches = []
    for sig in FAILURE_SIGNATURES.values():
        for dtc_pattern in sig.associated_dtcs:
            if re.match(dtc_pattern, dtc_code, re.IGNORECASE):
                matches.append(sig)
                break
    return matches


def get_signals_to_monitor(failure_mode_id: str) -> List[str]:
    """Get list of signals that should be monitored to detect a failure mode."""
    sig = get_signature(failure_mode_id)
    if not sig:
        return []
    
    signals = []
    for pattern in sig.primary_signals + sig.secondary_signals:
        signals.append(pattern.signal_name)
    return signals


def substitute_component(signature: FailureSignature, component_name: str) -> FailureSignature:
    """
    Create a copy of signature with component name substituted into placeholders.
    Replaces {sensor}, {motor}, {relay}, etc. with actual component name.
    """
    import copy
    new_sig = copy.deepcopy(signature)
    
    for pattern in new_sig.primary_signals + new_sig.secondary_signals:
        pattern.signal_name = pattern.signal_name.replace("{sensor}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{motor}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{pump}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{relay}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{valve}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{connector}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{wire}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{circuit}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{coil}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{cylinder}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{controlled_load}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{pumped_fluid}", component_name)
        pattern.signal_name = pattern.signal_name.replace("{load}", component_name)
    
    return new_sig
