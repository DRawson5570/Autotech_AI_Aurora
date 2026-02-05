"""
Exhaust system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


EXHAUST_LEAK = FailureMode(
    id="exhaust_leak",
    name="Exhaust Leak",
    category=FailureCategory.LEAK,
    component_id="exhaust_system",
    system_id="exhaust",
    immediate_effect="Exhaust gases escape before reaching tailpipe",
    cascade_effects=[
        "Loud exhaust noise",
        "Exhaust fumes in cabin",
        "O2 sensor readings affected",
        "Potential CO poisoning hazard",
    ],
    expected_dtcs=["P0171", "P0174", "P0420"],
    symptoms=[
        Symptom("Loud exhaust noise", SymptomSeverity.OBVIOUS),
        Symptom("Ticking noise on cold start", SymptomSeverity.MODERATE),
        Symptom("Exhaust smell in cabin", SymptomSeverity.SEVERE),
        Symptom("Check engine light (lean codes)", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Visual inspection for rust holes or loose connections",
        "Listen for exhaust noise changes",
        "Check with smoke machine",
        "Feel for exhaust escaping at joints",
    ],
    repair_actions=["Replace exhaust gasket", "Weld or replace damaged section", "Replace exhaust manifold"],
    repair_time_hours=1.5,
    parts_cost_low=20,
    parts_cost_high=300,
    relative_frequency=0.5,
)


EXHAUST_MANIFOLD_CRACK = FailureMode(
    id="exhaust_manifold_crack",
    name="Exhaust Manifold Cracked",
    category=FailureCategory.MECHANICAL,
    component_id="exhaust_manifold",
    system_id="exhaust",
    immediate_effect="Exhaust leak at manifold",
    cascade_effects=[
        "Ticking noise especially when cold",
        "Can cause lean condition",
        "Heat damage to nearby components",
    ],
    expected_dtcs=["P0171", "P0174"],
    symptoms=[
        Symptom("Ticking noise on cold start that goes away warm", SymptomSeverity.OBVIOUS),
        Symptom("Exhaust smell", SymptomSeverity.MODERATE),
        Symptom("Visible crack in manifold", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of manifold",
        "Listen for tick that decreases as engine warms",
        "Spray water on manifold - steam indicates crack location",
    ],
    repair_actions=["Replace exhaust manifold", "Replace manifold gasket"],
    repair_time_hours=3.0,
    parts_cost_low=100,
    parts_cost_high=400,
    relative_frequency=0.4,
)


FLEX_PIPE_FAILED = FailureMode(
    id="flex_pipe_failed",
    name="Exhaust Flex Pipe Failed",
    category=FailureCategory.MECHANICAL,
    component_id="flex_pipe",
    system_id="exhaust",
    immediate_effect="Flex joint leaks or separates",
    cascade_effects=[
        "Loud exhaust noise",
        "Can affect O2 readings",
        "May cause exhaust to hang low",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Loud exhaust noise from under car", SymptomSeverity.OBVIOUS),
        Symptom("Rattling or vibration", SymptomSeverity.MODERATE),
        Symptom("Visible damage to flex section", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection from underneath",
        "Check flex pipe for separation or holes",
        "Look for rust-through",
    ],
    repair_actions=["Replace flex pipe section", "Weld in new flex joint"],
    repair_time_hours=1.5,
    parts_cost_low=50,
    parts_cost_high=150,
    relative_frequency=0.4,
)


MUFFLER_FAILED = FailureMode(
    id="muffler_failed",
    name="Muffler Failed/Rusted",
    category=FailureCategory.MECHANICAL,
    component_id="muffler",
    system_id="exhaust",
    immediate_effect="Muffler no longer dampens exhaust sound",
    cascade_effects=[
        "Loud exhaust",
        "May affect back pressure slightly",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Loud exhaust noise", SymptomSeverity.OBVIOUS),
        Symptom("Rattling from muffler area", SymptomSeverity.MODERATE),
        Symptom("Visible rust holes", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of muffler",
        "Shake muffler - internal baffles broken?",
        "Look for rust-through holes",
    ],
    repair_actions=["Replace muffler"],
    repair_time_hours=1.0,
    parts_cost_low=50,
    parts_cost_high=200,
    relative_frequency=0.5,
)


# Exports
__all__ = [
    "EXHAUST_LEAK",
    "EXHAUST_MANIFOLD_CRACK",
    "FLEX_PIPE_FAILED",
    "MUFFLER_FAILED",
]
