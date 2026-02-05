"""
Intake system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


AIR_FILTER_CLOGGED = FailureMode(
    id="air_filter_clogged",
    name="Air Filter Clogged",
    category=FailureCategory.BLOCKAGE,
    component_id="air_filter",
    system_id="intake",
    immediate_effect="Restricted airflow to engine",
    cascade_effects=[
        "Reduced power",
        "Poor fuel economy",
        "Rich running condition",
    ],
    expected_dtcs=["P0101", "P0172", "P0175"],
    symptoms=[
        Symptom("Reduced power", SymptomSeverity.MODERATE),
        Symptom("Poor fuel economy", SymptomSeverity.SUBTLE),
        Symptom("Black smoke from exhaust", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection of air filter",
        "Check MAF readings (may be low)",
        "Hold filter up to light",
    ],
    repair_actions=["Replace air filter"],
    repair_time_hours=0.1,
    parts_cost_low=10,
    parts_cost_high=40,
    relative_frequency=0.7,
)


INTAKE_BOOT_CRACKED = FailureMode(
    id="intake_boot_cracked",
    name="Intake Boot/Hose Cracked",
    category=FailureCategory.LEAK,
    component_id="intake_boot",
    system_id="intake",
    immediate_effect="Unmetered air enters after MAF sensor",
    cascade_effects=[
        "Lean condition",
        "Rough idle",
        "Check engine light",
    ],
    expected_dtcs=["P0171", "P0174", "P0101"],
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Hesitation on acceleration", SymptomSeverity.MODERATE),
        Symptom("Check engine light", SymptomSeverity.OBVIOUS),
        Symptom("Whistling or hissing noise", SymptomSeverity.SUBTLE),
    ],
    discriminating_tests=[
        "Visual inspection of intake boot",
        "Flex boot while engine running - RPM change?",
        "Smoke test intake system",
        "Spray carb cleaner - RPM change indicates leak",
    ],
    repair_actions=["Replace intake boot/hose", "Check clamps"],
    repair_time_hours=0.5,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.5,
)


THROTTLE_BODY_CARBON = FailureMode(
    id="throttle_body_carbon",
    name="Throttle Body Carbon Buildup",
    category=FailureCategory.BLOCKAGE,
    component_id="throttle_body",
    system_id="intake",
    immediate_effect="Carbon restricts airflow and affects throttle response",
    cascade_effects=[
        "Rough or high idle",
        "Stalling",
        "Poor throttle response",
    ],
    expected_dtcs=["P0505", "P0506", "P0507", "P2111", "P2112"],
    symptoms=[
        Symptom("Rough or surging idle", SymptomSeverity.MODERATE),
        Symptom("Stalling when coming to stop", SymptomSeverity.MODERATE),
        Symptom("Hesitation on tip-in", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection of throttle plate",
        "Check idle air control readings",
        "Check throttle position at idle",
    ],
    repair_actions=["Clean throttle body", "May need throttle relearn procedure"],
    repair_time_hours=0.5,
    parts_cost_low=5,
    parts_cost_high=20,
    relative_frequency=0.6,
)


INTAKE_MANIFOLD_GASKET_LEAK = FailureMode(
    id="intake_manifold_gasket_leak",
    name="Intake Manifold Gasket Leak",
    category=FailureCategory.LEAK,
    component_id="intake_manifold",
    system_id="intake",
    immediate_effect="Vacuum leak at intake manifold",
    cascade_effects=[
        "Lean condition",
        "Rough idle",
        "Possible coolant leak (some designs)",
    ],
    expected_dtcs=["P0171", "P0174", "P0300", "P0505"],
    symptoms=[
        Symptom("Rough idle", SymptomSeverity.MODERATE),
        Symptom("Lean codes", SymptomSeverity.OBVIOUS),
        Symptom("Hissing noise from intake area", SymptomSeverity.SUBTLE),
        Symptom("Coolant loss (some engines)", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Smoke test intake",
        "Spray carb cleaner around manifold - RPM change?",
        "Check for coolant in intake (if applicable)",
    ],
    repair_actions=["Replace intake manifold gaskets"],
    repair_time_hours=3.0,
    parts_cost_low=30,
    parts_cost_high=100,
    relative_frequency=0.4,
)


# Exports
__all__ = [
    "AIR_FILTER_CLOGGED",
    "INTAKE_BOOT_CRACKED",
    "THROTTLE_BODY_CARBON",
    "INTAKE_MANIFOLD_GASKET_LEAK",
]
