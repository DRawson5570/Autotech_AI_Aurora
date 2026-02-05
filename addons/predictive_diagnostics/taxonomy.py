"""
Component Failure Taxonomy Database

This module contains the universal taxonomy of how automotive components fail.
Built from first principles - these failure modes apply regardless of vehicle
make/model. When combined with vehicle-specific wiring diagrams and specs,
we can generate complete fault trees.

The taxonomy is organized by component type, with each type having a set of
applicable failure modes. Each failure mode describes:
- What physically happens
- Observable symptoms
- Diagnostic approach
"""

from typing import Dict, List, Set
from enum import Enum


class ComponentType(str, Enum):
    """Categories of automotive components."""
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    RELAY = "relay"
    FUSE = "fuse"
    MOTOR = "motor"
    PUMP = "pump"
    VALVE = "valve"
    CONNECTOR = "connector"
    WIRING = "wiring"
    ECU = "ecu"
    BEARING = "bearing"
    SEAL = "seal"
    SWITCH = "switch"
    CAPACITOR = "capacitor"
    RESISTOR = "resistor"
    COIL = "coil"
    SOLENOID = "solenoid"
    BATTERY = "battery"
    ALTERNATOR = "alternator"
    STARTER = "starter"
    IGNITION_COIL = "ignition_coil"
    SPARK_PLUG = "spark_plug"
    FUEL_INJECTOR = "fuel_injector"
    THROTTLE_BODY = "throttle_body"


class FailureMode:
    """Represents a specific failure mode with its characteristics."""
    
    def __init__(
        self,
        id: str,
        name: str,
        description: str,
        symptoms: List[str],
        diagnostic_approach: str,
        common_causes: List[str] = None,
        severity: str = "medium"
    ):
        self.id = id
        self.name = name
        self.description = description
        self.symptoms = symptoms
        self.diagnostic_approach = diagnostic_approach
        self.common_causes = common_causes or []
        self.severity = severity  # critical, high, medium, low


# =============================================================================
# SENSOR FAILURE MODES
# =============================================================================

