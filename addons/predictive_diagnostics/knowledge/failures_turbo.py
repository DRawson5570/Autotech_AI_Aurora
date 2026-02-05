"""
Turbo system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


TURBO_WASTEGATE_STUCK_CLOSED = FailureMode(
    id="turbo_wastegate_stuck_closed",
    name="Wastegate Stuck Closed (Overboost)",
    category=FailureCategory.STUCK,
    component_id="wastegate",
    system_id="turbo",
    
    immediate_effect="Exhaust can't bypass turbo",
    cascade_effects=[
        "Boost pressure exceeds limit",
        "ECU fuel cut for protection",
        "Potential engine damage",
        "Detonation risk",
    ],
    
    pid_effects=[
        PIDEffect("boost_pressure", "high", ">target"),
        PIDEffect("timing_advance", "low", "ECU retards timing"),
    ],
    
    expected_dtcs=["P0234", "P0299"],
    
    symptoms=[
        Symptom("Engine cuts power under boost", SymptomSeverity.OBVIOUS),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("Rough running under load", SymptomSeverity.OBVIOUS),
    ],
    
    discriminating_tests=[
        "Monitor boost pressure vs target",
        "Check wastegate actuator movement",
        "Check boost control solenoid",
        "Inspect wastegate for carbon buildup",
    ],
    
    repair_actions=[
        "Clean or replace wastegate",
        "Check boost control solenoid",
        "Check actuator and lines",
    ],
    relative_frequency=0.3,
)


TURBO_WASTEGATE_STUCK_OPEN = FailureMode(
    id="turbo_wastegate_stuck_open",
    name="Wastegate Stuck Open (Underboost)",
    category=FailureCategory.STUCK,
    component_id="wastegate",
    system_id="turbo",
    
    immediate_effect="Exhaust bypasses turbo constantly",
    cascade_effects=[
        "Boost pressure below target",
        "Reduced power",
        "Poor acceleration",
    ],
    
    pid_effects=[
        PIDEffect("boost_pressure", "low", "<target"),
        PIDEffect("maf_reading", "low", "Less air than expected"),
    ],
    
    expected_dtcs=["P0299", "P0234"],
    
    symptoms=[
        Symptom("Lack of power/boost", SymptomSeverity.OBVIOUS),
        Symptom("Slow acceleration", SymptomSeverity.MODERATE),
        Symptom("Turbo whistle but no power", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Monitor boost pressure vs target",
        "Check wastegate position",
        "Check actuator vacuum/pressure",
        "Listen for wastegate rattle",
    ],
    
    repair_actions=[
        "Adjust wastegate actuator",
        "Replace wastegate if worn",
        "Check actuator and lines",
    ],
    relative_frequency=0.3,
)


TURBO_BEARING_FAILURE = FailureMode(
    id="turbo_bearing_failure",
    name="Turbo Bearing Failure",
    category=FailureCategory.MECHANICAL,
    component_id="turbo",
    system_id="turbo",
    
    immediate_effect="Turbo shaft wobbles/seizes",
    cascade_effects=[
        "Oil leaks into intake/exhaust",
        "Reduced boost",
        "Blue smoke",
        "Total turbo failure",
    ],
    
    pid_effects=[
        PIDEffect("boost_pressure", "low", "Declining"),
        PIDEffect("oil_consumption", "high", "Burning oil"),
    ],
    
    expected_dtcs=["P0299"],
    
    symptoms=[
        Symptom("Blue/white smoke from exhaust", SymptomSeverity.OBVIOUS),
        Symptom("Whining/grinding from turbo", SymptomSeverity.OBVIOUS),
        Symptom("Oil in intercooler piping", SymptomSeverity.OBVIOUS),
        Symptom("Declining boost over time", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Check turbo shaft play (should be minimal)",
        "Check for oil in intake piping",
        "Listen for turbo bearing noise",
        "Check oil supply and drain lines",
    ],
    
    repair_actions=[
        "Replace turbo",
        "Check oil supply restriction",
        "Check oil drain for blockage",
        "Clean/replace intercooler if contaminated",
    ],
    repair_time_hours=4.0,
    parts_cost_low=500,
    parts_cost_high=2000,
    relative_frequency=0.2,
)


BOOST_LEAK = FailureMode(
    id="boost_leak",
    name="Boost/Charge Pipe Leak",
    category=FailureCategory.LEAK,
    component_id="charge_pipe",
    system_id="turbo",
    
    immediate_effect="Pressurized air escaping before engine",
    cascade_effects=[
        "Reduced boost",
        "Lean condition",
        "Poor power",
        "Compressor surge",
    ],
    
    pid_effects=[
        PIDEffect("boost_pressure", "low", "<target"),
        PIDEffect("stft", "positive", "Lean compensation"),
        PIDEffect("maf_reading", "high", "Airflow not reaching cylinders"),
    ],
    
    expected_dtcs=["P0299", "P0171", "P0174"],
    
    symptoms=[
        Symptom("Whooshing/hissing under boost", SymptomSeverity.OBVIOUS),
        Symptom("Lack of power", SymptomSeverity.OBVIOUS),
        Symptom("Lean codes with boost codes", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Pressure test boost system",
        "Listen for leaks under boost",
        "Check intercooler connections",
        "Check turbo inlet/outlet connections",
        "Smoke test intake system",
    ],
    
    repair_actions=[
        "Tighten or replace clamps",
        "Replace damaged piping",
        "Replace intercooler if leaking",
    ],
    repair_time_hours=1.0,
    parts_cost_low=20,
    parts_cost_high=200,
    relative_frequency=0.5,
)


INTERCOOLER_CLOGGED = FailureMode(
    id="intercooler_clogged",
    name="Intercooler Clogged/Damaged",
    category=FailureCategory.BLOCKAGE,
    component_id="intercooler",
    system_id="turbo",
    
    immediate_effect="Hot charge air or restricted flow",
    cascade_effects=[
        "Reduced air density",
        "Detonation risk",
        "Reduced power",
        "Higher intake temps",
    ],
    
    pid_effects=[
        PIDEffect("iat", "high", "Higher than ambient + normal rise"),
        PIDEffect("boost_pressure", "may_decrease", "Restriction reduces flow"),
    ],
    
    expected_dtcs=["P0113", "P0299"],
    
    symptoms=[
        Symptom("High intake temps", SymptomSeverity.MODERATE),
        Symptom("Knock/detonation under load", SymptomSeverity.OBVIOUS),
        Symptom("Reduced power when hot", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Check IAT vs ambient",
        "Inspect intercooler fins for blockage",
        "Check intercooler for oil contamination inside",
        "Pressure test intercooler",
    ],
    
    repair_actions=[
        "Clean intercooler fins",
        "Flush intercooler internally",
        "Replace if damaged",
    ],
    repair_time_hours=2.0,
    parts_cost_low=150,
    parts_cost_high=400,
    relative_frequency=0.3,
)


# Exports
__all__ = [
    "TURBO_WASTEGATE_STUCK_CLOSED",
    "TURBO_WASTEGATE_STUCK_OPEN",
    "TURBO_BEARING_FAILURE",
    "BOOST_LEAK",
    "INTERCOOLER_CLOGGED",
]
