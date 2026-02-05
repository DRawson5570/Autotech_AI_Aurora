"""
Lighting system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


HEADLIGHT_BULB_BURNED = FailureMode(
    id="headlight_bulb_burned",
    name="Headlight Bulb Burned Out",
    category=FailureCategory.ELECTRICAL,
    component_id="headlight",
    system_id="lighting",
    immediate_effect="Headlight not illuminating",
    cascade_effects=[
        "Reduced visibility at night",
        "Safety hazard",
        "Ticket/inspection failure",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("One headlight not working", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection",
        "Check bulb filament",
        "Check for power at socket",
    ],
    repair_actions=["Replace bulb"],
    repair_time_hours=0.3,
    parts_cost_low=10,
    parts_cost_high=50,
    relative_frequency=0.7,
)


HEADLIGHT_CIRCUIT_ISSUE = FailureMode(
    id="headlight_circuit_issue",
    name="Headlight Circuit Problem",
    category=FailureCategory.ELECTRICAL,
    component_id="headlight",
    system_id="lighting",
    immediate_effect="Headlight does not receive power",
    cascade_effects=[
        "One or both headlights inoperative",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Headlight not working", SymptomSeverity.OBVIOUS),
        Symptom("New bulb doesn't work", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check fuse",
        "Check relay",
        "Check for power at headlight connector",
        "Check ground",
    ],
    repair_actions=["Replace fuse", "Replace relay", "Repair wiring"],
    repair_time_hours=0.5,
    parts_cost_low=5,
    parts_cost_high=50,
    relative_frequency=0.4,
)


TAILLIGHT_CIRCUIT_ISSUE = FailureMode(
    id="taillight_circuit_issue",
    name="Taillight/Brake Light Problem",
    category=FailureCategory.ELECTRICAL,
    component_id="taillight",
    system_id="lighting",
    immediate_effect="Tail or brake light not working",
    cascade_effects=[
        "Safety hazard",
        "Ticket/inspection failure",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Taillight or brake light out", SymptomSeverity.OBVIOUS),
        Symptom("Turn signal stays on solid", SymptomSeverity.MODERATE),
    ],
    discriminating_tests=[
        "Check bulb",
        "Check socket for corrosion",
        "Check ground connection",
    ],
    repair_actions=["Replace bulb", "Clean socket", "Repair ground"],
    repair_time_hours=0.3,
    parts_cost_low=5,
    parts_cost_high=30,
    relative_frequency=0.6,
)


TURN_SIGNAL_FAST_FLASH = FailureMode(
    id="turn_signal_fast_flash",
    name="Turn Signal Fast Flash",
    category=FailureCategory.ELECTRICAL,
    component_id="turn_signal",
    system_id="lighting",
    immediate_effect="Turn signal flashes faster than normal",
    cascade_effects=[
        "Usually indicates burned out bulb",
    ],
    expected_dtcs=[],
    symptoms=[
        Symptom("Turn signal flashes too fast", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Check all turn signal bulbs on affected side",
        "Check trailer connector if equipped",
    ],
    repair_actions=["Replace burned out bulb"],
    repair_time_hours=0.2,
    parts_cost_low=5,
    parts_cost_high=15,
    relative_frequency=0.7,
)


# Exports
__all__ = [
    "HEADLIGHT_BULB_BURNED",
    "HEADLIGHT_CIRCUIT_ISSUE",
    "TAILLIGHT_CIRCUIT_ISSUE",
    "TURN_SIGNAL_FAST_FLASH",
]