SENSOR_FAILURES: Dict[str, FailureMode] = {
    "stuck_low": FailureMode(
        id="sensor_stuck_low",
        name="Stuck Low",
        description="Sensor output remains at minimum value regardless of actual condition",
        symptoms=[
            "Signal constant at minimum",
            "DTC for circuit low/range low",
            "Related system malfunction due to wrong reading"
        ],
        diagnostic_approach="Verify sensor receives correct supply voltage and ground. "
                          "Apply known stimulus and check for response.",
        common_causes=["Open in signal wire", "Ground fault", "Sensor element failure"],
        severity="high"
    ),
    
    "stuck_high": FailureMode(
        id="sensor_stuck_high",
        name="Stuck High",
        description="Sensor output remains at maximum value regardless of actual condition",
        symptoms=[
            "Signal constant at maximum",
            "DTC for circuit high/range high",
            "Related system malfunction"
        ],
        diagnostic_approach="Disconnect sensor - signal should change. If still high, "
                          "check for short to voltage in wiring.",
        common_causes=["Short to voltage", "Internal sensor failure", "Reference voltage issue"],
        severity="high"
    ),
    
    "erratic": FailureMode(
        id="sensor_erratic",
        name="Erratic Signal",
        description="Sensor output jumps randomly or has noise beyond normal range",
        symptoms=[
            "Intermittent DTCs",
            "Erratic system behavior",
            "Signal noise visible on scope"
        ],
        diagnostic_approach="Check connector integrity, look for chafed wiring, "
                          "verify shielding on sensitive circuits.",
        common_causes=["Loose connector", "Chafed wire", "EMI interference", "Failing sensor"],
        severity="medium"
    ),
    
    "slow_response": FailureMode(
        id="sensor_slow_response",
        name="Slow Response",
        description="Sensor responds to changes but with significant delay",
        symptoms=[
            "Sluggish system response",
            "May not set DTC",
            "Poor driveability"
        ],
        diagnostic_approach="Compare response time to known-good sensor. "
                          "Check for contamination or degradation.",
        common_causes=["Sensor aging", "Contamination", "Thermal damage"],
        severity="medium"
    ),
    
    "offset_drift": FailureMode(
        id="sensor_offset_drift",
        name="Offset/Drift",
        description="Sensor reading has consistent offset from actual value",
        symptoms=[
            "System runs but not optimally",
            "May not set DTC if within range",
            "Fuel economy or performance issues"
        ],
        diagnostic_approach="Compare sensor reading to known accurate measurement. "
                          "Check for calibration drift.",
        common_causes=["Age", "Thermal cycling", "Contamination", "Physical damage"],
        severity="medium"
    ),
    
    "open_circuit": FailureMode(
        id="sensor_open",
        name="Open Circuit",
        description="Complete loss of electrical continuity in sensor circuit",
        symptoms=[
            "No signal",
            "DTC for open circuit",
            "System uses default/limp values"
        ],
        diagnostic_approach="Check continuity from ECU to sensor. Verify connector engagement.",
        common_causes=["Broken wire", "Connector disconnected", "Internal sensor failure"],
        severity="high"
    ),
    
    "short_to_ground": FailureMode(
        id="sensor_short_ground",
        name="Short to Ground",
        description="Signal wire shorted to chassis ground",
        symptoms=[
            "Signal at 0V or very low",
            "DTC for circuit low",
            "May damage ECU driver"
        ],
        diagnostic_approach="Disconnect sensor and check signal wire isolation to ground. "
                          "Inspect harness for chafing.",
        common_causes=["Chafed insulation", "Water intrusion", "Pinched wire"],
        severity="high"
    ),
    
    "short_to_power": FailureMode(
        id="sensor_short_power",
        name="Short to Power",
        description="Signal wire shorted to voltage source",
        symptoms=[
            "Signal at supply voltage",
            "DTC for circuit high",
            "Possible ECU damage"
        ],
        diagnostic_approach="Disconnect sensor - if signal still high, short is in harness. "
                          "Check for melted/crossed wires.",
        common_causes=["Melted insulation", "Crossed wires", "Connector damage"],
        severity="critical"
    ),
}


# =============================================================================
# RELAY FAILURE MODES
# =============================================================================

RELAY_FAILURES: Dict[str, FailureMode] = {
    "coil_open": FailureMode(
        id="relay_coil_open",
        name="Coil Open",
        description="Relay coil has open circuit, cannot energize",
        symptoms=[
            "No click when commanded",
            "Controlled load never activates",
            "Coil resistance infinite"
        ],
        diagnostic_approach="Apply 12V directly to coil terminals. If no click, coil is open. "
                          "Measure coil resistance (should be 50-100Ω typically).",
        common_causes=["Thermal damage", "Coil burnout from over-voltage", "Manufacturing defect"],
        severity="high"
    ),
    
    "coil_short": FailureMode(
        id="relay_coil_short",
        name="Coil Shorted",
        description="Relay coil has short circuit, draws excessive current",
        symptoms=[
            "Blown fuse on control circuit",
            "Coil gets very hot",
            "Very low coil resistance"
        ],
        diagnostic_approach="Measure coil resistance - if near zero, coil is shorted. "
                          "Check if control fuse blows immediately.",
        common_causes=["Insulation breakdown", "Overheating", "Age"],
        severity="high"
    ),
    
    "contacts_welded": FailureMode(
        id="relay_contacts_welded",
        name="Contacts Welded",
        description="Relay contacts are fused together, load always on",
        symptoms=[
            "Load runs continuously even with key off",
            "Parasitic battery drain",
            "Relay doesn't click off"
        ],
        diagnostic_approach="Remove relay - if load still runs (shouldn't without relay), "
                          "wiring bypass. If load stops, relay contacts were welded.",
        common_causes=["High inrush current", "Contactor arcing", "Overload"],
        severity="critical"
    ),
    
    "contacts_pitted": FailureMode(
        id="relay_contacts_pitted",
        name="Contacts Pitted/Corroded",
        description="Relay contacts have high resistance from wear or corrosion",
        symptoms=[
            "Intermittent load operation",
            "Voltage drop across relay contacts",
            "Load works sometimes"
        ],
        diagnostic_approach="Measure voltage drop across relay contacts under load. "
                          "Should be <0.2V. Higher indicates contact resistance.",
        common_causes=["Normal wear", "Arcing damage", "Moisture intrusion"],
        severity="medium"
    ),
    
    "contacts_open": FailureMode(
        id="relay_contacts_open",
        name="Contacts Open/Failed",
        description="Relay contacts don't close even when coil is energized",
        symptoms=[
            "Relay clicks but load doesn't run",
            "Coil energizes (can measure)",
            "No continuity through contacts"
        ],
        diagnostic_approach="Verify coil energizes (click or ammeter). "
                          "Check contact continuity when energized - should be <1Ω.",
        common_causes=["Mechanical failure", "Contact spring broken", "Severe pitting"],
        severity="high"
    ),
}


