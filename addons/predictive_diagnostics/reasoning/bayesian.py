"""
Bayesian reasoning for diagnostic updates.

Implements belief updating as evidence arrives:
- Prior beliefs from ML model or base rates
- Likelihood of evidence given each failure
- Posterior beliefs after observing evidence

This allows the system to:
1. Start with ML predictions
2. Update beliefs as tests are performed
3. Recommend the most informative next test
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
import math


@dataclass
class BeliefState:
    """
    Current belief distribution over failure hypotheses.
    
    Tracks probability of each failure mode and the evidence
    that led to these beliefs.
    """
    # Probability of each failure (sums to 1)
    probabilities: Dict[str, float] = field(default_factory=dict)
    
    # Evidence observed so far
    evidence: List[Dict] = field(default_factory=list)
    
    # Failures ruled out (probability effectively 0)
    ruled_out: Set[str] = field(default_factory=set)
    
    def __post_init__(self):
        self._normalize()
    
    def _normalize(self):
        """Ensure probabilities sum to 1."""
        total = sum(self.probabilities.values())
        if total > 0:
            self.probabilities = {
                k: v / total for k, v in self.probabilities.items()
            }
    
    def get_top_hypotheses(self, n: int = 5) -> List[Tuple[str, float]]:
        """Get top N hypotheses by probability."""
        sorted_probs = sorted(
            self.probabilities.items(),
            key=lambda x: -x[1]
        )
        return sorted_probs[:n]
    
    def get_entropy(self) -> float:
        """
        Calculate entropy of belief distribution.
        
        Higher entropy = more uncertainty
        Lower entropy = more confident
        """
        entropy = 0.0
        for p in self.probabilities.values():
            if p > 0:
                entropy -= p * math.log2(p)
        return entropy
    
    def is_confident(self, threshold: float = 0.7) -> bool:
        """Check if we're confident in a single diagnosis."""
        if not self.probabilities:
            return False
        top_prob = max(self.probabilities.values())
        return top_prob >= threshold
    
    def copy(self) -> 'BeliefState':
        """Create a copy of this belief state."""
        return BeliefState(
            probabilities=dict(self.probabilities),
            evidence=list(self.evidence),
            ruled_out=set(self.ruled_out),
        )


