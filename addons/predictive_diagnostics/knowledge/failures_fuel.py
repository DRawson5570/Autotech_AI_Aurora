"""
Fuel system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


FUEL_PUMP_WEAK = FailureMode(
    id="fuel_pump_weak",
    name="Fuel Pump Weak/Failing",
    category=FailureCategory.MECHANICAL,
    component_id="fuel_pump",
    system_id="fuel",
    
    immediate_effect="Insufficient fuel pressure/volume to injectors",
    cascade_effects=[
        "Lean condition under load",
        "Loss of power",
        "Hard starting especially when hot",
        "Engine stalling",
    ],
    
    pid_effects=[
        PIDEffect("fuel_pressure", "low", "<35 psi"),
        PIDEffect("ltft", "positive", "+10 to +25%"),
        PIDEffect("stft", "positive", "+5 to +15%"),
    ],
    
    expected_dtcs=["P0087", "P0171", "P0174", "P0230"],
    
    symptoms=[
        Symptom("Hard starting (especially hot)", SymptomSeverity.MODERATE),
        Symptom("Loss of power under acceleration", SymptomSeverity.OBVIOUS),
        Symptom("Engine stalling", SymptomSeverity.SEVERE),
        Symptom("Whining noise from fuel tank", SymptomSeverity.SUBTLE),
        Symptom("Engine surging", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Fuel pressure test - should be 35-65 psi (varies by vehicle)",
        "Volume test - should deliver 1 pint in 30 seconds",
        "Pressure drop test - check for leaky injectors",
        "Listen for pump operation when key on",
    ],
    
    repair_actions=[
        "Check fuel filter first",
        "Replace fuel pump",
        "Inspect fuel lines for restrictions",
    ],
    repair_time_hours=2.0,
    parts_cost_low=200,
    parts_cost_high=500,
    relative_frequency=0.5,
)


FUEL_INJECTOR_CLOGGED = FailureMode(
    id="fuel_injector_clogged",
    name="Fuel Injector Clogged/Restricted",
    category=FailureCategory.BLOCKAGE,
    component_id="fuel_injector",
    system_id="fuel",
    
    immediate_effect="Insufficient fuel delivery to affected cylinder",
    cascade_effects=[
        "Lean misfire on affected cylinder",
        "Rough idle",
        "Loss of power",
        "Increased emissions",
    ],
    
    pid_effects=[
        PIDEffect("misfire_count", "high", "Specific cylinder"),
        PIDEffect("stft", "positive", "Bank may run lean"),
    ],
    
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304", "P0171", "P0174"],
    
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Misfire", SymptomSeverity.OBVIOUS),
        Symptom("Loss of power", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Injector balance test",
        "Noid light test - verify signal to injector",
        "Swap injector to different cylinder to confirm",
        "Fuel injector cleaning service",
    ],
    
    repair_actions=[
        "Professional fuel injector cleaning",
        "Replace injector if cleaning fails",
        "Use quality fuel and injector cleaner",
    ],
    repair_time_hours=1.0,
    parts_cost_low=50,
    parts_cost_high=150,
    relative_frequency=0.4,
)


FUEL_INJECTOR_LEAKING = FailureMode(
    id="fuel_injector_leaking",
    name="Fuel Injector Leaking",
    category=FailureCategory.LEAK,
    component_id="fuel_injector",
    system_id="fuel",
    
    immediate_effect="Fuel drips into cylinder when engine off",
    cascade_effects=[
        "Rich condition on affected cylinder",
        "Hard starting (flooded)",
        "Raw fuel smell",
        "Catalytic converter damage",
    ],
    
    pid_effects=[
        PIDEffect("stft", "negative", "-10 to -25% on affected bank"),
        PIDEffect("o2_sensor", "rich", "<0.3V"),
    ],
    
    expected_dtcs=["P0172", "P0175", "P0300"],
    
    symptoms=[
        Symptom("Hard starting (floods easily)", SymptomSeverity.MODERATE),
        Symptom("Fuel smell", SymptomSeverity.OBVIOUS),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Black smoke from exhaust", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Fuel pressure drop test - pressure should hold for 5+ minutes",
        "Visual inspection for external leaks",
        "Pinch fuel return line and watch pressure gauge",
    ],
    
    repair_actions=[
        "Replace leaking injector",
        "Replace injector O-rings",
        "Check for fuel rail leaks",
    ],
    repair_time_hours=1.5,
    parts_cost_low=80,
    parts_cost_high=200,
    relative_frequency=0.3,
)


MAF_SENSOR_CONTAMINATED = FailureMode(
    id="maf_sensor_contaminated",
    name="MAF Sensor Contaminated/Failed",
    category=FailureCategory.DRIFT,
    component_id="maf_sensor",
    system_id="fuel",
    
    immediate_effect="Inaccurate air flow measurement",
    cascade_effects=[
        "Incorrect fuel calculation",
        "Lean or rich condition",
        "Poor driveability",
        "Hesitation and stumble",
    ],
    
    pid_effects=[
        PIDEffect("maf", "erratic", "Reading doesn't match expected"),
        PIDEffect("stft", "variable", "May be positive or negative"),
        PIDEffect("ltft", "variable", "Significant deviation"),
    ],
    
    expected_dtcs=["P0100", "P0101", "P0102", "P0103", "P0171", "P0174"],
    
    symptoms=[
        Symptom("Hesitation on acceleration", SymptomSeverity.MODERATE),
        Symptom("Stalling", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Black smoke (if reading low)", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Compare MAF reading to calculated air flow",
        "Check MAF at idle: typically 2-7 g/s",
        "Check MAF at WOT: should increase smoothly",
        "Visual inspection for contamination",
    ],
    
    repair_actions=[
        "Clean MAF sensor with MAF cleaner",
        "Replace if cleaning doesn't help",
        "Check air filter and intake for leaks",
    ],
    relative_frequency=0.5,
)


O2_SENSOR_FAILED = FailureMode(
    id="o2_sensor_failed",
    name="Oxygen Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="o2_sensor",
    system_id="fuel",
    
    immediate_effect="No or incorrect exhaust oxygen feedback",
    cascade_effects=[
        "Fuel system runs open loop",
        "Poor fuel economy",
        "Increased emissions",
        "Catalytic converter damage over time",
    ],
    
    pid_effects=[
        PIDEffect("o2_sensor", "stuck", "No switching or stuck at one voltage"),
        PIDEffect("stft", "variable", "May be stuck at limit"),
    ],
    
    expected_dtcs=["P0130", "P0131", "P0132", "P0133", "P0134", "P0135", 
                   "P0136", "P0137", "P0138", "P0140", "P0141"],
    
    symptoms=[
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("Poor fuel economy", SymptomSeverity.MODERATE),
        Symptom("Rough idle", SymptomSeverity.SUBTLE),
        Symptom("Failed emissions test", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Monitor O2 sensor voltage - should switch 0.1-0.9V",
        "Check heater circuit resistance",
        "Propane enrichment test",
        "Check response time",
    ],
    
    repair_actions=[
        "Replace O2 sensor",
        "Clear codes and verify repair",
        "Check for exhaust leaks that might affect reading",
    ],
    relative_frequency=0.6,
)


VACUUM_LEAK = FailureMode(
    id="vacuum_leak",
    name="Vacuum Leak",
    category=FailureCategory.LEAK,
    component_id="intake_manifold",
    system_id="fuel",
    
    immediate_effect="Unmeasured air enters intake",
    cascade_effects=[
        "Lean condition",
        "Rough idle",
        "High idle speed",
        "Poor performance",
    ],
    
    pid_effects=[
        PIDEffect("stft", "positive", "+10 to +25%"),
        PIDEffect("ltft", "positive", "+5 to +20%"),
        PIDEffect("map", "high", "Lower vacuum than expected"),
        PIDEffect("rpm", "high", "Elevated idle"),
    ],
    
    expected_dtcs=["P0171", "P0174", "P0505", "P0507"],
    
    symptoms=[
        Symptom("High idle", SymptomSeverity.MODERATE),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Hissing sound from engine", SymptomSeverity.SUBTLE),
        Symptom("Hesitation", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Smoke test intake system",
        "Spray carb cleaner around intake - RPM change indicates leak",
        "Check vacuum hoses for cracks",
        "Inspect intake manifold gasket",
    ],
    
    repair_actions=[
        "Locate and seal leak",
        "Replace cracked vacuum hoses",
        "Replace intake manifold gasket if needed",
    ],
    relative_frequency=0.6,
)


IAT_SENSOR_FAILED_HIGH = FailureMode(
    id="iat_sensor_failed_high",
    name="Intake Air Temp Sensor Reading High",
    category=FailureCategory.ELECTRICAL,
    component_id="iat_sensor",
    system_id="fuel",
    immediate_effect="PCM sees false high intake air temperature",
    cascade_effects=[
        "PCM reduces fuel (thinks air is less dense)",
        "Lean condition possible",
        "Poor performance in cold weather",
    ],
    expected_dtcs=["P0113"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Poor cold start performance", SymptomSeverity.MODERATE),
        Symptom("Hesitation", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Compare IAT reading to ambient temp (cold engine)",
        "Check sensor resistance vs temperature chart",
        "Check for open circuit (reads very hot)",
    ],
    repair_actions=["Replace IAT sensor", "Check connector and wiring"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=60,
    relative_frequency=0.3,
)


IAT_SENSOR_FAILED_LOW = FailureMode(
    id="iat_sensor_failed_low",
    name="Intake Air Temp Sensor Reading Low",
    category=FailureCategory.ELECTRICAL,
    component_id="iat_sensor",
    system_id="fuel",
    immediate_effect="PCM sees false low intake air temperature",
    cascade_effects=[
        "PCM adds fuel (thinks air is denser)",
        "Rich condition",
        "Poor fuel economy",
    ],
    expected_dtcs=["P0112"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Rich exhaust smell", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Compare IAT reading to ambient temp (cold engine)",
        "Check sensor resistance vs temperature chart",
        "Check for shorted circuit (reads very cold)",
    ],
    repair_actions=["Replace IAT sensor", "Check connector and wiring"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=60,
    relative_frequency=0.3,
)


MAP_SENSOR_FAILED = FailureMode(
    id="map_sensor_failed",
    name="MAP Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="map_sensor",
    system_id="fuel",
    immediate_effect="PCM cannot accurately measure manifold pressure",
    cascade_effects=[
        "Incorrect fuel calculation",
        "Poor idle quality",
        "Hesitation and stalling",
    ],
    expected_dtcs=["P0105", "P0106", "P0107", "P0108"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Stalling", SymptomSeverity.OBVIOUS),
        Symptom("Black smoke", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check MAP voltage at key on (should be ~4.5V)",
        "Apply vacuum - voltage should drop",
        "Compare MAP to calculated load",
    ],
    repair_actions=["Replace MAP sensor", "Check vacuum hose for leaks"],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.4,
)


TPS_SENSOR_FAILED = FailureMode(
    id="tps_sensor_failed",
    name="Throttle Position Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="tps_sensor",
    system_id="fuel",
    immediate_effect="PCM cannot accurately read throttle position",
    cascade_effects=[
        "Erratic idle",
        "Hesitation on acceleration",
        "Possible limp mode",
    ],
    expected_dtcs=["P0120", "P0121", "P0122", "P0123", "P0220", "P0221", "P0222", "P0223"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Erratic idle", SymptomSeverity.MODERATE),
        Symptom("Hesitation", SymptomSeverity.MODERATE),
        Symptom("Surge on acceleration", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Graph TPS signal while slowly opening throttle (smooth curve?)",
        "Check for dead spots or dropouts",
        "Check reference voltage (5V)",
    ],
    repair_actions=["Replace TPS sensor", "On electronic throttle, may need throttle body"],
    repair_time_hours=0.5,
    parts_cost_low=40,
    parts_cost_high=150,
    relative_frequency=0.5,
)


APP_SENSOR_FAILED = FailureMode(
    id="app_sensor_failed",
    name="Accelerator Pedal Position Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="app_sensor",
    system_id="fuel",
    immediate_effect="PCM cannot read driver throttle request",
    cascade_effects=[
        "Limp mode - limited power",
        "Vehicle may not accelerate properly",
        "Possible no-start",
    ],
    expected_dtcs=["P2122", "P2123", "P2127", "P2128", "P2138"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Limp mode / reduced power", SymptomSeverity.SEVERE),
        Symptom("Pedal feels unresponsive", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Graph APP sensors while pressing pedal",
        "Check for correlation between APP1 and APP2",
        "Check reference voltage and ground",
    ],
    repair_actions=["Replace accelerator pedal assembly"],
    repair_time_hours=0.5,
    parts_cost_low=100,
    parts_cost_high=300,
    relative_frequency=0.3,
)


MASS_AIR_FLOW_SENSOR_FAILED = FailureMode(
    id="mass_air_flow_sensor_failed",
    name="Mass Air Flow Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="maf_sensor",
    system_id="fuel",
    immediate_effect="PCM cannot measure incoming air mass",
    cascade_effects=[
        "Incorrect fuel calculation",
        "Rich or lean condition",
        "Poor idle and drivability",
    ],
    expected_dtcs=["P0100", "P0101", "P0102", "P0103", "P0104"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Stalling", SymptomSeverity.MODERATE),
        Symptom("Hesitation", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check MAF reading at idle (typically 3-7 g/s)",
        "Snap throttle - MAF should spike and return",
        "Check for contamination on hot wire/film",
    ],
    repair_actions=["Clean MAF sensor", "Replace if cleaning doesn't help"],
    repair_time_hours=0.3,
    parts_cost_low=80,
    parts_cost_high=250,
    relative_frequency=0.5,
)


FUEL_PRESSURE_REGULATOR_FAILED = FailureMode(
    id="fuel_pressure_regulator_failed",
    name="Fuel Pressure Regulator Failed",
    category=FailureCategory.MECHANICAL,
    component_id="fuel_pressure_regulator",
    system_id="fuel",
    immediate_effect="Fuel pressure not regulated properly",
    cascade_effects=[
        "Rich or lean condition depending on failure mode",
        "Hard starting",
        "Poor performance",
    ],
    expected_dtcs=["P0087", "P0088", "P0089", "P0190", "P0191"],
    symptoms=[
        Symptom("Hard starting", SymptomSeverity.MODERATE),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Black smoke (rich)", SymptomSeverity.MODERATE),
        Symptom("Fuel smell at tailpipe", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check fuel pressure (compare to spec)",
        "Check for fuel in vacuum line to regulator (if equipped)",
        "Dead-head pressure test",
    ],
    repair_actions=["Replace fuel pressure regulator"],
    repair_time_hours=1.0,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.4,
)


FUEL_FILTER_CLOGGED = FailureMode(
    id="fuel_filter_clogged",
    name="Fuel Filter Clogged",
    category=FailureCategory.BLOCKAGE,
    component_id="fuel_filter",
    system_id="fuel",
    immediate_effect="Restricted fuel flow to engine",
    cascade_effects=[
        "Low fuel pressure under load",
        "Starvation at high RPM",
        "Engine cuts out",
    ],
    expected_dtcs=["P0087", "P0171"],
    symptoms=[
        Symptom("Loss of power under load", SymptomSeverity.MODERATE),
        Symptom("Engine stumbles at high speed", SymptomSeverity.MODERATE),
        Symptom("Hard starting", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check fuel pressure at idle vs under load",
        "Pressure should hold steady under load",
        "Inspect filter (if accessible)",
    ],
    repair_actions=["Replace fuel filter"],
    repair_time_hours=0.5,
    parts_cost_low=15,
    parts_cost_high=50,
    relative_frequency=0.4,
)


FUEL_INJECTOR_CIRCUIT_OPEN = FailureMode(
    id="fuel_injector_circuit_open",
    name="Fuel Injector Circuit Open",
    category=FailureCategory.ELECTRICAL,
    component_id="fuel_injector",
    system_id="fuel",
    immediate_effect="Injector does not receive signal - cylinder not firing",
    cascade_effects=[
        "Misfire on that cylinder",
        "Rough idle",
        "Loss of power",
    ],
    expected_dtcs=["P0201", "P0202", "P0203", "P0204", "P0205", "P0206", "P0207", "P0208"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Misfire", SymptomSeverity.OBVIOUS),
        Symptom("Rough idle", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check injector resistance (typically 12-16 ohms)",
        "Check for power at injector connector",
        "Use noid light to check for injector pulse",
    ],
    repair_actions=["Repair wiring", "Replace connector", "Replace injector if shorted"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=100,
    relative_frequency=0.4,
)


FUEL_TANK_VENT_BLOCKED = FailureMode(
    id="fuel_tank_vent_blocked",
    name="Fuel Tank Vent Blocked",
    category=FailureCategory.BLOCKAGE,
    component_id="fuel_tank",
    system_id="fuel",
    immediate_effect="Tank cannot vent, creates vacuum",
    cascade_effects=[
        "Fuel pump works harder",
        "Tank may collapse slightly",
        "Engine stalls due to fuel starvation",
    ],
    expected_dtcs=["P0440", "P0446"],
    symptoms=[
        Symptom("Engine stalls or hesitates", SymptomSeverity.MODERATE),
        Symptom("Whooshing sound when opening gas cap", SymptomSeverity.MODERATE),
        Symptom("Difficulty refueling", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Open gas cap - excessive vacuum release?",
        "Check EVAP vent valve operation",
        "Smoke test EVAP system",
    ],
    repair_actions=["Replace vent valve", "Clear blocked vent line"],
    repair_time_hours=1.0,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.3,
)


HIGH_PRESSURE_FUEL_PUMP_FAILED = FailureMode(
    id="high_pressure_fuel_pump_failed",
    name="High Pressure Fuel Pump Failed (GDI)",
    category=FailureCategory.MECHANICAL,
    component_id="hpfp",
    system_id="fuel",
    immediate_effect="Cannot build sufficient fuel pressure for direct injection",
    cascade_effects=[
        "Long crank/no start",
        "Severe misfire",
        "Engine runs rough or not at all",
    ],
    expected_dtcs=["P0087", "P0088", "P0089", "P0191"],
    symptoms=[
        Symptom("Long crank time", SymptomSeverity.OBVIOUS),
        Symptom("Rough idle", SymptomSeverity.SEVERE),
        Symptom("Loss of power", SymptomSeverity.SEVERE),
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check high pressure fuel pressure (should be 500-2000+ psi)",
        "Check HPFP cam follower for wear",
        "Compare commanded vs actual fuel pressure",
    ],
    repair_actions=["Replace HPFP", "Inspect cam follower"],
    repair_time_hours=2.0,
    parts_cost_low=300,
    parts_cost_high=800,
    relative_frequency=0.4,
)


FUEL_LEVEL_SENSOR_FAILED = FailureMode(
    id="fuel_level_sensor_failed",
    name="Fuel Level Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="fuel_level_sensor",
    system_id="fuel",
    immediate_effect="Incorrect fuel gauge reading",
    cascade_effects=[
        "Gauge stuck on full or empty",
        "Erratic gauge movement",
        "Risk of running out of fuel",
    ],
    expected_dtcs=["P0460", "P0461", "P0462", "P0463"],
    symptoms=[
        Symptom("Fuel gauge stuck", SymptomSeverity.OBVIOUS),
        Symptom("Erratic fuel gauge reading", SymptomSeverity.MODERATE),
        Symptom("Low fuel light always on or never on", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check fuel level sender resistance",
        "Check wiring to fuel tank",
        "Verify gauge operation by grounding sender wire",
    ],
    repair_actions=["Replace fuel level sensor/sender", "Check wiring"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.4,
)


BAROMETRIC_PRESSURE_SENSOR_FAILED = FailureMode(
    id="barometric_pressure_sensor_failed",
    name="Barometric Pressure Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="baro_sensor",
    system_id="fuel",
    immediate_effect="PCM cannot compensate for altitude changes",
    cascade_effects=[
        "Poor performance at altitude",
        "Rich or lean condition",
    ],
    expected_dtcs=["P0105", "P0106", "P1106", "P1107"],
    symptoms=[
        Symptom("Poor performance at altitude", SymptomSeverity.MODERATE),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Compare BARO reading to actual barometric pressure",
        "Check sensor voltage/signal",
        "Some vehicles use MAP sensor for BARO at key-on",
    ],
    repair_actions=["Replace BARO sensor", "Check wiring"],
    repair_time_hours=0.5,
    parts_cost_low=40,
    parts_cost_high=120,
    relative_frequency=0.2,
)


# Exports
__all__ = [
    "FUEL_PUMP_WEAK",
    "FUEL_INJECTOR_CLOGGED",
    "FUEL_INJECTOR_LEAKING",
    "MAF_SENSOR_CONTAMINATED",
    "O2_SENSOR_FAILED",
    "VACUUM_LEAK",
    "IAT_SENSOR_FAILED_HIGH",
    "IAT_SENSOR_FAILED_LOW",
    "MAP_SENSOR_FAILED",
    "TPS_SENSOR_FAILED",
    "APP_SENSOR_FAILED",
    "MASS_AIR_FLOW_SENSOR_FAILED",
    "FUEL_PRESSURE_REGULATOR_FAILED",
    "FUEL_FILTER_CLOGGED",
    "FUEL_INJECTOR_CIRCUIT_OPEN",
    "FUEL_TANK_VENT_BLOCKED",
    "HIGH_PRESSURE_FUEL_PUMP_FAILED",
    "FUEL_LEVEL_SENSOR_FAILED",
    "BAROMETRIC_PRESSURE_SENSOR_FAILED",
]