# =============================================================================
# MOTOR/PUMP FAILURE MODES
# =============================================================================

MOTOR_FAILURES: Dict[str, FailureMode] = {
    "open_winding": FailureMode(
        id="motor_open_winding",
        name="Open Winding",
        description="Motor winding has break, no current flow possible",
        symptoms=[
            "Motor doesn't run",
            "Zero current draw",
            "Infinite resistance between terminals"
        ],
        diagnostic_approach="Measure resistance across motor terminals. "
                          "Should be a few ohms, not infinite.",
        common_causes=["Thermal damage", "Vibration fatigue", "Manufacturing defect"],
        severity="high"
    ),
    
    "shorted_winding": FailureMode(
        id="motor_shorted_winding",
        name="Shorted Winding",
        description="Motor winding has internal short, draws excessive current",
        symptoms=[
            "Motor runs hot",
            "Blows fuse or trips breaker",
            "Very low resistance"
        ],
        diagnostic_approach="Measure resistance - should match spec. "
                          "Too low = shorted. Check current draw.",
        common_causes=["Overheating", "Insulation breakdown", "Contamination"],
        severity="critical"
    ),
    
    "seized": FailureMode(
        id="motor_seized",
        name="Mechanically Seized",
        description="Motor shaft cannot rotate due to mechanical binding",
        symptoms=[
            "Motor hums but doesn't spin",
            "Very high current (stall current)",
            "Fuse may blow quickly"
        ],
        diagnostic_approach="Disconnect motor and try to rotate by hand. "
                          "Should turn freely. Listen for grinding.",
        common_causes=["Bearing failure", "Contamination", "Corrosion", "Lack of lubrication"],
        severity="high"
    ),
    
    "worn_brushes": FailureMode(
        id="motor_worn_brushes",
        name="Worn Brushes",
        description="Motor brushes worn, intermittent contact with commutator",
        symptoms=[
            "Intermittent operation",
            "Motor works if tapped",
            "Sparking visible in some cases"
        ],
        diagnostic_approach="If accessible, inspect brushes for wear. "
                          "Minimum brush length typically 5mm.",
        common_causes=["Normal wear", "High use", "Contamination accelerating wear"],
        severity="medium"
    ),
    
    "weak_output": FailureMode(
        id="motor_weak",
        name="Weak Output",
        description="Motor runs but with reduced power/speed",
        symptoms=[
            "Slow operation",
            "May not reach full speed",
            "Reduced system performance"
        ],
        diagnostic_approach="Check supply voltage at motor. Check current vs spec. "
                          "Verify mechanical freedom.",
        common_causes=["Voltage drop in circuit", "Partial short", "Bearing drag", "Age"],
        severity="medium"
    ),
}


# =============================================================================
# VALVE/SOLENOID FAILURE MODES
# =============================================================================