class BayesianReasoner:
    """
    Bayesian diagnostic reasoning engine.
    
    Updates beliefs using Bayes' rule:
    P(failure|evidence) ∝ P(evidence|failure) * P(failure)
    
    The likelihood P(evidence|failure) comes from our causal knowledge.
    """
    
    def __init__(self, causal_graph=None):
        """
        Args:
            causal_graph: Optional CausalGraph for likelihood lookups
        """
        self.causal_graph = causal_graph
        
        # Likelihood tables: P(evidence|failure)
        # Format: evidence_type -> {failure_id -> probability}
        self._likelihoods = self._build_likelihood_tables()
    
    def _build_likelihood_tables(self) -> Dict[str, Dict[str, float]]:
        """
        Build likelihood tables from domain knowledge.
        
        These encode P(symptom|failure) - the probability of
        observing a symptom given a specific failure.
        """
        # Base likelihoods from physics/knowledge
        likelihoods = {
            # Temperature symptoms
            "coolant_temp_high": {
                "thermostat_stuck_closed": 0.95,
                "radiator_blocked_external": 0.85,
                "radiator_blocked_internal": 0.85,
                "radiator_blocked": 0.90,
                "cooling_fan_not_operating": 0.80,
                "water_pump_failure": 0.90,
                "water_pump_belt_slipping": 0.70,
                "coolant_leak": 0.60,
                "ect_sensor_failed_high": 0.99,  # Sensor reads high
                "normal": 0.05,
            },
            "coolant_temp_low": {
                "thermostat_stuck_open": 0.95,
                "ect_sensor_failed_low": 0.99,
                "cooling_fan_always_on": 0.40,
                "normal": 0.10,  # Can happen in cold weather
            },
            "coolant_temp_normal": {
                "normal": 0.90,
                "pressure_cap_faulty": 0.70,
                "coolant_leak": 0.50,  # Early stage
            },
            
            # DTC symptoms - Cooling
            "dtc_P0217": {  # Engine overtemp
                "thermostat_stuck_closed": 0.80,
                "radiator_blocked": 0.75,
                "cooling_fan_not_operating": 0.70,
                "water_pump_failure": 0.85,
                "coolant_leak": 0.40,
            },
            "dtc_P0128": {  # Coolant temp below threshold
                "thermostat_stuck_open": 0.90,
                "ect_sensor_failed_low": 0.60,
            },
            "dtc_P0118": {  # ECT circuit high
                "ect_sensor_failed_high": 0.95,
            },
            "dtc_P0117": {  # ECT circuit low
                "ect_sensor_failed_low": 0.95,
            },
            
            # =================================================================
            # FUEL SYSTEM DTCs
            # =================================================================
            "system_lean_bank1": {  # P0171
                "vacuum_leak": 0.85,
                "maf_sensor_contaminated": 0.80,
                "fuel_pump_weak": 0.70,
                "fuel_injector_clogged": 0.65,
                "o2_sensor_failed": 0.40,
                "normal": 0.02,
            },

            # Combined fuels trims strong evidence for lean causes
            "high_total_fuel_trim": {
                "vacuum_leak": 0.85,
                "maf_sensor_contaminated": 0.75,
                "fuel_pump_weak": 0.65,
                "fuel_injector_clogged": 0.60,
                "normal": 0.01,
            },
            "moderate_total_fuel_trim": {
                "vacuum_leak": 0.65,
                "maf_sensor_contaminated": 0.55,
                "fuel_pump_weak": 0.45,
                "fuel_injector_clogged": 0.4,
                "normal": 0.02,
            },

            "o2_lean": {
                "vacuum_leak": 0.8,
                "maf_sensor_contaminated": 0.6,
                "normal": 0.01,
            },

            "maf_high": {
                "vacuum_leak": 0.6,
                "maf_sensor_contaminated": 0.8,
                "normal": 0.05,
            },

            "stft_high": {
                "vacuum_leak": 0.75,
                "maf_sensor_contaminated": 0.65,
                "normal": 0.02,
            },
            "ltft_high": {
                "vacuum_leak": 0.75,
                "maf_sensor_contaminated": 0.65,
                "normal": 0.02,
            },
            "system_lean_bank2": {  # P0174
                "vacuum_leak": 0.85,
                "maf_sensor_contaminated": 0.80,
                "fuel_pump_weak": 0.70,
                "fuel_injector_clogged": 0.65,
                "o2_sensor_failed": 0.40,
                "normal": 0.02,
            },
            "system_rich_bank1": {  # P0172
                "fuel_injector_leaking": 0.80,
                "maf_sensor_contaminated": 0.70,
                "o2_sensor_failed": 0.60,
                "pcv_valve_stuck": 0.40,
                "normal": 0.02,
            },
            "system_rich_bank2": {  # P0175
                "fuel_injector_leaking": 0.80,
                "maf_sensor_contaminated": 0.70,
                "o2_sensor_failed": 0.60,
                "pcv_valve_stuck": 0.40,
                "normal": 0.02,
            },
            "fuel_pressure_low": {  # P0087
                "fuel_pump_weak": 0.95,
                "fuel_injector_leaking": 0.30,
                "normal": 0.02,
            },
            "fuel_pressure_high": {  # P0088
                "fuel_pump_weak": 0.20,  # Regulator issue
                "normal": 0.10,
            },
            "fuel_pump_circuit": {  # P0230
                "fuel_pump_weak": 0.90,
                "normal": 0.02,
            },
            "maf_circuit": {  # P0100
                "maf_sensor_contaminated": 0.95,
                "normal": 0.02,
            },
            "maf_range": {  # P0101
                "maf_sensor_contaminated": 0.90,
                "vacuum_leak": 0.40,
                "normal": 0.05,
            },
            "maf_low": {  # P0102
                "maf_sensor_contaminated": 0.85,
                "normal": 0.05,
            },
            "maf_high": {  # P0103
                "maf_sensor_contaminated": 0.85,
                "vacuum_leak": 0.30,
                "normal": 0.05,
            },

            # HV isolation / insulation evidence (OEM-specific)
            "insulation_resistance_low": {
                "tesla_hv_isolation_fault": 0.95,
                "hv_isolation_fault": 0.95,
                "tesla_ptc_heater_failure": 0.60,
                "tesla_contactor_failure": 0.20,
                "normal": 0.01,
            },

            "dtc_insulation_resistance_low": {
                "tesla_hv_isolation_fault": 0.95,
                "hv_isolation_fault": 0.95,
                "tesla_ptc_heater_failure": 0.55,
                "tesla_contactor_failure": 0.15,
                "normal": 0.01,
            },
            "idle_control": {  # P0505
                "vacuum_leak": 0.80,
                "maf_sensor_contaminated": 0.50,
                "pcv_valve_stuck": 0.40,
                "normal": 0.05,
            },
            "idle_rpm_low": {  # P0506
                "vacuum_leak": 0.70,
                "fuel_injector_clogged": 0.50,
                "normal": 0.10,
            },
            "idle_rpm_high": {  # P0507
                "vacuum_leak": 0.85,
                "maf_sensor_contaminated": 0.40,
                "normal": 0.05,
            },
            
            # =================================================================
            # IGNITION/MISFIRE DTCs
            # =================================================================
            "random_misfire": {  # P0300
                "spark_plug_fouled": 0.75,
                "ignition_coil_failed": 0.70,
                "fuel_injector_clogged": 0.60,
                "vacuum_leak": 0.55,
                "fuel_pump_weak": 0.40,
                "low_compression": 0.50,
                "normal": 0.01,
            },
            "misfire_cyl1": {  # P0301
                "spark_plug_fouled": 0.85,
                "ignition_coil_failed": 0.90,
                "fuel_injector_clogged": 0.70,
                "low_compression": 0.60,
                "normal": 0.01,
            },
            "misfire_cyl2": {  # P0302
                "spark_plug_fouled": 0.85,
                "ignition_coil_failed": 0.90,
                "fuel_injector_clogged": 0.70,
                "low_compression": 0.60,
                "normal": 0.01,
            },
            "misfire_cyl3": {  # P0303
                "spark_plug_fouled": 0.85,
                "ignition_coil_failed": 0.90,
                "fuel_injector_clogged": 0.70,
                "low_compression": 0.60,
                "normal": 0.01,
            },
            "misfire_cyl4": {  # P0304
                "spark_plug_fouled": 0.85,
                "ignition_coil_failed": 0.90,
                "fuel_injector_clogged": 0.70,
                "low_compression": 0.60,
                "normal": 0.01,
            },
            "ignition_coil_a": {  # P0351
                "ignition_coil_failed": 0.95,
                "normal": 0.02,
            },
            "ignition_coil_b": {  # P0352
                "ignition_coil_failed": 0.95,
                "normal": 0.02,
            },
            "ignition_coil_c": {  # P0353
                "ignition_coil_failed": 0.95,
                "normal": 0.02,
            },
            "ignition_coil_d": {  # P0354
                "ignition_coil_failed": 0.95,
                "normal": 0.02,
            },
            
            # =================================================================
            # O2 SENSOR DTCs
            # =================================================================
            "o2_sensor_b1s1": {  # P0130
                "o2_sensor_failed": 0.90,
                "vacuum_leak": 0.20,
                "normal": 0.02,
            },
            "o2_low_voltage_b1s1": {  # P0131 - stuck lean
                "vacuum_leak": 0.80,
                "o2_sensor_failed": 0.75,
                "fuel_pump_weak": 0.50,
                "normal": 0.02,
            },
            "o2_high_voltage_b1s1": {  # P0132 - stuck rich
                "fuel_injector_leaking": 0.75,
                "o2_sensor_failed": 0.70,
                "normal": 0.02,
            },
            "o2_slow_response_b1s1": {  # P0133
                "o2_sensor_failed": 0.90,
                "normal": 0.05,
            },
            "o2_no_activity_b1s1": {  # P0134
                "o2_sensor_failed": 0.95,
                "normal": 0.02,
            },
            
            # =================================================================
            # CHARGING SYSTEM DTCs
            # =================================================================
            "system_voltage_low": {  # P0562
                "alternator_failing": 0.90,
                "battery_weak": 0.50,
                "normal": 0.02,
            },
            "system_voltage_high": {  # P0563
                "alternator_failing": 0.85,  # Regulator
                "normal": 0.05,
            },
            
            # Physical observations
            "upper_hose_hot_no_flow": {
                "thermostat_stuck_closed": 0.85,
                "water_pump_failure": 0.90,
            },
            "upper_hose_cold": {
                "thermostat_stuck_open": 0.30,  # Should be warm eventually
                "water_pump_failure": 0.80,
            },
            "coolant_level_low": {
                "coolant_leak": 0.90,
                "pressure_cap_faulty": 0.50,
            },
            "fan_not_running_when_hot": {
                "cooling_fan_not_operating": 0.95,
            },
            "fan_always_running": {
                "cooling_fan_always_on": 0.90,
                "ect_sensor_failed_high": 0.70,
            },
            "steam_from_overflow": {
                "pressure_cap_faulty": 0.80,
                "coolant_leak": 0.40,
            },
            "belt_squealing": {
                "water_pump_belt_slipping": 0.85,
            },
            
            # Test results
            "thermostat_opens_in_hot_water": {
                "thermostat_stuck_closed": 0.02,  # Fails test
                "thermostat_stuck_open": 0.98,   # Passes but might stay open
                "normal": 0.98,
            },
            "thermostat_stays_closed_in_hot_water": {
                "thermostat_stuck_closed": 0.95,
            },
            "pressure_test_fails": {
                "coolant_leak": 0.90,
                "pressure_cap_faulty": 0.60,
            },
            "infrared_temp_matches_gauge": {
                "ect_sensor_failed_high": 0.05,
                "ect_sensor_failed_low": 0.05,
                "normal": 0.95,
            },
            "infrared_temp_differs_from_gauge": {
                "ect_sensor_failed_high": 0.90,
                "ect_sensor_failed_low": 0.90,
            },
            
            # =================================================================
            # ENGINE MECHANICAL SYMPTOMS
            # =================================================================
            "misfire": {
                "spark_plug_fouled": 0.80,
                "ignition_coil_failed": 0.90,
                "fuel_injector_clogged": 0.70,
                "low_compression": 0.85,
                "vacuum_leak": 0.50,
            },
            "rough_idle": {
                "spark_plug_fouled": 0.70,
                "ignition_coil_failed": 0.60,
                "fuel_injector_clogged": 0.65,
                "vacuum_leak": 0.80,
                "maf_sensor_contaminated": 0.60,
                "pcv_valve_stuck": 0.50,
                "low_compression": 0.60,
            },
            "loss_of_power": {
                "spark_plug_fouled": 0.50,
                "ignition_coil_failed": 0.70,
                "fuel_pump_weak": 0.80,
                "fuel_injector_clogged": 0.60,
                "maf_sensor_contaminated": 0.65,
                "timing_chain_stretched": 0.70,
                "low_compression": 0.75,
            },
            "white_smoke_exhaust": {
                "head_gasket_failure": 0.95,
                "ect_sensor_failed_low": 0.20,  # Rich running can cause steam
            },
            "milky_oil": {
                "head_gasket_failure": 0.95,
            },
            "bubbles_in_coolant": {
                "head_gasket_failure": 0.90,
            },
            "oil_pressure_low": {
                "oil_pump_failure": 0.90,
                "normal": 0.05,
            },
            "engine_knock": {
                "oil_pump_failure": 0.70,
                "timing_chain_stretched": 0.40,
            },
            "rattling_noise_startup": {
                "timing_chain_stretched": 0.90,
            },
            
            # =================================================================
            # FUEL SYSTEM SYMPTOMS
            # =================================================================
            "hard_starting": {
                "fuel_pump_weak": 0.70,
                "fuel_injector_leaking": 0.65,
                "ckp_sensor_failed": 0.80,
                "cmp_sensor_failed": 0.50,
                "spark_plug_fouled": 0.60,
                "battery_weak": 0.75,
            },
            "stalling": {
                "fuel_pump_weak": 0.80,
                "maf_sensor_contaminated": 0.60,
                "ckp_sensor_failed": 0.90,
                "vacuum_leak": 0.40,
            },
            "hesitation": {
                "fuel_pump_weak": 0.60,
                "maf_sensor_contaminated": 0.70,
                "spark_plug_fouled": 0.50,
                "ignition_coil_failed": 0.55,
                "fuel_injector_clogged": 0.65,
            },
            "poor_fuel_economy": {
                "o2_sensor_failed": 0.70,
                "maf_sensor_contaminated": 0.65,
                "spark_plug_fouled": 0.50,
                "thermostat_stuck_open": 0.60,
                "fuel_injector_leaking": 0.50,
            },
            "fuel_smell": {
                "fuel_injector_leaking": 0.90,
                "fuel_pump_weak": 0.10,  # External leak sometimes
            },
            "black_smoke_exhaust": {
                "fuel_injector_leaking": 0.80,
                "maf_sensor_contaminated": 0.70,
                "o2_sensor_failed": 0.50,
            },
            "hissing_from_engine": {
                "vacuum_leak": 0.90,
            },
            "high_idle": {
                "vacuum_leak": 0.80,
                "maf_sensor_contaminated": 0.40,
            },
            
            # =================================================================
            # IGNITION SYSTEM SYMPTOMS  
            # =================================================================
            "no_start_cranks": {
                "ckp_sensor_failed": 0.85,
                "fuel_pump_weak": 0.70,
                "ignition_coil_failed": 0.40,  # If all coils
            },
            "check_engine_light_flashing": {
                "ignition_coil_failed": 0.90,
                "spark_plug_fouled": 0.70,
            },
            
            # =================================================================
            # CHARGING/STARTING SYMPTOMS
            # =================================================================
            "battery_light_on": {
                "alternator_failing": 0.90,
                "battery_weak": 0.30,
            },
            "dimming_lights": {
                "alternator_failing": 0.85,
                "battery_weak": 0.50,
            },
            "slow_cranking": {
                "battery_weak": 0.90,
                "starter_failing": 0.70,
            },
            "clicking_no_start": {
                "battery_weak": 0.85,
                "starter_failing": 0.80,
            },
            "grinding_on_start": {
                "starter_failing": 0.90,
            },
            
            # =================================================================
            # TRANSMISSION SYMPTOMS
            # =================================================================
            "transmission_slipping": {
                "trans_fluid_low": 0.80,
                "shift_solenoid_failed": 0.60,
                "torque_converter_shudder": 0.30,
            },
            "harsh_shifts": {
                "shift_solenoid_failed": 0.75,
                "trans_fluid_low": 0.50,
            },
            "delayed_engagement": {
                "trans_fluid_low": 0.85,
                "shift_solenoid_failed": 0.40,
            },
            "transmission_shudder": {
                "torque_converter_shudder": 0.90,
                "trans_fluid_low": 0.40,
            },
            "burnt_fluid_smell": {
                "trans_fluid_low": 0.95,
            },
            "limp_mode": {
                "shift_solenoid_failed": 0.85,
            },
            
            # =================================================================
            # BRAKE SYMPTOMS
            # =================================================================
            "brake_squeal": {
                "brake_pads_worn": 0.90,
            },
            "brake_grinding": {
                "brake_pads_worn": 0.95,  # Metal to metal
            },
            "brake_pulsation": {
                "brake_rotor_warped": 0.90,
            },
            "steering_shake_braking": {
                "brake_rotor_warped": 0.90,
            },
            "pulls_when_braking": {
                "brake_caliper_sticking": 0.85,
            },
            "sinking_brake_pedal": {
                "master_cylinder_failing": 0.90,
            },
            "soft_brake_pedal": {
                "master_cylinder_failing": 0.70,
                "brake_pads_worn": 0.30,
            },
            "abs_light_on": {
                "abs_sensor_failed": 0.90,
            },
            "traction_control_light": {
                "abs_sensor_failed": 0.85,
            },
            "one_wheel_hot": {
                "brake_caliper_sticking": 0.90,
            },
            "burning_smell_wheel": {
                "brake_caliper_sticking": 0.85,
            },
            
            # =================================================================
            # TRANSMISSION DTCs (new/expanded)
            # =================================================================
            "tcc_stuck_off": {  # P0741
                "tcc_stuck_off": 0.95,
                "torque_converter_shudder": 0.30,
                "trans_fluid_low": 0.25,
                "normal": 0.01,
            },
            "tcc_stuck_on": {  # P0742
                "tcc_stuck_on": 0.95,
                "normal": 0.01,
            },
            "tcc_circuit": {  # P0740
                "tcc_stuck_off": 0.70,
                "tcc_stuck_on": 0.30,
                "torque_converter_shudder": 0.50,
                "normal": 0.02,
            },
            "incorrect_gear_ratio": {  # P0730
                "valve_body_failure": 0.85,
                "shift_solenoid_failed": 0.60,
                "trans_fluid_low": 0.50,
                "normal": 0.01,
            },
            "gear_1_ratio": {  # P0731
                "valve_body_failure": 0.80,
                "shift_solenoid_failed": 0.70,
                "trans_fluid_low": 0.40,
                "normal": 0.01,
            },
            "gear_2_ratio": {  # P0732
                "valve_body_failure": 0.80,
                "shift_solenoid_failed": 0.70,
                "trans_fluid_low": 0.40,
                "normal": 0.01,
            },
            "gear_3_ratio": {  # P0733
                "valve_body_failure": 0.80,
                "shift_solenoid_failed": 0.70,
                "trans_fluid_low": 0.40,
                "normal": 0.01,
            },
            "shift_malfunction": {  # P0780
                "valve_body_failure": 0.85,
                "shift_solenoid_failed": 0.75,
                "trans_fluid_low": 0.50,
                "normal": 0.01,
            },
            "input_speed_sensor": {  # P0715
                "trans_speed_sensor_failed": 0.95,
                "normal": 0.02,
            },
            "output_speed_sensor": {  # P0720
                "trans_speed_sensor_failed": 0.95,
                "normal": 0.02,
            },
            "shift_solenoid_a": {  # P0750
                "shift_solenoid_failed": 0.95,
                "normal": 0.02,
            },
            "shift_solenoid_b": {  # P0755
                "shift_solenoid_failed": 0.95,
                "normal": 0.02,
            },
            
            # =================================================================
            # TURBO/BOOST DTCs
            # =================================================================
            "turbo_underboost": {  # P0299
                "turbo_wastegate_stuck_open": 0.85,
                "boost_leak": 0.90,
                "turbo_bearing_failure": 0.60,
                "intercooler_clogged": 0.40,
                "normal": 0.02,
            },
            "turbo_overboost": {  # P0234
                "turbo_wastegate_stuck_closed": 0.95,
                "normal": 0.01,
            },
            "boost_leak_symptom": {
                "boost_leak": 0.95,
                "intercooler_clogged": 0.20,
                "normal": 0.02,
            },
            "turbo_noise": {
                "turbo_bearing_failure": 0.90,
                "boost_leak": 0.30,
                "normal": 0.05,
            },
            "oil_in_intercooler": {
                "turbo_bearing_failure": 0.95,
                "normal": 0.02,
            },
            "blue_smoke": {
                "turbo_bearing_failure": 0.85,
                "pcv_valve_stuck": 0.40,
                "normal": 0.05,
            },
            "lack_of_power_turbo": {
                "boost_leak": 0.85,
                "turbo_wastegate_stuck_open": 0.80,
                "turbo_bearing_failure": 0.70,
                "intercooler_clogged": 0.50,
                "normal": 0.10,
            },
            
            # =================================================================
            # STARTER SYSTEM DTCs
            # =================================================================
            "starter_circuit": {  # P0615
                "starter_motor_failing": 0.80,
                "starter_solenoid_failed": 0.85,
                "battery_weak": 0.30,
                "normal": 0.02,
            },
            "starter_circuit_low": {  # P0616
                "starter_solenoid_failed": 0.90,
                "starter_motor_failing": 0.70,
                "normal": 0.02,
            },
            "starter_circuit_high": {  # P0617
                "starter_solenoid_failed": 0.85,
                "normal": 0.05,
            },
            "click_no_crank": {
                "starter_solenoid_failed": 0.90,
                "battery_weak": 0.80,
                "starter_motor_failing": 0.60,
                "normal": 0.01,
            },
            "starter_spins_no_engage": {
                "starter_solenoid_failed": 0.95,
                "starter_motor_failing": 0.40,
                "normal": 0.01,
            },
            "grinding_start": {
                "starter_motor_failing": 0.90,
                "normal": 0.02,
            },
            
            # =================================================================
            # VVT/TIMING DTCs
            # =================================================================
            "vvt_solenoid_a_bank1": {  # P0010
                "vvt_solenoid_stuck": 0.95,
                "cam_phaser_worn": 0.40,
                "normal": 0.02,
            },
            "vvt_overadvanced_a_b1": {  # P0011
                "vvt_solenoid_stuck": 0.80,
                "cam_phaser_worn": 0.70,
                "timing_chain_stretched": 0.50,
                "oil_pump_failure": 0.30,  # Low oil pressure
                "normal": 0.02,
            },
            "vvt_retarded_a_b1": {  # P0012
                "vvt_solenoid_stuck": 0.80,
                "cam_phaser_worn": 0.70,
                "timing_chain_stretched": 0.50,
                "normal": 0.02,
            },
            "cam_phaser_rattle": {
                "cam_phaser_worn": 0.95,
                "timing_chain_stretched": 0.40,
                "oil_pump_failure": 0.50,
                "normal": 0.02,
            },
            
            # =================================================================
            # ABS-SPECIFIC DTCs
            # =================================================================
            "abs_lf_sensor": {  # C0035
                "wheel_speed_sensor_failed": 0.95,
                "abs_sensor_failed": 0.90,
                "normal": 0.02,
            },
            "abs_rf_sensor": {  # C0040
                "wheel_speed_sensor_failed": 0.95,
                "abs_sensor_failed": 0.90,
                "normal": 0.02,
            },
            "abs_lr_sensor": {  # C0045
                "wheel_speed_sensor_failed": 0.95,
                "abs_sensor_failed": 0.90,
                "normal": 0.02,
            },
            "abs_rr_sensor": {  # C0050
                "wheel_speed_sensor_failed": 0.95,
                "abs_sensor_failed": 0.90,
                "normal": 0.02,
            },
            "abs_pump_motor": {  # C0110
                "abs_pump_motor_failed": 0.95,
                "abs_module_failed": 0.40,
                "normal": 0.02,
            },
            "ebcm_relay": {  # C0265
                "abs_module_failed": 0.90,
                "abs_pump_motor_failed": 0.40,
                "normal": 0.02,
            },
            "lost_comm_abs": {  # U0121
                "abs_module_failed": 0.85,
                "normal": 0.05,
            },
            "speedometer_erratic": {
                "trans_speed_sensor_failed": 0.70,
                "wheel_speed_sensor_failed": 0.60,
                "normal": 0.10,
            },
            
            # =================================================================
            # ADDITIONAL IGNITION DTCs
            # =================================================================
            "ignition_coil_e": {  # P0355
                "ignition_coil_failed": 0.95,
                "ignition_module_failed": 0.50,
                "normal": 0.02,
            },
            "ignition_coil_f": {  # P0356
                "ignition_coil_failed": 0.95,
                "ignition_module_failed": 0.50,
                "normal": 0.02,
            },
            "all_cylinders_misfire": {
                "ignition_module_failed": 0.90,
                "fuel_pump_weak": 0.70,
                "vacuum_leak": 0.40,
                "normal": 0.01,
            },
            "arcing_visible": {
                "secondary_ignition_leak": 0.95,
                "ignition_coil_failed": 0.40,
                "normal": 0.01,
            },
            "misfire_when_humid": {
                "secondary_ignition_leak": 0.90,
                "spark_plug_fouled": 0.50,
                "normal": 0.05,
            },
            "dies_when_hot_restarts_cool": {
                "ignition_module_failed": 0.90,
                "ckp_sensor_failed": 0.70,
                "fuel_pump_weak": 0.50,
                "normal": 0.02,
            },
        }
        
        return likelihoods
    
    def create_initial_state(self, 
                             prior_probs: Optional[Dict[str, float]] = None) -> BeliefState:
        """
        Create initial belief state.
        
        Args:
            prior_probs: Initial probabilities (e.g., from ML model)
                        If None, uses uniform distribution
        """
        if prior_probs is None:
            # Uniform prior over all failures
            failures = [
                "normal",
                # Cooling system
                "thermostat_stuck_closed",
                "thermostat_stuck_open",
                "water_pump_failure",
                "water_pump_belt_slipping",
                "radiator_blocked_external",
                "radiator_blocked_internal",
                "radiator_blocked",
                "cooling_fan_not_operating",
                "cooling_fan_always_on",
                "pressure_cap_faulty",
                "ect_sensor_failed_high",
                "ect_sensor_failed_low",
                "coolant_leak",
                # Engine mechanical
                "low_compression",
                "head_gasket_failure",
                "timing_chain_stretched",
                "oil_pump_failure",
                "pcv_valve_stuck",
                "vvt_solenoid_stuck",
                "cam_phaser_worn",
                # Fuel system
                "fuel_pump_weak",
                "fuel_injector_clogged",
                "fuel_injector_leaking",
                "maf_sensor_contaminated",
                "o2_sensor_failed",
                "vacuum_leak",
                # Ignition system
                "spark_plug_fouled",
                "ignition_coil_failed",
                "ckp_sensor_failed",
                "cmp_sensor_failed",
                "ignition_module_failed",
                "secondary_ignition_leak",
                # Charging/starting
                "alternator_failing",
                "battery_weak",
                "starter_failing",
                "starter_motor_failing",
                "starter_solenoid_failed",
                # Transmission
                "trans_fluid_low",
                "torque_converter_shudder",
                "shift_solenoid_failed",
                "valve_body_failure",
                "tcc_stuck_off",
                "tcc_stuck_on",
                "trans_speed_sensor_failed",
                # EV/HV specific
                "hv_isolation_fault",
                "tesla_hv_isolation_fault",
                # Brakes/ABS
                "brake_pads_worn",
                "brake_rotor_warped",
                "abs_sensor_failed",
                "brake_caliper_sticking",
                "master_cylinder_failing",
                "abs_module_failed",
                "abs_pump_motor_failed",
                "wheel_speed_sensor_failed",
                # Turbo/boost
                "turbo_wastegate_stuck_closed",
                "turbo_wastegate_stuck_open",
                "turbo_bearing_failure",
                "boost_leak",
                "intercooler_clogged",
            ]
            prior_probs = {f: 1.0 / len(failures) for f in failures}
        
        return BeliefState(probabilities=prior_probs)
    
    def update(self, state: BeliefState, 
               evidence_type: str, 
               observed: bool = True) -> BeliefState:
        """
        Update beliefs given new evidence.
        
        Args:
            state: Current belief state
            evidence_type: Type of evidence (e.g., "coolant_temp_high")
            observed: True if evidence is present, False if absent
            
        Returns:
            New belief state after update
        """
        new_state = state.copy()
        
        # Get likelihood table for this evidence
        likelihoods = self._likelihoods.get(evidence_type, {})
        
        if not likelihoods:
            # Unknown evidence type - no update
            new_state.evidence.append({
                "type": evidence_type,
                "observed": observed,
                "impact": "unknown",
            })
            return new_state
        
        # Apply Bayes' rule
        new_probs = {}
        for failure, prior in state.probabilities.items():
            if failure in state.ruled_out:
                new_probs[failure] = 0.0
                continue
            
            # Get likelihood P(evidence|failure)
            likelihood = likelihoods.get(failure, 0.1)  # Default low probability
            
            # If evidence is absent, use complement
            if not observed:
                likelihood = 1.0 - likelihood
            
            # Posterior ∝ likelihood * prior
            new_probs[failure] = likelihood * prior
        
        new_state.probabilities = new_probs
        new_state._normalize()
        
        # Safety-critical overrides: certain evidence should strongly bias results
        # Strong safety-critical handling for isolation evidence
        if observed and evidence_type in ("insulation_resistance_low", "dtc_insulation_resistance_low"):
            # Check if the other complementary evidence has already been observed
            has_other = any(
                e["type"] in ("insulation_resistance_low", "dtc_insulation_resistance_low")
                for e in state.evidence
            )

            if has_other:
                # Both sensor and DTC evidence present — decisive override
                if "hv_isolation_fault" in new_state.probabilities:
                    new_state.probabilities["hv_isolation_fault"] = 0.995
                if "tesla_hv_isolation_fault" in new_state.probabilities:
                    new_state.probabilities["tesla_hv_isolation_fault"] = 0.99

                # Zero out unrelated failures to avoid dilution
                for f in list(new_state.probabilities.keys()):
                    if f not in ("hv_isolation_fault", "tesla_hv_isolation_fault") and not f.startswith("normal"):
                        new_state.probabilities[f] = 0.0
            else:
                # Single piece of evidence: strong bias but allow other possibilities
                if "hv_isolation_fault" in new_state.probabilities:
                    new_state.probabilities["hv_isolation_fault"] = max(new_state.probabilities.get("hv_isolation_fault", 0.0), 0.99)
                if "tesla_hv_isolation_fault" in new_state.probabilities:
                    new_state.probabilities["tesla_hv_isolation_fault"] = max(new_state.probabilities.get("tesla_hv_isolation_fault", 0.0), 0.95)

                for f in list(new_state.probabilities.keys()):
                    if f not in ("hv_isolation_fault", "tesla_hv_isolation_fault") and not f.startswith("normal"):
                        new_state.probabilities[f] = min(new_state.probabilities.get(f, 0.0), 0.0001)

            # Renormalize after forced adjustments
            new_state._normalize()

        # Record evidence
        new_state.evidence.append({
            "type": evidence_type,
            "observed": observed,
            "impact": "updated",
        })
        
        return new_state
    
    def rule_out(self, state: BeliefState, failure_id: str) -> BeliefState:
        """
        Definitively rule out a failure (set probability to 0).
        
        Use when a test conclusively eliminates a possibility.
        """
        new_state = state.copy()
        new_state.ruled_out.add(failure_id)
        new_state.probabilities[failure_id] = 0.0
        new_state._normalize()
        return new_state
    
    def get_best_test(self, state: BeliefState) -> Optional[Dict]:
        """
        Recommend the test that maximizes information gain.
        
        Returns the test that would most reduce entropy (uncertainty).
        """
        # Get top hypotheses to discriminate between
        top_hyps = state.get_top_hypotheses(5)
        if len(top_hyps) < 2:
            return None
        
        top_failures = [h[0] for h in top_hyps if h[0] != "normal"]
        
        # Find tests that discriminate between top failures
        best_test = None
        best_info_gain = 0.0
        
        for evidence_type, likelihoods in self._likelihoods.items():
            # Skip if we've already observed this
            if any(e["type"] == evidence_type for e in state.evidence):
                continue
            
            # Calculate expected information gain
            info_gain = self._expected_info_gain(state, evidence_type)
            
            if info_gain > best_info_gain:
                best_info_gain = info_gain
                best_test = {
                    "test": evidence_type,
                    "expected_info_gain": info_gain,
                    "description": self._get_test_description(evidence_type),
                }
        
        return best_test
    
    def _expected_info_gain(self, state: BeliefState, evidence_type: str) -> float:
        """Calculate expected information gain from a test."""
        current_entropy = state.get_entropy()
        
        likelihoods = self._likelihoods.get(evidence_type, {})
        if not likelihoods:
            return 0.0
        
        # P(evidence) = sum over failures of P(evidence|failure) * P(failure)
        p_evidence = sum(
            likelihoods.get(f, 0.1) * p
            for f, p in state.probabilities.items()
        )
        p_no_evidence = 1.0 - p_evidence
        
        # Expected entropy after observing test result
        expected_entropy = 0.0
        
        for observed, p_outcome in [(True, p_evidence), (False, p_no_evidence)]:
            if p_outcome <= 0:
                continue
            
            # Calculate posterior entropy
            hypothetical_state = self.update(state, evidence_type, observed)
            posterior_entropy = hypothetical_state.get_entropy()
            expected_entropy += p_outcome * posterior_entropy
        
        return current_entropy - expected_entropy
    
    def _get_test_description(self, evidence_type: str) -> str:
        """Get human-readable description of a test."""
        descriptions = {
            "coolant_temp_high": "Check if coolant temperature is above normal",
            "coolant_temp_low": "Check if coolant temperature stays below normal",
            "dtc_P0217": "Check for DTC P0217 (engine overtemperature)",
            "dtc_P0128": "Check for DTC P0128 (coolant below threshold)",
            "upper_hose_hot_no_flow": "Feel upper radiator hose - is it hot with no flow?",
            "coolant_level_low": "Check coolant reservoir level",
            "fan_not_running_when_hot": "Observe if fan runs when engine is hot",
            "thermostat_opens_in_hot_water": "Remove thermostat and test in boiling water",
            "pressure_test_fails": "Perform cooling system pressure test",
            "infrared_temp_matches_gauge": "Compare IR thermometer to temp gauge",
            "belt_squealing": "Listen for belt noise during operation",
        }
        return descriptions.get(evidence_type, f"Check: {evidence_type}")
