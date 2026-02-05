"""
Ignition system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


SPARK_PLUG_FOULED = FailureMode(
    id="spark_plug_fouled",
    name="Spark Plug Fouled/Worn",
    category=FailureCategory.MECHANICAL,
    component_id="spark_plug",
    system_id="ignition",
    
    immediate_effect="Weak or no spark at affected cylinder",
    cascade_effects=[
        "Misfire",
        "Rough idle",
        "Loss of power",
        "Increased emissions",
    ],
    
    pid_effects=[
        PIDEffect("misfire_count", "high", "Specific cylinder"),
    ],
    
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304"],
    
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Misfire", SymptomSeverity.OBVIOUS),
        Symptom("Loss of power", SymptomSeverity.MODERATE),
        Symptom("Hard starting", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Remove and inspect spark plugs",
        "Check gap - should be per spec (typically 0.028-0.060)",
        "Look for carbon fouling, oil fouling, or worn electrode",
    ],
    
    repair_actions=[
        "Replace spark plugs",
        "If oil fouled: check valve seals/piston rings",
        "If carbon fouled: address rich condition",
    ],
    relative_frequency=0.6,
)


IGNITION_COIL_FAILED = FailureMode(
    id="ignition_coil_failed",
    name="Ignition Coil Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ignition_coil",
    system_id="ignition",
    
    immediate_effect="No spark to affected cylinder(s)",
    cascade_effects=[
        "Complete misfire on affected cylinder",
        "Rough running",
        "Possible damage to catalytic converter",
    ],
    
    pid_effects=[
        PIDEffect("misfire_count", "high", "Consistent on specific cylinder"),
    ],
    
    expected_dtcs=["P0351", "P0352", "P0353", "P0354", "P0300", "P0301", "P0302"],
    
    symptoms=[
        Symptom("Misfire", SymptomSeverity.SEVERE),
        Symptom("Rough idle", SymptomSeverity.OBVIOUS),
        Symptom("Check engine light flashing", SymptomSeverity.SEVERE),
        Symptom("Loss of power", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Swap coil to different cylinder - does misfire follow?",
        "Check coil resistance (primary and secondary)",
        "Use spark tester to verify spark",
        "Check coil driver signal with scope",
    ],
    
    repair_actions=[
        "Replace ignition coil",
        "Check boot for carbon tracking",
        "Inspect spark plug well for moisture",
    ],
    relative_frequency=0.5,
)


CRANKSHAFT_POSITION_SENSOR_FAILED = FailureMode(
    id="ckp_sensor_failed",
    name="Crankshaft Position Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ckp_sensor",
    system_id="ignition",
    
    immediate_effect="No crank signal to ECU",
    cascade_effects=[
        "No spark",
        "No fuel injection",
        "Engine cranks but won't start",
        "Random stalling if intermittent",
    ],
    
    pid_effects=[
        PIDEffect("rpm", "zero", "No RPM signal during crank"),
    ],
    
    expected_dtcs=["P0335", "P0336", "P0337", "P0338", "P0339"],
    
    symptoms=[
        Symptom("No start - cranks but won't fire", SymptomSeverity.SEVERE),
        Symptom("Random stalling", SymptomSeverity.SEVERE),
        Symptom("Intermittent no-start", SymptomSeverity.SEVERE),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Check for RPM signal on scanner during crank",
        "Check sensor resistance (typically 200-2000 ohms)",
        "Scope the signal pattern",
        "Check for metal debris on magnetic sensor",
    ],
    
    repair_actions=[
        "Replace crankshaft position sensor",
        "Check reluctor ring for damage",
        "Inspect wiring for damage",
    ],
    relative_frequency=0.4,
)


CAMSHAFT_POSITION_SENSOR_FAILED = FailureMode(
    id="cmp_sensor_failed",
    name="Camshaft Position Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="cmp_sensor",
    system_id="ignition",
    
    immediate_effect="No cam signal for sequential injection/ignition timing",
    cascade_effects=[
        "Engine may run rough or not start",
        "Falls back to batch fire injection",
        "Timing issues",
    ],
    
    pid_effects=[
        PIDEffect("cam_signal", "erratic", "No or intermittent signal"),
    ],
    
    expected_dtcs=["P0340", "P0341", "P0342", "P0343", "P0344", "P0345"],
    
    symptoms=[
        Symptom("Hard starting", SymptomSeverity.MODERATE),
        Symptom("Rough running", SymptomSeverity.MODERATE),
        Symptom("Stalling", SymptomSeverity.MODERATE),
        Symptom("No start (some vehicles)", SymptomSeverity.SEVERE),
    ],
    
    discriminating_tests=[
        "Check for cam signal on scanner",
        "Scope the signal pattern",
        "Check sensor resistance",
        "Inspect for oil contamination",
    ],
    
    repair_actions=[
        "Replace camshaft position sensor",
        "Check timing chain/belt condition",
        "Clear codes and verify",
    ],
    relative_frequency=0.4,
)


IGNITION_MODULE_FAILED = FailureMode(
    id="ignition_module_failed",
    name="Ignition Control Module Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="ignition_module",
    system_id="ignition",
    
    immediate_effect="No spark signal to coils",
    cascade_effects=[
        "No spark",
        "No start or stall",
        "Intermittent misfires",
    ],
    
    pid_effects=[
        PIDEffect("misfire_count", "high", "All cylinders"),
        PIDEffect("rpm", "erratic", "During failure"),
    ],
    
    expected_dtcs=["P0351", "P0352", "P0353", "P0354", "P0355", "P0356", "P0357", "P0358"],
    
    symptoms=[
        Symptom("No start, no spark", SymptomSeverity.SEVERE),
        Symptom("Engine dies when hot, restarts when cool", SymptomSeverity.OBVIOUS),
        Symptom("Random misfires all cylinders", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Check for spark at all cylinders",
        "Check module output signal",
        "Check for intermittent failure when hot",
        "Check CKP/CMP signals to module",
    ],
    
    repair_actions=[
        "Replace ignition module",
        "Check all connections",
        "Check for heat-related failure",
    ],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.3,
)


SECONDARY_IGNITION_LEAK = FailureMode(
    id="secondary_ignition_leak",
    name="Secondary Ignition Leak (Plug Wire/Boot)",
    category=FailureCategory.ELECTRICAL,
    component_id="plug_wire",
    system_id="ignition",
    
    immediate_effect="Spark energy leaking to ground",
    cascade_effects=[
        "Weak spark at plug",
        "Misfire under load",
        "Carbon tracking",
    ],
    
    pid_effects=[
        PIDEffect("misfire_count", "high", "Specific cylinder"),
    ],
    
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304", "P0305", "P0306"],
    
    symptoms=[
        Symptom("Misfire worse under load", SymptomSeverity.MODERATE),
        Symptom("Visible arcing at night", SymptomSeverity.OBVIOUS),
        Symptom("Rough idle when humid", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Check for arcing in dark (spray water mist)",
        "Check plug wire resistance",
        "Inspect boots for cracks/carbon tracking",
        "Swap wires between cylinders, does misfire move?",
    ],
    
    repair_actions=[
        "Replace plug wires/coil boots",
        "Check for carbon tracking on coil",
        "Replace spark plugs if damaged",
    ],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.5,
)


KNOCK_SENSOR_FAILED = FailureMode(
    id="knock_sensor_failed",
    name="Knock Sensor Failed",
    category=FailureCategory.ELECTRICAL,
    component_id="knock_sensor",
    system_id="ignition",
    immediate_effect="PCM cannot detect engine knock/detonation",
    cascade_effects=[
        "PCM may retard timing excessively as precaution",
        "Reduced power and efficiency",
        "Or PCM may not protect engine from actual knock",
    ],
    expected_dtcs=["P0325", "P0326", "P0327", "P0328", "P0330", "P0332"],
    symptoms=[
        Symptom("Check engine light on", SymptomSeverity.OBVIOUS),
        Symptom("Reduced power", SymptomSeverity.MODERATE),
        Symptom("Possible pinging under load", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check knock sensor resistance (typically 100k-500k ohms)",
        "Check wiring continuity to PCM",
        "Tap on engine block while monitoring sensor signal",
    ],
    repair_actions=["Replace knock sensor", "Check wiring and connector"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=150,
    relative_frequency=0.4,
)


IGNITION_COIL_WEAK = FailureMode(
    id="ignition_coil_weak",
    name="Ignition Coil Weak/Marginal",
    category=FailureCategory.DRIFT,
    component_id="ignition_coil",
    system_id="ignition",
    immediate_effect="Weak spark under load",
    cascade_effects=[
        "Misfire under load only",
        "May pass idle test but fail under acceleration",
    ],
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304"],
    symptoms=[
        Symptom("Misfire under acceleration", SymptomSeverity.MODERATE),
        Symptom("Stumble on hills", SymptomSeverity.MODERATE),
        Symptom("OK at idle", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Load test ignition system",
        "Swap coil to another cylinder - does misfire move?",
        "Check coil resistance (primary and secondary)",
    ],
    repair_actions=["Replace ignition coil"],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.5,
)


SPARK_PLUG_WORN = FailureMode(
    id="spark_plug_worn",
    name="Spark Plug Worn",
    category=FailureCategory.DRIFT,
    component_id="spark_plug",
    system_id="ignition",
    immediate_effect="Increased gap requires higher voltage to fire",
    cascade_effects=[
        "Misfire under load",
        "Hard starting",
        "Poor fuel economy",
    ],
    expected_dtcs=["P0300", "P0301", "P0302", "P0303", "P0304"],
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Misfire", SymptomSeverity.MODERATE),
        Symptom("Hard starting", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Remove and inspect spark plugs",
        "Check gap (compare to spec)",
        "Look for wear, deposits, damage",
    ],
    repair_actions=["Replace spark plugs"],
    repair_time_hours=1.0,
    parts_cost_low=20,
    parts_cost_high=80,
    relative_frequency=0.6,
)


# Exports
__all__ = [
    "SPARK_PLUG_FOULED",
    "IGNITION_COIL_FAILED",
    "CRANKSHAFT_POSITION_SENSOR_FAILED",
    "CAMSHAFT_POSITION_SENSOR_FAILED",
    "IGNITION_MODULE_FAILED",
    "SECONDARY_IGNITION_LEAK",
    "KNOCK_SENSOR_FAILED",
    "IGNITION_COIL_WEAK",
    "SPARK_PLUG_WORN",
]