VALVE_FAILURES: Dict[str, FailureMode] = {
    "stuck_open": FailureMode(
        id="valve_stuck_open",
        name="Stuck Open",
        description="Valve remains open regardless of command",
        symptoms=[
            "Flow when there shouldn't be",
            "System pressure/flow abnormal",
            "Related DTCs for system performance"
        ],
        diagnostic_approach="Command valve closed and verify no flow. "
                          "May need to apply direct power to solenoid.",
        common_causes=["Debris preventing closure", "Mechanical damage", "Solenoid failure"],
        severity="high"
    ),
    
    "stuck_closed": FailureMode(
        id="valve_stuck_closed",
        name="Stuck Closed",
        description="Valve remains closed regardless of command",
        symptoms=[
            "No flow when commanded open",
            "System starved for fluid/air",
            "Performance DTCs"
        ],
        diagnostic_approach="Command valve open, verify flow. "
                          "Listen for solenoid click, check for debris blockage.",
        common_causes=["Debris blockage", "Solenoid coil failure", "Mechanical binding"],
        severity="high"
    ),
    
    "leaking": FailureMode(
        id="valve_leaking",
        name="Leaking Past Seat",
        description="Valve doesn't seal completely when closed",
        symptoms=[
            "Some flow even when closed",
            "Gradual pressure loss",
            "Reduced system efficiency"
        ],
        diagnostic_approach="Check for flow/pressure change when valve should be sealed. "
                          "May need to remove and inspect seat.",
        common_causes=["Debris on seat", "Worn seal", "Corrosion"],
        severity="medium"
    ),
    
    "slow_response": FailureMode(
        id="valve_slow",
        name="Slow Response",
        description="Valve operates but with delay",
        symptoms=[
            "Sluggish system response",
            "May cause hunting/oscillation",
            "Timing-related DTCs"
        ],
        diagnostic_approach="Time valve response vs spec. "
                          "Check solenoid resistance and mechanical freedom.",
        common_causes=["Contamination", "Weak solenoid", "Sticky mechanism"],
        severity="medium"
    ),
}


# =============================================================================
# CONNECTOR/WIRING FAILURE MODES
# =============================================================================

CONNECTOR_FAILURES: Dict[str, FailureMode] = {
    "high_resistance": FailureMode(
        id="connector_high_resistance",
        name="High Resistance",
        description="Connector has excessive resistance causing voltage drop",
        symptoms=[
            "Voltage at load lower than source",
            "Connector may feel warm",
            "Intermittent or weak operation"
        ],
        diagnostic_approach="Voltage drop test across connector under load. "
                          ">0.5V indicates problem. Inspect terminals.",
        common_causes=["Corrosion", "Loose terminal", "Terminal damage", "Water intrusion"],
        severity="medium"
    ),
    
    "open": FailureMode(
        id="connector_open",
        name="Open Circuit",
        description="No electrical continuity through connector",
        symptoms=[
            "Complete loss of function",
            "Open circuit DTC",
            "May be intermittent if partially connected"
        ],
        diagnostic_approach="Continuity check through connector. "
                          "Wiggle test while checking continuity.",
        common_causes=["Backed-out terminal", "Broken wire at terminal", "Disconnected"],
        severity="high"
    ),
    
    "intermittent": FailureMode(
        id="connector_intermittent",
        name="Intermittent Connection",
        description="Connection makes and breaks randomly",
        symptoms=[
            "Random system behavior",
            "Intermittent DTCs",
            "Problems when driving over bumps"
        ],
        diagnostic_approach="Wiggle test connectors while monitoring circuit. "
                          "Look for thermal cycling issues.",
        common_causes=["Loose connector", "Corroded terminal", "Damaged locking tab"],
        severity="medium"
    ),
}


