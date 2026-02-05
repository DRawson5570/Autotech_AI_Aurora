"""
Model-Based Diagnosis Engine

This is the core of physics-based fault isolation. Instead of pattern matching,
it uses the physics models to:

1. Predict what sensors SHOULD read (forward simulation)
2. Compare to actual readings (residual analysis)
3. Identify which fault best explains the deviation (hypothesis testing)

"Each fault produces a UNIQUE signature in the physics."

This approach handles:
- Novel failures (never seen before in training data)
- Intermittent issues (physics still applies)
- Multiple simultaneous faults
- Confidence quantification (how well does physics explain this?)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import math

from .cooling_system import CoolingSystemModel, CoolingSystemState


@dataclass
class OperatingConditions:
    """
    Current operating point of the vehicle.
    
    This is the context needed to predict expected behavior.
    From scan tool data or estimated from other readings.
    """
    rpm: float = 800                    # Engine RPM
    load_fraction: float = 0.2          # Engine load (0-1)
    ambient_temp_c: float = 25.0        # Outside temperature
    vehicle_speed_kph: float = 0.0      # Vehicle speed
    ac_on: bool = False                 # AC compressor
    engine_runtime_minutes: float = 10  # Time since start


@dataclass
class SensorReadings:
    """
    Actual sensor readings from the vehicle.
    
    These are compared against physics model predictions.
    """
    # Cooling system
    coolant_temp_c: Optional[float] = None      # ECT sensor
    oil_temp_c: Optional[float] = None          # If available
    intake_air_temp_c: Optional[float] = None   # IAT
    
    # Derived/observed
    fan_running: Optional[bool] = None
    heater_output_hot: Optional[bool] = None    # Heater blowing hot air?
    upper_hose_hot: Optional[bool] = None       # Physical check
    lower_hose_hot: Optional[bool] = None       # Physical check
    temp_rising_at_idle: Optional[bool] = None  # Temp climbs when stopped
    
    # DTCs present
    dtcs: List[str] = field(default_factory=list)


@dataclass
class PhysicsTrace:
    """
    Detailed trace of physics calculations.
    
    This is the "show your work" - explains exactly why the model
    predicts what it predicts. Essential for building trust with techs.
    """
    steps: List[str] = field(default_factory=list)
    equations_used: List[str] = field(default_factory=list)
    values_calculated: Dict[str, float] = field(default_factory=dict)
    
    def add_step(self, description: str, equation: str = None, **values):
        """Add a calculation step to the trace"""
        self.steps.append(description)
        if equation:
            self.equations_used.append(equation)
        self.values_calculated.update(values)
    
    def to_string(self) -> str:
        """Format trace for display"""
        lines = ["## Physics Reasoning Trace\n"]
        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. {step}")
        if self.values_calculated:
            lines.append("\n### Calculated Values:")
            for name, value in self.values_calculated.items():
                if isinstance(value, float):
                    lines.append(f"- {name}: {value:.2f}")
                else:
                    lines.append(f"- {name}: {value}")
        return "\n".join(lines)


@dataclass
class DiagnosticHypothesis:
    """
    A candidate fault with evidence analysis.
    """
    fault_id: str
    fault_description: str
    
    # How well does this fault explain the observations?
    consistency_score: float  # 0-1, higher = better match
    
    # Predicted vs actual comparison
    predicted_temp_c: float
    actual_temp_c: float
    temp_deviation_c: float
    
    # Additional predicted symptoms
    predicted_symptoms: List[str] = field(default_factory=list)
    observed_symptoms: List[str] = field(default_factory=list)
    symptom_match_score: float = 0.0
    
    # Physics explanation
    physics_trace: PhysicsTrace = field(default_factory=PhysicsTrace)
    
    # What would confirm/rule out this hypothesis
    confirming_tests: List[str] = field(default_factory=list)
    ruling_out_tests: List[str] = field(default_factory=list)


@dataclass 
class DiagnosticResult:
    """
    Complete diagnostic result from model-based analysis.
    """
    # Operating context
    conditions: OperatingConditions
    readings: SensorReadings
    
    # Normal (no fault) prediction
    expected_temp_c: float
    expected_state: CoolingSystemState
    
    # Deviation from normal
    deviation_c: float
    deviation_significant: bool
    
    # Ranked hypotheses
    hypotheses: List[DiagnosticHypothesis] = field(default_factory=list)
    
    # Top diagnosis
    primary_diagnosis: Optional[DiagnosticHypothesis] = None
    confidence: float = 0.0
    
    # Explanation
    summary: str = ""
    physics_explanation: str = ""
    
    def get_report(self) -> str:
        """Generate full diagnostic report"""
        lines = []
        lines.append("# Model-Based Diagnostic Report\n")
        
        lines.append("## Operating Conditions")
        lines.append(f"- RPM: {self.conditions.rpm}")
        lines.append(f"- Load: {self.conditions.load_fraction * 100:.0f}%")
        lines.append(f"- Ambient: {self.conditions.ambient_temp_c}°C")
        lines.append(f"- Vehicle speed: {self.conditions.vehicle_speed_kph} kph")
        lines.append("")
        
        lines.append("## Sensor Readings")
        if self.readings.coolant_temp_c:
            lines.append(f"- Coolant temp: {self.readings.coolant_temp_c}°C")
        lines.append("")
        
        lines.append("## Physics Analysis")
        lines.append(f"- **Expected** coolant temp: {self.expected_temp_c:.1f}°C")
        if self.readings.coolant_temp_c:
            lines.append(f"- **Actual** coolant temp: {self.readings.coolant_temp_c}°C")
            lines.append(f"- **Deviation**: {self.deviation_c:+.1f}°C")
        lines.append("")
        
        if self.deviation_significant:
            lines.append("⚠️ **Significant deviation detected**\n")
        else:
            lines.append("✅ **Operating within expected range**\n")
        
        if self.primary_diagnosis:
            lines.append("## Primary Diagnosis")
            h = self.primary_diagnosis
            lines.append(f"### {h.fault_description}")
            lines.append(f"- Consistency score: {h.consistency_score * 100:.0f}%")
            lines.append(f"- This fault predicts: {h.predicted_temp_c:.1f}°C")
            lines.append(f"- Actual reading: {h.actual_temp_c:.1f}°C")
            lines.append(f"- Match: {abs(h.temp_deviation_c):.1f}°C difference")
            lines.append("")
            
            if h.physics_trace.steps:
                lines.append(h.physics_trace.to_string())
            
            if h.confirming_tests:
                lines.append("\n### Confirming Tests")
                for test in h.confirming_tests:
                    lines.append(f"- {test}")
        
        if len(self.hypotheses) > 1:
            lines.append("\n## Alternative Hypotheses")
            for h in self.hypotheses[1:4]:
                lines.append(f"- {h.fault_description}: {h.consistency_score * 100:.0f}% match")
        
        return "\n".join(lines)


class ModelBasedDiagnostics:
    """
    Main diagnostic engine using physics models.
    
    This is the "brain" that:
    1. Takes sensor data + operating conditions
    2. Simulates expected behavior from physics
    3. Compares to actual readings
    4. Tests fault hypotheses
    5. Ranks by consistency with physics
    
    Usage:
        mbd = ModelBasedDiagnostics()
        
        result = mbd.diagnose(
            conditions=OperatingConditions(rpm=2000, load=0.3, ambient=30),
            readings=SensorReadings(coolant_temp_c=115, fan_running=True)
        )
        
        print(result.get_report())
    """
    
    # Fault definitions with expected symptoms
    FAULT_DEFINITIONS = {
        "thermostat_stuck_closed": {
            "description": "Thermostat stuck closed - coolant cannot reach radiator",
            "expected_symptoms": ["high_temp", "upper_hose_hot", "lower_hose_cold", "radiator_cold"],
            "confirming_tests": [
                "Feel upper radiator hose - should be hot but lower hose cold",
                "Use IR thermometer on radiator - should show cold spots",
                "Remove thermostat and test in boiling water"
            ],
            "typical_temp_deviation": +25,  # °C above normal
        },
        "thermostat_stuck_open": {
            "description": "Thermostat stuck open - engine runs cold",
            "expected_symptoms": ["low_temp", "no_heat", "slow_warmup"],
            "confirming_tests": [
                "Monitor warmup time - should reach temp in 5-10 min",
                "Check heater output temperature",
                "P0128 code likely present"
            ],
            "typical_temp_deviation": -20,
        },
        "water_pump_failed": {
            "description": "Water pump failure - no coolant circulation",
            "expected_symptoms": ["high_temp", "no_flow_sensation", "rapid_temp_rise"],
            "confirming_tests": [
                "Feel upper hose - hot but no flow pulsation",
                "Check for pump weep hole leakage",
                "Listen for bearing noise",
                "Watch temp rise rate at idle - should be rapid"
            ],
            "typical_temp_deviation": +30,
        },
        "water_pump_slipping": {
            "description": "Water pump belt slipping or impeller degraded",
            "expected_symptoms": ["high_temp_under_load", "belt_squeal"],
            "confirming_tests": [
                "Check belt tension and condition",
                "Listen for belt squeal under load",
                "Temp may be OK at idle, high under load"
            ],
            "typical_temp_deviation": +15,
        },
        "radiator_blocked_internal": {
            "description": "Radiator internally blocked - reduced coolant flow",
            "expected_symptoms": ["high_temp", "uneven_radiator_temp"],
            "confirming_tests": [
                "IR scan radiator - look for cold vertical bands",
                "Check coolant flow rate",
                "Flush cooling system"
            ],
            "typical_temp_deviation": +20,
        },
        "radiator_blocked_external": {
            "description": "Radiator externally blocked - bugs, debris",
            "expected_symptoms": ["high_temp_at_low_speed", "normal_at_highway"],
            "confirming_tests": [
                "Visual inspection of radiator fins",
                "Check AC condenser for debris",
                "Temp OK at highway speed, high at idle"
            ],
            "typical_temp_deviation": +15,
        },
        "fan_failed": {
            "description": "Cooling fan not operating",
            "expected_symptoms": ["high_temp_at_idle", "normal_at_highway", "fan_not_running"],
            "confirming_tests": [
                "Observe fan operation when hot",
                "Check fan relay and fuse",
                "Command fan on with scan tool",
                "P0480/P0481 codes likely"
            ],
            "typical_temp_deviation": +20,
        },
        "fan_relay_stuck_on": {
            "description": "Fan relay stuck on - fan runs constantly",
            "expected_symptoms": ["fan_always_on", "slow_warmup", "low_temp"],
            "confirming_tests": [
                "Fan runs immediately at cold start",
                "Check relay operation",
                "May cause slow warmup"
            ],
            "typical_temp_deviation": -10,
        },
        "coolant_low": {
            "description": "Low coolant level - air in system",
            "expected_symptoms": ["high_temp", "fluctuating_temp", "no_heat", "overflow_bubbling"],
            "confirming_tests": [
                "Check coolant level in reservoir and radiator",
                "Look for external leaks",
                "Check for air bubbles in overflow"
            ],
            "typical_temp_deviation": +25,
        },
        "ect_sensor_failed_high": {
            "description": "ECT sensor reading high (false overheating)",
            "expected_symptoms": ["gauge_high", "fan_always_on", "engine_actually_cool"],
            "confirming_tests": [
                "Compare IR thermometer to gauge reading",
                "Check sensor resistance vs. temperature chart",
                "Actual engine feels normal temp to touch"
            ],
            "typical_temp_deviation": 0,  # Engine actually normal
        },
        "ect_sensor_failed_low": {
            "description": "ECT sensor reading low (false cold)",
            "expected_symptoms": ["gauge_low", "fan_never_runs", "rich_running", "engine_actually_hot"],
            "confirming_tests": [
                "Compare IR thermometer to gauge reading",
                "Check if fan ever activates",
                "P0117/P0118 codes"
            ],
            "typical_temp_deviation": 0,  # Sensor wrong, not engine
        },
        "normal": {
            "description": "System operating normally",
            "expected_symptoms": [],
            "confirming_tests": [],
            "typical_temp_deviation": 0,
        },
    }
    
    def __init__(self):
        self.cooling_model = CoolingSystemModel()
        
        # Acceptable deviation from model (°C)
        self.normal_tolerance = 8.0  # Within ±8°C is "normal"
        
    def diagnose(
        self,
        conditions: OperatingConditions,
        readings: SensorReadings
    ) -> DiagnosticResult:
        """
        Perform model-based diagnosis.
        
        Args:
            conditions: Current operating point
            readings: Actual sensor values
            
        Returns:
            DiagnosticResult with physics-based analysis
        """
        # Step 1: Simulate normal operation
        self.cooling_model.reset_faults()
        
        normal_state = self.cooling_model.simulate_steady_state(
            rpm=conditions.rpm,
            load_fraction=conditions.load_fraction,
            ambient_temp_c=conditions.ambient_temp_c,
            vehicle_speed_kph=conditions.vehicle_speed_kph,
            ac_on=conditions.ac_on,
        )
        
        expected_temp = normal_state.coolant_temp_engine
        
        # Step 2: Calculate deviation
        actual_temp = readings.coolant_temp_c if readings.coolant_temp_c else expected_temp
        deviation = actual_temp - expected_temp
        deviation_significant = abs(deviation) > self.normal_tolerance
        
        # Step 3: Test fault hypotheses
        hypotheses = []
        
        for fault_id, fault_info in self.FAULT_DEFINITIONS.items():
            hypothesis = self._test_hypothesis(
                fault_id=fault_id,
                fault_info=fault_info,
                conditions=conditions,
                readings=readings,
                expected_normal_temp=expected_temp
            )
            hypotheses.append(hypothesis)
        
        # Step 4: Rank by consistency score
        hypotheses.sort(key=lambda h: h.consistency_score, reverse=True)
        
        # Step 5: Determine primary diagnosis
        if deviation_significant and hypotheses:
            primary = hypotheses[0]
            # Confidence based on how much better top hypothesis is than alternatives
            if len(hypotheses) > 1:
                confidence = primary.consistency_score - hypotheses[1].consistency_score * 0.5
            else:
                confidence = primary.consistency_score
        else:
            # No significant deviation - probably normal
            primary = next((h for h in hypotheses if h.fault_id == "normal"), hypotheses[0])
            confidence = 0.9 if not deviation_significant else 0.3
        
        # Build result
        result = DiagnosticResult(
            conditions=conditions,
            readings=readings,
            expected_temp_c=expected_temp,
            expected_state=normal_state,
            deviation_c=deviation,
            deviation_significant=deviation_significant,
            hypotheses=hypotheses,
            primary_diagnosis=primary,
            confidence=min(confidence, 1.0),
            summary=self._generate_summary(primary, deviation, conditions),
            physics_explanation=self._generate_physics_explanation(
                expected_temp, actual_temp, deviation, conditions
            ),
        )
        
        return result
    
    def _test_hypothesis(
        self,
        fault_id: str,
        fault_info: Dict,
        conditions: OperatingConditions,
        readings: SensorReadings,
        expected_normal_temp: float
    ) -> DiagnosticHypothesis:
        """Test a single fault hypothesis against physics model"""
        
        # Create physics trace
        trace = PhysicsTrace()
        
        if fault_id == "normal":
            # Normal operation hypothesis
            predicted_temp = expected_normal_temp
            trace.add_step(
                "Normal operation - all components functioning correctly",
                predicted_temp=predicted_temp
            )
        else:
            # Inject fault and simulate
            self.cooling_model.reset_faults()
            self.cooling_model.inject_fault(fault_id)
            
            trace.add_step(f"Injecting fault: {fault_info['description']}")
            
            faulty_state = self.cooling_model.simulate_steady_state(
                rpm=conditions.rpm,
                load_fraction=conditions.load_fraction,
                ambient_temp_c=conditions.ambient_temp_c,
                vehicle_speed_kph=conditions.vehicle_speed_kph,
                ac_on=conditions.ac_on,
            )
            
            predicted_temp = faulty_state.coolant_temp_engine
            
            trace.add_step(
                f"Physics model predicts coolant temp with this fault: {predicted_temp:.1f}°C",
                heat_generated=faulty_state.heat_generated,
                heat_rejected=faulty_state.heat_rejected,
                thermostat_position=faulty_state.thermostat_flow_fraction,
            )
            
            # Reset for next hypothesis
            self.cooling_model.reset_faults()
        
        # Calculate consistency score
        actual_temp = readings.coolant_temp_c if readings.coolant_temp_c else expected_normal_temp
        temp_error = abs(predicted_temp - actual_temp)
        
        # Score based on how close prediction matches actual
        # Perfect match = 1.0, 20°C off = ~0.3
        temp_consistency = math.exp(-temp_error / 15.0)
        
        # Check symptom consistency
        symptom_score = self._check_symptom_consistency(
            fault_info.get("expected_symptoms", []),
            readings
        )
        
        # Combined score (weighted)
        consistency_score = 0.7 * temp_consistency + 0.3 * symptom_score
        
        trace.add_step(
            f"Consistency: temp_match={temp_consistency:.2f}, symptoms={symptom_score:.2f}",
            consistency_score=consistency_score
        )
        
        return DiagnosticHypothesis(
            fault_id=fault_id,
            fault_description=fault_info["description"],
            consistency_score=consistency_score,
            predicted_temp_c=predicted_temp,
            actual_temp_c=actual_temp,
            temp_deviation_c=predicted_temp - actual_temp,
            predicted_symptoms=fault_info.get("expected_symptoms", []),
            symptom_match_score=symptom_score,
            physics_trace=trace,
            confirming_tests=fault_info.get("confirming_tests", []),
        )
    
    def _check_symptom_consistency(
        self,
        expected_symptoms: List[str],
        readings: SensorReadings
    ) -> float:
        """Check how well observed symptoms match expected"""
        if not expected_symptoms:
            return 0.5  # Neutral if no symptoms expected
        
        matches = 0
        checks = 0
        
        symptom_checks = {
            "high_temp": lambda r: r.coolant_temp_c and r.coolant_temp_c > 100,
            "low_temp": lambda r: r.coolant_temp_c and r.coolant_temp_c < 80,
            "fan_running": lambda r: r.fan_running == True,
            "fan_not_running": lambda r: r.fan_running == False,
            "fan_always_on": lambda r: r.fan_running == True,  # Context matters
            "no_heat": lambda r: r.heater_output_hot == False,
            "upper_hose_hot": lambda r: r.upper_hose_hot == True,
            "lower_hose_cold": lambda r: r.lower_hose_hot == False,
        }
        
        for symptom in expected_symptoms:
            if symptom in symptom_checks:
                check_func = symptom_checks[symptom]
                try:
                    result = check_func(readings)
                    if result is not None:
                        checks += 1
                        if result:
                            matches += 1
                except:
                    pass
        
        if checks == 0:
            return 0.5  # No data to check
        
        return matches / checks
    
    def _generate_summary(
        self,
        hypothesis: DiagnosticHypothesis,
        deviation: float,
        conditions: OperatingConditions
    ) -> str:
        """Generate human-readable summary"""
        if abs(deviation) <= self.normal_tolerance:
            return (
                f"Cooling system operating normally. "
                f"At {conditions.rpm} RPM, {conditions.load_fraction*100:.0f}% load, "
                f"temperature is within expected range."
            )
        
        return (
            f"**{hypothesis.fault_description}** "
            f"(consistency: {hypothesis.consistency_score*100:.0f}%). "
            f"Physics model with this fault predicts {hypothesis.predicted_temp_c:.1f}°C, "
            f"matching the observed {hypothesis.actual_temp_c:.1f}°C."
        )
    
    def _generate_physics_explanation(
        self,
        expected: float,
        actual: float,
        deviation: float,
        conditions: OperatingConditions
    ) -> str:
        """Generate physics-based explanation"""
        lines = []
        
        lines.append("### Heat Balance Analysis")
        lines.append("")
        lines.append("At this operating point:")
        lines.append(f"- Engine generating approximately {self._estimate_heat_watts(conditions)/1000:.1f} kW to coolant")
        lines.append(f"- Expected equilibrium temperature: {expected:.1f}°C")
        
        if abs(deviation) > self.normal_tolerance:
            if deviation > 0:
                lines.append(f"- Actual temperature {deviation:.1f}°C HIGHER than expected")
                lines.append("- Heat rejection is insufficient OR heat generation increased")
            else:
                lines.append(f"- Actual temperature {abs(deviation):.1f}°C LOWER than expected")
                lines.append("- Heat rejection exceeds normal OR thermostat not closing")
        else:
            lines.append(f"- Actual temperature within normal range ({deviation:+.1f}°C)")
        
        return "\n".join(lines)
    
    def _estimate_heat_watts(self, conditions: OperatingConditions) -> float:
        """Estimate heat to coolant from operating conditions"""
        return self.cooling_model.calculate_heat_generation(
            conditions.rpm, conditions.load_fraction
        )
