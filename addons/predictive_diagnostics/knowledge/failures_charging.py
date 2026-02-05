"""
Charging system failure modes.
"""

from .base import FailureMode, FailureCategory, Symptom, SymptomSeverity, PIDEffect


ALTERNATOR_FAILING = FailureMode(
    id="alternator_failing",
    name="Alternator Failing/Weak",
    category=FailureCategory.ELECTRICAL,
    component_id="alternator",
    system_id="charging",
    
    immediate_effect="Insufficient charging voltage",
    cascade_effects=[
        "Battery drains",
        "Dimming lights",
        "Electrical system issues",
        "Eventually no start",
    ],
    
    pid_effects=[
        PIDEffect("battery_voltage", "low", "<13.5V running"),
    ],
    
    expected_dtcs=["P0562", "P0622", "P0621"],
    
    symptoms=[
        Symptom("Battery/charging warning light", SymptomSeverity.OBVIOUS),
        Symptom("Dimming headlights", SymptomSeverity.MODERATE),
        Symptom("Dead battery repeatedly", SymptomSeverity.OBVIOUS),
        Symptom("Whining noise from alternator", SymptomSeverity.SUBTLE),
    ],
    
    discriminating_tests=[
        "Check voltage at battery - should be 13.5-14.5V running",
        "Load test alternator",
        "Check alternator belt condition and tension",
        "Inspect connections for corrosion",
    ],
    
    repair_actions=[
        "Replace alternator",
        "Check/replace belt",
        "Clean battery terminals",
        "Test battery condition",
    ],
    repair_time_hours=1.5,
    parts_cost_low=150,
    parts_cost_high=400,
    relative_frequency=0.5,
)


BATTERY_WEAK = FailureMode(
    id="battery_weak",
    name="Battery Weak/Failing",
    category=FailureCategory.ELECTRICAL,
    component_id="battery",
    system_id="charging",
    
    immediate_effect="Insufficient cranking power",
    cascade_effects=[
        "Slow cranking",
        "Clicking no-start",
        "Electrical reset/memory loss",
    ],
    
    pid_effects=[
        PIDEffect("battery_voltage", "low", "<12.4V key off"),
    ],
    
    expected_dtcs=["P0562", "U0100"],
    
    symptoms=[
        Symptom("Slow cranking", SymptomSeverity.OBVIOUS),
        Symptom("Clicking sound, no start", SymptomSeverity.SEVERE),
        Symptom("Clock/radio reset", SymptomSeverity.SUBTLE),
        Symptom("Dim lights during crank", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Battery voltage test - should be 12.4-12.7V fully charged",
        "Load test battery - should hold above 9.6V",
        "Check for parasitic drain",
        "Inspect terminals and cables",
    ],
    
    repair_actions=[
        "Charge and retest battery",
        "Replace battery if failed",
        "Clean terminals",
        "Check for parasitic drain",
    ],
    repair_time_hours=0.5,
    parts_cost_low=100,
    parts_cost_high=250,
    relative_frequency=0.7,
)


STARTER_FAILING = FailureMode(
    id="starter_failing",
    name="Starter Motor Failing",
    category=FailureCategory.MECHANICAL,
    component_id="starter",
    system_id="charging",
    
    immediate_effect="Starter motor doesn't engage or spins weakly",
    cascade_effects=[
        "No start condition",
        "Grinding noise",
        "Intermittent starting",
    ],
    
    pid_effects=[],  # Starter issues typically don't set PIDs
    
    expected_dtcs=["P0615", "P0616", "P0617"],
    
    symptoms=[
        Symptom("Clicking but no crank", SymptomSeverity.SEVERE),
        Symptom("Grinding noise during start", SymptomSeverity.OBVIOUS),
        Symptom("Intermittent no-start", SymptomSeverity.MODERATE),
        Symptom("Slow cranking with good battery", SymptomSeverity.MODERATE),
    ],
    
    discriminating_tests=[
        "Check battery voltage during crank - significant drop indicates starter",
        "Tap starter while someone cranks - if starts, solenoid/contacts bad",
        "Check starter current draw - typically 150-200A",
        "Verify battery and cables are good first",
    ],
    
    repair_actions=[
        "Replace starter motor",
        "Check flywheel/flexplate teeth",
        "Inspect starter wiring",
    ],
    repair_time_hours=1.5,
    parts_cost_low=150,
    parts_cost_high=350,
    relative_frequency=0.4,
)


BATTERY_TERMINAL_CORROSION = FailureMode(
    id="battery_terminal_corrosion",
    name="Battery Terminal Corrosion",
    category=FailureCategory.ELECTRICAL,
    component_id="battery_terminal",
    system_id="charging",
    immediate_effect="High resistance at battery connection",
    cascade_effects=[
        "Hard starting",
        "Electrical problems",
        "Charging issues",
    ],
    expected_dtcs=["P0562", "U0100"],
    symptoms=[
        Symptom("Hard starting", SymptomSeverity.MODERATE),
        Symptom("Dim lights", SymptomSeverity.MODERATE),
        Symptom("Visible corrosion (white/green buildup)", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of terminals",
        "Voltage drop test across terminals",
        "Check cable condition",
    ],
    repair_actions=["Clean terminals", "Replace cables if corroded", "Apply anti-corrosion spray"],
    repair_time_hours=0.3,
    parts_cost_low=5,
    parts_cost_high=50,
    relative_frequency=0.6,
)


ALTERNATOR_BELT_SLIPPING = FailureMode(
    id="alternator_belt_slipping",
    name="Alternator/Serpentine Belt Slipping",
    category=FailureCategory.MECHANICAL,
    component_id="serpentine_belt",
    system_id="charging",
    immediate_effect="Belt not driving accessories properly",
    cascade_effects=[
        "Charging system underperforming",
        "Power steering intermittent",
        "A/C intermittent",
    ],
    expected_dtcs=["P0562", "P0563"],
    symptoms=[
        Symptom("Squealing noise on startup or acceleration", SymptomSeverity.OBVIOUS),
        Symptom("Battery light flickering", SymptomSeverity.MODERATE),
        Symptom("Belt glazed or cracked", SymptomSeverity.OBVIOUS),
    ],
    discriminating_tests=[
        "Visual inspection of belt condition",
        "Check belt tension",
        "Check for oil/coolant contamination on belt",
        "Check tensioner operation",
    ],
    repair_actions=["Replace serpentine belt", "Replace tensioner if weak"],
    repair_time_hours=0.5,
    parts_cost_low=20,
    parts_cost_high=60,
    relative_frequency=0.5,
)


# Exports
__all__ = [
    "ALTERNATOR_FAILING",
    "BATTERY_WEAK",
    "STARTER_FAILING",
    "BATTERY_TERMINAL_CORROSION",
    "ALTERNATOR_BELT_SLIPPING",
]