WIRING_FAILURES: Dict[str, FailureMode] = {
    "open": FailureMode(
        id="wiring_open",
        name="Open Wire",
        description="Wire has break, no continuity",
        symptoms=[
            "Circuit doesn't work",
            "Open circuit DTC",
            "No continuity end-to-end"
        ],
        diagnostic_approach="Check continuity along wire. Use divide-and-conquer "
                          "to locate break point.",
        common_causes=["Chafing through", "Connector pull-out", "Physical damage"],
        severity="high"
    ),
    
    "short_to_ground": FailureMode(
        id="wiring_short_ground",
        name="Short to Ground",
        description="Wire insulation breached, contacting chassis ground",
        symptoms=[
            "Circuit low DTC",
            "Blown fuse on power circuits",
            "Signal reads minimum"
        ],
        diagnostic_approach="Disconnect both ends, check wire isolation to ground. "
                          "Inspect routing for chafe points.",
        common_causes=["Chafed insulation", "Pinched wire", "Rodent damage"],
        severity="high"
    ),
    
    "short_to_power": FailureMode(
        id="wiring_short_power",
        name="Short to Power",
        description="Wire contacting voltage source through insulation breach",
        symptoms=[
            "Signal reads high",
            "Unexpected voltage on circuit",
            "Possible smoke/damage"
        ],
        diagnostic_approach="Disconnect both ends, check for voltage on wire. "
                          "Look for crossed/melted wires.",
        common_causes=["Melted harness", "Crossed wires", "Improper repair"],
        severity="critical"
    ),
    
    "chafed": FailureMode(
        id="wiring_chafed",
        name="Chafed Insulation",
        description="Wire insulation worn but not yet shorted",
        symptoms=[
            "Intermittent faults",
            "May have voltage leak to nearby circuits",
            "Visual damage if inspected"
        ],
        diagnostic_approach="Visual inspection of harness, especially at routing "
                          "points, grommets, and sharp edges.",
        common_causes=["Poor routing", "Missing grommets", "Vibration wear"],
        severity="medium"
    ),
}


# =============================================================================
# FUSE FAILURE MODES
# =============================================================================

FUSE_FAILURES: Dict[str, FailureMode] = {
    "blown": FailureMode(
        id="fuse_blown",
        name="Blown Fuse",
        description="Fuse element has melted from overcurrent",
        symptoms=[
            "Circuit completely dead",
            "Fuse visually blown",
            "Multiple systems may be affected"
        ],
        diagnostic_approach="Visual inspection or continuity check. "
                          "If replacement blows, find the short.",
        common_causes=["Short circuit downstream", "Overloaded circuit", "Component failure"],
        severity="high"
    ),
    
    "high_resistance": FailureMode(
        id="fuse_high_resistance",
        name="High Resistance",
        description="Fuse has poor contact in holder or corroded",
        symptoms=[
            "Circuit works but weak",
            "Fuse holder warm/hot",
            "Voltage drop across fuse"
        ],
        diagnostic_approach="Voltage drop test across fuse under load. "
                          "Should be <0.1V. Inspect holder contacts.",
        common_causes=["Corroded holder", "Wrong fuse size", "Loose fuse"],
        severity="medium"
    ),
}


# =============================================================================
# IGNITION SYSTEM FAILURE MODES
# =============================================================================

IGNITION_COIL_FAILURES: Dict[str, FailureMode] = {
    "open_primary": FailureMode(
        id="coil_open_primary",
        name="Open Primary Winding",
        description="Primary coil winding has break, no spark possible",
        symptoms=[
            "No spark on that cylinder",
            "Misfire DTC",
            "Primary resistance infinite"
        ],
        diagnostic_approach="Measure primary resistance (typically 0.5-2Ω). "
                          "Infinite = open.",
        common_causes=["Thermal damage", "Internal failure", "Age"],
        severity="high"
    ),
    
    "open_secondary": FailureMode(
        id="coil_open_secondary",
        name="Open Secondary Winding",
        description="Secondary coil winding has break",
        symptoms=[
            "No spark",
            "Misfire",
            "Secondary resistance very high"
        ],
        diagnostic_approach="Measure secondary resistance (typically 5-15kΩ). "
                          "Infinite = open.",
        common_causes=["Internal failure", "High voltage damage", "Age"],
        severity="high"
    ),
    
    "shorted": FailureMode(
        id="coil_shorted",
        name="Shorted Winding",
        description="Coil winding has internal short",
        symptoms=[
            "Weak spark",
            "Coil gets very hot",
            "Resistance too low"
        ],
        diagnostic_approach="Measure resistance and compare to spec. "
                          "Too low = shorted.",
        common_causes=["Overheating", "Insulation breakdown"],
        severity="high"
    ),
    
    "weak_spark": FailureMode(
        id="coil_weak",
        name="Weak Spark Output",
        description="Coil produces spark but insufficient energy",
        symptoms=[
            "Hard starting",
            "Misfire under load",
            "May not set DTC"
        ],
        diagnostic_approach="Use spark tester to verify spark intensity. "
                          "Compare to known-good coil.",
        common_causes=["Age", "Thermal damage", "Partial short"],
        severity="medium"
    ),
}


SPARK_PLUG_FAILURES: Dict[str, FailureMode] = {
    "fouled": FailureMode(
        id="plug_fouled",
        name="Fouled",
        description="Spark plug covered in deposits, preventing spark",
        symptoms=[
            "Misfire",
            "Hard starting",
            "Visible deposits on plug"
        ],
        diagnostic_approach="Remove and inspect plug. Carbon = rich mixture. "
                          "Oil = ring/valve guide wear.",
        common_causes=["Rich mixture", "Oil consumption", "Short trips"],
        severity="medium"
    ),
    
    "worn_gap": FailureMode(
        id="plug_worn_gap",
        name="Excessive Gap",
        description="Electrode worn, gap too wide",
        symptoms=[
            "Misfire at high load",
            "Hard starting",
            "Gap > spec"
        ],
        diagnostic_approach="Measure gap with feeler gauge. Compare to spec.",
        common_causes=["Normal wear", "High mileage"],
        severity="low"
    ),
    
    "cracked_insulator": FailureMode(
        id="plug_cracked",
        name="Cracked Insulator",
        description="Ceramic insulator cracked, spark leaking",
        symptoms=[
            "Intermittent misfire",
            "Visible crack",
            "May track to ground"
        ],
        diagnostic_approach="Visual inspection for cracks. "
                          "May be internal - swap with known-good.",
        common_causes=["Overtorque", "Thermal shock", "Impact"],
        severity="medium"
    ),
}


# =============================================================================
# FUEL SYSTEM FAILURE MODES
# =============================================================================

FUEL_INJECTOR_FAILURES: Dict[str, FailureMode] = {
    "clogged": FailureMode(
        id="injector_clogged",
        name="Clogged",
        description="Injector spray pattern blocked or restricted",
        symptoms=[
            "Lean misfire",
            "Rough idle",
            "Poor fuel economy"
        ],
        diagnostic_approach="Compare injector balance test or flow rate. "
                          "Ultrasonic cleaning may help.",
        common_causes=["Fuel contamination", "Deposits", "Age"],
        severity="medium"
    ),
    
    "leaking": FailureMode(
        id="injector_leaking",
        name="Leaking",
        description="Injector drips fuel when closed",
        symptoms=[
            "Rich condition",
            "Hard hot start",
            "Fuel smell"
        ],
        diagnostic_approach="Injector leak-down test. Should hold pressure "
                          "for several minutes.",
        common_causes=["Debris on seat", "Worn seal", "Corrosion"],
        severity="high"
    ),
    
    "stuck_open": FailureMode(
        id="injector_stuck_open",
        name="Stuck Open",
        description="Injector mechanically stuck in open position",
        symptoms=[
            "Severe rich condition on that cylinder",
            "Hydro-lock risk",
            "Fuel in oil"
        ],
        diagnostic_approach="Balance test shows that cylinder always rich. "
                          "Disconnect to verify.",
        common_causes=["Mechanical failure", "Contamination"],
        severity="critical"
    ),
    
    "stuck_closed": FailureMode(
        id="injector_stuck_closed",
        name="Stuck Closed",
        description="Injector won't open when commanded",
        symptoms=[
            "Dead cylinder",
            "Injector DTC",
            "No pulse at injector"
        ],
        diagnostic_approach="Verify control signal present. If yes, injector bad. "
                          "Check coil resistance.",
        common_causes=["Coil failure", "Mechanical seizure"],
        severity="high"
    ),
    
    "electrical_open": FailureMode(
        id="injector_open_circuit",
        name="Open Circuit",
        description="Injector coil or wiring has open",
        symptoms=[
            "Injector DTC",
            "Dead cylinder",
            "Infinite resistance"
        ],
        diagnostic_approach="Measure injector resistance (typically 10-16Ω). "
                          "Check wiring continuity.",
        common_causes=["Coil failure", "Wiring damage", "Connector issue"],
        severity="high"
    ),
}


# =============================================================================
# MASTER TAXONOMY - Maps component types to applicable failure modes
# =============================================================================

FAILURE_TAXONOMY: Dict[ComponentType, Dict[str, FailureMode]] = {
    ComponentType.SENSOR: SENSOR_FAILURES,
    ComponentType.RELAY: RELAY_FAILURES,
    ComponentType.MOTOR: MOTOR_FAILURES,
    ComponentType.PUMP: MOTOR_FAILURES,  # Pumps share motor failure modes
    ComponentType.VALVE: VALVE_FAILURES,
    ComponentType.SOLENOID: VALVE_FAILURES,  # Solenoids share valve failure modes
    ComponentType.CONNECTOR: CONNECTOR_FAILURES,
    ComponentType.WIRING: WIRING_FAILURES,
    ComponentType.FUSE: FUSE_FAILURES,
    ComponentType.IGNITION_COIL: IGNITION_COIL_FAILURES,
    ComponentType.SPARK_PLUG: SPARK_PLUG_FAILURES,
    ComponentType.FUEL_INJECTOR: FUEL_INJECTOR_FAILURES,
    ComponentType.COIL: IGNITION_COIL_FAILURES,
}


def get_failure_modes_for_component(component_type: ComponentType) -> Dict[str, FailureMode]:
    """Get all applicable failure modes for a component type."""
    return FAILURE_TAXONOMY.get(component_type, {})


def get_all_failure_modes() -> Dict[str, FailureMode]:
    """Get flat dictionary of all failure modes."""
    all_modes = {}
    for modes in FAILURE_TAXONOMY.values():
        all_modes.update(modes)
    return all_modes


def get_component_types_for_failure_mode(failure_mode_id: str) -> List[ComponentType]:
    """Get which component types can have this failure mode."""
    types = []
    for comp_type, modes in FAILURE_TAXONOMY.items():
        if failure_mode_id in modes:
            types.append(comp_type)
    return types


# =============================================================================
# COMPONENT IDENTIFICATION KEYWORDS
# =============================================================================
# Used to identify component types from Mitchell wiring diagram text

COMPONENT_KEYWORDS: Dict[ComponentType, List[str]] = {
    ComponentType.SENSOR: [
        "sensor", "sending unit", "sender", "transducer", "thermistor",
        "MAP", "MAF", "CKP", "CMP", "TPS", "O2", "oxygen", "knock",
        "temperature", "pressure", "position", "speed sensor"
    ],
    ComponentType.RELAY: [
        "relay", "K", "RY"
    ],
    ComponentType.MOTOR: [
        "motor", "M", "blower", "wiper", "window", "seat", "mirror"
    ],
    ComponentType.PUMP: [
        "pump", "fuel pump", "water pump", "coolant pump", "washer pump",
        "ABS pump", "hydraulic pump", "oil pump"
    ],
    ComponentType.VALVE: [
        "valve", "EGR", "EVAP", "purge", "VVT", "control valve"
    ],
    ComponentType.SOLENOID: [
        "solenoid", "SOL", "actuator"
    ],
    ComponentType.FUSE: [
        "fuse", "F", "FB", "fusible"
    ],
    ComponentType.CONNECTOR: [
        "connector", "C", "terminal", "splice", "junction"
    ],
    ComponentType.ECU: [
        "ECU", "ECM", "PCM", "TCM", "BCM", "module", "control unit"
    ],
    ComponentType.IGNITION_COIL: [
        "ignition coil", "coil pack", "COP"
    ],
    ComponentType.SPARK_PLUG: [
        "spark plug", "plug"
    ],
    ComponentType.FUEL_INJECTOR: [
        "injector", "fuel injector", "INJ"
    ],
}


def identify_component_type(component_name: str) -> ComponentType:
    """Identify component type from its name using keywords."""
    name_lower = component_name.lower()
    
    for comp_type, keywords in COMPONENT_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in name_lower:
                return comp_type
    
    # Default to generic component
    return ComponentType.SENSOR  # Most common type
