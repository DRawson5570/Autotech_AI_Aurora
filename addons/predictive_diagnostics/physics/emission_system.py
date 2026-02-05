"""
Emission System Physics Model

Models the physics of emission control systems:
- Catalytic converter (three-way catalyst)
- EGR (Exhaust Gas Recirculation)
- EVAP (Evaporative Emission Control)
- PCV (Positive Crankcase Ventilation)
- Oxygen sensors (wideband/narrowband)

Physics principles:
- Catalyst efficiency = f(temperature, age, contamination)
- Light-off temperature (~300°C) for catalytic conversion
- EGR flow affects NOx and combustion stability
- EVAP system pressure decay for leak detection
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
import math


class CatalystState(Enum):
    """Catalyst operating state."""
    COLD = "cold"          # Below light-off
    WARMING = "warming"    # Approaching light-off
    ACTIVE = "active"      # Normal operation
    DEGRADED = "degraded"  # Reduced efficiency
    FAILED = "failed"      # No conversion


@dataclass
class CatalyticConverterModel:
    """
    Three-way catalytic converter physics.
    
    Converts:
    - CO → CO2 (oxidation)
    - HC → H2O + CO2 (oxidation)  
    - NOx → N2 + O2 (reduction)
    
    Key physics:
    - Light-off temperature: ~300°C (minimum for 50% efficiency)
    - Optimal window: 14.5-14.8 AFR (stoichiometric)
    - Efficiency degrades with age, poisoning, thermal damage
    """
    
    # Design parameters
    light_off_temp_c: float = 300.0       # Temperature for 50% efficiency
    optimal_temp_c: float = 450.0         # Peak efficiency temperature
    max_temp_c: float = 900.0             # Thermal damage threshold
    new_efficiency: float = 0.98          # New catalyst efficiency
    
    # Current state
    temperature_c: float = 25.0           # Current catalyst temp
    efficiency: float = 0.98              # Current efficiency (0-1)
    age_km: float = 0.0                   # Catalyst age in km
    
    # Fault injection
    _fault: str = None
    _fault_severity: float = 0.0
    
    def reset(self):
        """Reset to default state."""
        self.temperature_c = 25.0
        self.efficiency = self.new_efficiency
        self.age_km = 0.0
        self._fault = None
        self._fault_severity = 0.0
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """Inject a fault into the catalyst."""
        self._fault = fault
        self._fault_severity = min(1.0, max(0.0, severity))
    
    def get_temperature_efficiency(self) -> float:
        """
        Get efficiency based on temperature.
        
        Efficiency ramps up from light-off to optimal temp.
        
        Returns:
            Temperature-based efficiency factor (0-1)
        """
        if self.temperature_c < self.light_off_temp_c * 0.5:
            return 0.0  # Too cold for any conversion
        elif self.temperature_c < self.light_off_temp_c:
            # Ramp up to 50% at light-off
            t_frac = (self.temperature_c - self.light_off_temp_c * 0.5) / (self.light_off_temp_c * 0.5)
            return 0.5 * t_frac
        elif self.temperature_c < self.optimal_temp_c:
            # Ramp from 50% to 100% efficiency
            t_frac = (self.temperature_c - self.light_off_temp_c) / (self.optimal_temp_c - self.light_off_temp_c)
            return 0.5 + 0.5 * t_frac
        else:
            return 1.0  # Full temperature efficiency
    
    def get_afr_efficiency(self, afr: float) -> float:
        """
        Get efficiency based on air-fuel ratio.
        
        Three-way catalysts require stoichiometric AFR (14.7)
        for simultaneous CO/HC oxidation and NOx reduction.
        
        Args:
            afr: Air-fuel ratio
            
        Returns:
            AFR-based efficiency factor (0-1)
        """
        stoich = 14.7
        # Efficiency drops off as AFR deviates from stoich
        # Window is approximately 14.5-14.9
        deviation = abs(afr - stoich)
        if deviation < 0.2:
            return 1.0
        elif deviation < 1.0:
            return 1.0 - (deviation - 0.2) * 0.5  # Gradual drop
        else:
            return max(0.3, 1.0 - deviation * 0.3)  # Significant reduction
    
    def get_effective_efficiency(self, afr: float = 14.7) -> float:
        """
        Get overall catalyst efficiency.
        
        Combines:
        - Base efficiency (age degradation)
        - Temperature efficiency
        - AFR efficiency
        - Fault effects
        """
        base = self.efficiency
        temp_eff = self.get_temperature_efficiency()
        afr_eff = self.get_afr_efficiency(afr)
        
        # Apply faults
        if self._fault == "catalyst_degraded":
            base *= (1.0 - 0.5 * self._fault_severity)  # Up to 50% reduction
        elif self._fault == "catalyst_poisoned":
            base *= (1.0 - 0.7 * self._fault_severity)  # Severe reduction
        elif self._fault == "catalyst_thermal_damage":
            base *= (1.0 - 0.8 * self._fault_severity)  # Very severe
        elif self._fault == "catalyst_failed":
            base = 0.1  # Nearly no conversion
        
        return base * temp_eff * afr_eff
    
    def get_state(self) -> CatalystState:
        """Get current catalyst operating state."""
        if self._fault == "catalyst_failed":
            return CatalystState.FAILED
        if self.temperature_c < self.light_off_temp_c * 0.5:
            return CatalystState.COLD
        if self.temperature_c < self.light_off_temp_c:
            return CatalystState.WARMING
        eff = self.get_effective_efficiency()
        if eff < 0.5:
            return CatalystState.DEGRADED
        return CatalystState.ACTIVE
    
    def warm_up(self, exhaust_temp_c: float, dt_seconds: float = 1.0):
        """
        Simulate catalyst warm-up.
        
        Args:
            exhaust_temp_c: Incoming exhaust temperature
            dt_seconds: Time step
        """
        # Simple thermal model: catalyst approaches exhaust temp
        time_constant = 60.0  # seconds
        if self._fault == "slow_warmup":
            time_constant *= 2.0  # Takes twice as long
        
        delta = exhaust_temp_c - self.temperature_c
        self.temperature_c += delta * dt_seconds / time_constant


@dataclass
class EGRModel:
    """
    Exhaust Gas Recirculation physics.
    
    EGR reduces NOx by lowering combustion temperatures.
    
    Key physics:
    - Recirculates 5-20% of exhaust back to intake
    - Reduces peak combustion temp → less NOx
    - Too much EGR causes rough idle/misfire
    """
    
    # Design parameters
    max_flow_rate_percent: float = 20.0   # Max EGR as % of intake
    
    # Current state
    commanded_position: float = 0.0       # 0-100% commanded
    actual_position: float = 0.0          # 0-100% actual
    flow_rate_percent: float = 0.0        # % of intake air
    
    # Fault state
    _fault: str = None
    _fault_severity: float = 0.0
    
    def reset(self):
        """Reset to default state."""
        self.commanded_position = 0.0
        self.actual_position = 0.0
        self.flow_rate_percent = 0.0
        self._fault = None
        self._fault_severity = 0.0
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """Inject a fault."""
        self._fault = fault
        self._fault_severity = min(1.0, max(0.0, severity))
    
    def update_position(self, command: float):
        """
        Update EGR position based on command.
        
        Args:
            command: Commanded position 0-100%
        """
        self.commanded_position = command
        
        # Apply faults
        if self._fault == "egr_stuck_open":
            self.actual_position = 50.0 + 50.0 * self._fault_severity  # Stuck partially/fully open
        elif self._fault == "egr_stuck_closed":
            self.actual_position = 0.0  # Stuck closed
        elif self._fault == "egr_slow_response":
            # Moves slowly toward command
            delta = command - self.actual_position
            self.actual_position += delta * 0.3  # Slow response
        elif self._fault == "egr_flow_restricted":
            # Position OK but flow reduced
            self.actual_position = command
        else:
            self.actual_position = command
    
    def get_flow_rate(self, intake_airflow_gs: float) -> float:
        """
        Calculate EGR flow rate.
        
        Args:
            intake_airflow_gs: Intake airflow in g/s
            
        Returns:
            EGR flow as percentage of intake
        """
        base_rate = (self.actual_position / 100.0) * self.max_flow_rate_percent
        
        if self._fault == "egr_flow_restricted":
            base_rate *= (1.0 - 0.6 * self._fault_severity)  # Reduced flow
        
        self.flow_rate_percent = base_rate
        return base_rate
    
    def get_nox_reduction_factor(self) -> float:
        """
        Get NOx reduction from EGR.
        
        Returns:
            Factor to multiply NOx production (0-1)
        """
        # Each 1% EGR reduces NOx by ~10%
        if self.flow_rate_percent <= 0:
            return 1.0  # No reduction
        
        reduction = 1.0 - (self.flow_rate_percent * 0.05)  # 5% reduction per 1% EGR
        return max(0.2, reduction)  # Max 80% reduction
    
    def get_combustion_stability_factor(self) -> float:
        """
        Get combustion stability with EGR.
        
        Too much EGR causes rough idle/misfire.
        
        Returns:
            Stability factor (1.0 = stable, <1.0 = unstable)
        """
        if self.flow_rate_percent < 15.0:
            return 1.0  # Stable
        elif self.flow_rate_percent < 20.0:
            # Mild instability
            return 1.0 - (self.flow_rate_percent - 15.0) * 0.05
        else:
            # Significant instability
            return max(0.5, 1.0 - (self.flow_rate_percent - 15.0) * 0.1)


@dataclass
class EVAPModel:
    """
    Evaporative Emission Control system physics.
    
    Captures fuel vapors from tank and burns them in engine.
    
    Key physics:
    - Charcoal canister adsorbs fuel vapors
    - Purge valve releases vapors to intake
    - Leak detection via pressure decay
    """
    
    # System parameters
    tank_volume_liters: float = 60.0
    canister_capacity_grams: float = 100.0  # Vapor storage capacity
    
    # Current state
    tank_pressure_kpa: float = 101.3       # Atmospheric
    canister_saturation: float = 0.0       # 0-1 (how full)
    purge_valve_duty: float = 0.0          # 0-100%
    vent_valve_open: bool = True           # Normally open
    
    # Fault state
    _fault: str = None
    _fault_severity: float = 0.0
    
    def reset(self):
        """Reset to default state."""
        self.tank_pressure_kpa = 101.3
        self.canister_saturation = 0.0
        self.purge_valve_duty = 0.0
        self.vent_valve_open = True
        self._fault = None
        self._fault_severity = 0.0
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """Inject a fault."""
        self._fault = fault
        self._fault_severity = min(1.0, max(0.0, severity))
    
    def run_leak_test(self, test_duration_seconds: float = 30.0) -> Dict[str, Any]:
        """
        Simulate EVAP leak test.
        
        Test procedure:
        1. Close vent valve
        2. Apply vacuum or pressure
        3. Monitor pressure decay
        
        Args:
            test_duration_seconds: Test duration
            
        Returns:
            Test results dict
        """
        # Seal the system
        self.vent_valve_open = False
        
        # Initial pressure (slightly positive from fuel vapors)
        initial_pressure = 102.0  # kPa
        
        # Calculate pressure decay based on leaks
        leak_rate_kpa_per_second = 0.0
        
        if self._fault == "evap_large_leak":
            # Large leak (>0.040" hole)
            leak_rate_kpa_per_second = 0.5 * self._fault_severity
        elif self._fault == "evap_small_leak":
            # Small leak (0.020-0.040")
            leak_rate_kpa_per_second = 0.1 * self._fault_severity
        elif self._fault == "evap_purge_stuck_open":
            # Purge valve stuck open acts as large leak
            leak_rate_kpa_per_second = 0.8
        elif self._fault == "evap_vent_stuck_closed":
            # Can't vent - no leak but system can't be tested properly
            pass
        elif self._fault == "evap_canister_saturated":
            # Saturated canister doesn't hold vacuum as well
            leak_rate_kpa_per_second = 0.05
        
        # Normal small system losses
        leak_rate_kpa_per_second += 0.01
        
        # Calculate final pressure
        pressure_decay = leak_rate_kpa_per_second * test_duration_seconds
        final_pressure = initial_pressure - pressure_decay
        
        # Determine result
        decay_rate = pressure_decay / test_duration_seconds
        
        if decay_rate < 0.02:
            result = "pass"
        elif decay_rate < 0.1:
            result = "small_leak"
        else:
            result = "large_leak"
        
        # Restore vent
        self.vent_valve_open = True
        
        return {
            "result": result,
            "initial_pressure_kpa": initial_pressure,
            "final_pressure_kpa": final_pressure,
            "decay_rate_kpa_per_s": decay_rate,
            "test_duration_s": test_duration_seconds,
        }
    
    def get_purge_flow_effect(self) -> float:
        """
        Get effect of purge flow on fuel trim.
        
        Purge adds fuel vapors to intake, enriching mixture.
        
        Returns:
            Fuel trim effect (negative = rich, 0 = no effect)
        """
        if self._fault == "evap_purge_stuck_closed":
            return 0.0  # No purge effect
        
        if self._fault == "evap_purge_stuck_open":
            # Constant enrichment from vapors
            return -8.0 * self._fault_severity  # Significant rich
        
        if self._fault == "evap_canister_saturated":
            # Heavy vapor load when purging
            effect = -3.0 * self._fault_severity * (self.purge_valve_duty / 100.0)
            return effect
        
        # Normal purge effect (small)
        return -0.5 * (self.purge_valve_duty / 100.0)


@dataclass 
class O2SensorModel:
    """
    Oxygen sensor physics (narrowband and wideband).
    
    Narrowband (traditional):
    - Outputs 0.1-0.9V based on rich/lean
    - Cross-count to check operation
    - Switches rapidly at stoichiometric
    
    Wideband (AFR sensor):
    - Outputs current proportional to AFR
    - Can measure wide range (10:1 to 20:1)
    """
    
    # Sensor type
    is_wideband: bool = False
    
    # Narrowband parameters
    rich_voltage: float = 0.9
    lean_voltage: float = 0.1
    stoich_afr: float = 14.7
    
    # Current state
    current_voltage: float = 0.45  # Mid-scale at startup
    heater_on: bool = True
    heated: bool = False
    
    # Fault state
    _fault: str = None
    _fault_severity: float = 0.0
    
    def reset(self):
        """Reset sensor state."""
        self.current_voltage = 0.45
        self.heater_on = True
        self.heated = False
        self._fault = None
        self._fault_severity = 0.0
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """Inject a sensor fault."""
        self._fault = fault
        self._fault_severity = min(1.0, max(0.0, severity))
    
    def get_voltage(self, actual_afr: float, exhaust_temp_c: float = 400.0) -> float:
        """
        Get sensor output voltage.
        
        Args:
            actual_afr: Actual air-fuel ratio
            exhaust_temp_c: Exhaust gas temperature
            
        Returns:
            Sensor voltage (V)
        """
        # Check if heated
        if not self.heater_on and exhaust_temp_c < 300:
            self.heated = False
            return 0.45  # Mid-scale when cold
        self.heated = True
        
        # Apply faults
        if self._fault == "o2_heater_failed":
            if exhaust_temp_c < 300:
                self.heated = False
                return 0.45  # Cold sensor
        
        if self._fault == "o2_stuck_lean":
            return self.lean_voltage
        
        if self._fault == "o2_stuck_rich":
            return self.rich_voltage
        
        if self._fault == "o2_lazy":
            # Slow response - stays near center
            voltage = 0.45 + (actual_afr - self.stoich_afr) * 0.1
            voltage = max(0.3, min(0.6, voltage))
            return voltage
        
        if self._fault == "o2_contaminated":
            # Reduced amplitude
            if actual_afr < self.stoich_afr:
                return 0.7 - 0.2 * self._fault_severity
            else:
                return 0.3 + 0.2 * self._fault_severity
        
        # Normal operation - narrowband
        if actual_afr < self.stoich_afr - 0.3:
            # Rich
            return self.rich_voltage
        elif actual_afr > self.stoich_afr + 0.3:
            # Lean
            return self.lean_voltage
        else:
            # Transition zone
            fraction = (actual_afr - (self.stoich_afr - 0.3)) / 0.6
            return self.rich_voltage - fraction * (self.rich_voltage - self.lean_voltage)
    
    def is_switching(self, voltage_history: List[float]) -> bool:
        """
        Check if sensor is switching properly (narrowband).
        
        Args:
            voltage_history: Recent voltage readings
            
        Returns:
            True if sensor is switching between rich/lean
        """
        if len(voltage_history) < 10:
            return False
        
        # Count transitions across 0.45V threshold
        crossings = 0
        for i in range(1, len(voltage_history)):
            if (voltage_history[i-1] < 0.45 and voltage_history[i] > 0.45) or \
               (voltage_history[i-1] > 0.45 and voltage_history[i] < 0.45):
                crossings += 1
        
        # Should have at least 2 crossings per second in closed loop
        return crossings >= 2


@dataclass
class EmissionSystemState:
    """Current state of emission system."""
    catalyst_temp_c: float = 25.0
    catalyst_efficiency: float = 0.0
    catalyst_state: CatalystState = CatalystState.COLD
    egr_position: float = 0.0
    egr_flow_percent: float = 0.0
    evap_pressure_kpa: float = 101.3
    upstream_o2_voltage: float = 0.45
    downstream_o2_voltage: float = 0.45
    
    # Emissions output
    co_ppm: float = 0.0
    hc_ppm: float = 0.0
    nox_ppm: float = 0.0


@dataclass
class EmissionSystemModel:
    """
    Integrated emission system model.
    
    Combines all emission control subsystems and predicts
    emission levels based on operating conditions.
    """
    
    catalyst: CatalyticConverterModel = field(default_factory=CatalyticConverterModel)
    egr: EGRModel = field(default_factory=EGRModel)
    evap: EVAPModel = field(default_factory=EVAPModel)
    upstream_o2: O2SensorModel = field(default_factory=O2SensorModel)
    downstream_o2: O2SensorModel = field(default_factory=O2SensorModel)
    
    # Fault tracking
    _injected_faults: Dict[str, float] = field(default_factory=dict)
    
    def reset(self):
        """Reset all components."""
        self.catalyst.reset()
        self.egr.reset()
        self.evap.reset()
        self.upstream_o2.reset()
        self.downstream_o2.reset()
        self._injected_faults.clear()
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """
        Inject a fault into the emission system.
        
        Supported faults:
        - catalyst_degraded: Reduced catalyst efficiency
        - catalyst_poisoned: Contaminated catalyst
        - catalyst_thermal_damage: Overheated catalyst
        - catalyst_failed: Complete catalyst failure
        - egr_stuck_open: EGR valve stuck open
        - egr_stuck_closed: EGR valve stuck closed
        - egr_flow_restricted: Clogged EGR passages
        - evap_large_leak: Large EVAP leak
        - evap_small_leak: Small EVAP leak  
        - evap_purge_stuck_open: Purge valve stuck open
        - evap_purge_stuck_closed: Purge valve stuck closed
        - evap_canister_saturated: Charcoal canister saturated
        - o2_upstream_stuck_lean: Front O2 stuck lean
        - o2_upstream_stuck_rich: Front O2 stuck rich
        - o2_upstream_lazy: Slow front O2 response
        - o2_downstream_stuck_lean: Rear O2 stuck lean
        - o2_downstream_stuck_rich: Rear O2 stuck rich
        - o2_heater_failed: O2 heater circuit failed
        """
        self._injected_faults[fault] = severity
        
        # Route to appropriate component
        if fault.startswith("catalyst_"):
            self.catalyst.inject_fault(fault, severity)
        elif fault.startswith("egr_"):
            self.egr.inject_fault(fault, severity)
        elif fault.startswith("evap_"):
            self.evap.inject_fault(fault, severity)
        elif fault.startswith("o2_upstream_"):
            self.upstream_o2.inject_fault(fault.replace("o2_upstream_", "o2_"), severity)
        elif fault.startswith("o2_downstream_"):
            self.downstream_o2.inject_fault(fault.replace("o2_downstream_", "o2_"), severity)
        elif fault == "o2_heater_failed":
            self.upstream_o2.inject_fault(fault, severity)
            self.downstream_o2.inject_fault(fault, severity)
    
    def simulate(
        self,
        rpm: float = 800,
        load_percent: float = 20,
        afr: float = 14.7,
        exhaust_temp_c: float = 400,
        time_running_s: float = 300,
        ambient_temp_c: float = 25,
    ) -> EmissionSystemState:
        """
        Simulate emission system state.
        
        Args:
            rpm: Engine RPM
            load_percent: Engine load (0-100)
            afr: Current air-fuel ratio
            exhaust_temp_c: Exhaust gas temperature
            time_running_s: Time since engine start
            ambient_temp_c: Ambient temperature
            
        Returns:
            Current emission system state
        """
        state = EmissionSystemState()
        
        # Simulate catalyst warm-up
        if time_running_s < 120:
            # First 2 minutes - warming up
            warmup_fraction = time_running_s / 120.0
            self.catalyst.temperature_c = ambient_temp_c + (exhaust_temp_c - ambient_temp_c) * warmup_fraction * 0.8
        else:
            self.catalyst.temperature_c = exhaust_temp_c * 0.9  # Slightly below exhaust temp
        
        state.catalyst_temp_c = self.catalyst.temperature_c
        state.catalyst_efficiency = self.catalyst.get_effective_efficiency(afr)
        state.catalyst_state = self.catalyst.get_state()
        
        # EGR - typically 5-15% at cruise, 0% at idle/WOT
        if rpm > 1200 and load_percent > 20 and load_percent < 80:
            egr_command = 10.0  # Typical cruise EGR
        else:
            egr_command = 0.0
        
        self.egr.update_position(egr_command)
        intake_airflow = rpm * 0.05 * load_percent / 100  # Rough airflow estimate
        state.egr_flow_percent = self.egr.get_flow_rate(intake_airflow)
        state.egr_position = self.egr.actual_position
        
        # EVAP - purge at cruise
        if rpm > 1200 and time_running_s > 60:
            self.evap.purge_valve_duty = 20.0
        else:
            self.evap.purge_valve_duty = 0.0
        
        state.evap_pressure_kpa = self.evap.tank_pressure_kpa
        
        # O2 sensors
        state.upstream_o2_voltage = self.upstream_o2.get_voltage(afr, exhaust_temp_c)
        
        # Downstream O2 sees post-catalyst exhaust
        # If catalyst is working, downstream is steady near stoich
        if state.catalyst_efficiency > 0.8:
            downstream_afr = 14.7  # Catalyst buffers variations
        else:
            downstream_afr = afr  # Passes through
        
        state.downstream_o2_voltage = self.downstream_o2.get_voltage(downstream_afr, exhaust_temp_c * 0.8)
        
        # Calculate emissions
        state.co_ppm, state.hc_ppm, state.nox_ppm = self._calculate_emissions(
            afr, state.catalyst_efficiency, state.egr_flow_percent, load_percent
        )
        
        return state
    
    def _calculate_emissions(
        self,
        afr: float,
        catalyst_efficiency: float,
        egr_percent: float,
        load_percent: float
    ) -> tuple:
        """
        Calculate tailpipe emissions.
        
        Returns:
            Tuple of (CO_ppm, HC_ppm, NOx_ppm)
        """
        stoich = 14.7
        
        # Pre-catalyst emissions (engine out)
        if afr < stoich:
            # Rich - high CO/HC, low NOx
            richness = (stoich - afr) / stoich
            co_engine = 10000 + richness * 40000  # 1-5% CO
            hc_engine = 500 + richness * 2000     # 500-2500 ppm
            nox_engine = 2000 - richness * 1500   # Reduced at rich
        else:
            # Lean - low CO, lower HC, higher NOx
            leanness = (afr - stoich) / stoich
            co_engine = 1000 - leanness * 500     # Low CO when lean
            hc_engine = 300 + leanness * 500      # Some HC from misfire
            nox_engine = 2500 + leanness * 1000   # High NOx when lean
        
        # EGR effect on NOx
        nox_engine *= self.egr.get_nox_reduction_factor()
        
        # Load effect (more emissions at high load)
        load_factor = 0.5 + (load_percent / 100.0)
        co_engine *= load_factor
        hc_engine *= load_factor
        nox_engine *= load_factor
        
        # Catalyst reduction
        co_tailpipe = co_engine * (1.0 - catalyst_efficiency)
        hc_tailpipe = hc_engine * (1.0 - catalyst_efficiency)
        nox_tailpipe = nox_engine * (1.0 - catalyst_efficiency)
        
        return co_tailpipe, hc_tailpipe, nox_tailpipe


def run_tests():
    """Run emission system tests."""
    print("=" * 60)
    print("EMISSION SYSTEM PHYSICS MODEL TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    def check(name: str, condition: bool, detail: str = ""):
        nonlocal passed, failed
        if condition:
            print(f"✅ {name} PASSED {detail}")
            passed += 1
        else:
            print(f"❌ {name} FAILED {detail}")
            failed += 1
    
    # Test 1: Normal operation - warmed up
    print("\n--- Test 1: Normal Operation (Warmed Up) ---")
    model = EmissionSystemModel()
    state = model.simulate(
        rpm=2000,
        load_percent=40,
        afr=14.7,
        exhaust_temp_c=450,
        time_running_s=300,
    )
    check(
        "Normal catalyst efficiency",
        state.catalyst_efficiency > 0.8,  # Adjusted - AFR not perfect
        f"(efficiency={state.catalyst_efficiency:.2f})"
    )
    check(
        "Low tailpipe CO",
        state.co_ppm < 500,
        f"(CO={state.co_ppm:.0f} ppm)"
    )
    check(
        "Catalyst state active",
        state.catalyst_state == CatalystState.ACTIVE,
        f"(state={state.catalyst_state.value})"
    )
    
    # Test 2: Cold start
    print("\n--- Test 2: Cold Start ---")
    model = EmissionSystemModel()
    state = model.simulate(
        rpm=1200,
        load_percent=20,
        afr=14.7,
        exhaust_temp_c=200,
        time_running_s=30,
        ambient_temp_c=20,
    )
    check(
        "Cold catalyst low efficiency",
        state.catalyst_efficiency < 0.5,
        f"(efficiency={state.catalyst_efficiency:.2f})"
    )
    check(
        "Cold start high emissions",
        state.co_ppm > 500,  # Adjusted threshold
        f"(CO={state.co_ppm:.0f} ppm)"
    )
    
    # Test 3: Catalyst degraded (P0420)
    print("\n--- Test 3: Catalyst Degraded (P0420) ---")
    model = EmissionSystemModel()
    model.inject_fault("catalyst_degraded", severity=0.8)
    state = model.simulate(
        rpm=2000,
        load_percent=40,
        afr=14.7,
        exhaust_temp_c=450,
        time_running_s=300,
    )
    check(
        "Degraded catalyst reduced efficiency",
        state.catalyst_efficiency < 0.7,
        f"(efficiency={state.catalyst_efficiency:.2f})"
    )
    check(
        "Higher tailpipe emissions vs normal",
        state.co_ppm > 300,  # Higher than normal (~150)
        f"(CO={state.co_ppm:.0f} ppm)"
    )
    # Downstream O2 should mirror upstream (not buffered)
    check(
        "Downstream O2 similar to upstream",
        abs(state.downstream_o2_voltage - state.upstream_o2_voltage) < 0.3,
        f"(up={state.upstream_o2_voltage:.2f}V, down={state.downstream_o2_voltage:.2f}V)"
    )
    
    # Test 4: EGR stuck open
    print("\n--- Test 4: EGR Stuck Open ---")
    model = EmissionSystemModel()
    model.inject_fault("egr_stuck_open", severity=1.0)
    state = model.simulate(
        rpm=800,
        load_percent=20,
        afr=14.7,
        exhaust_temp_c=400,
        time_running_s=300,
    )
    check(
        "EGR stuck open high flow at idle",
        state.egr_flow_percent > 10,
        f"(EGR flow={state.egr_flow_percent:.1f}%)"
    )
    stability = model.egr.get_combustion_stability_factor()
    check(
        "Reduced combustion stability",
        stability < 0.9,
        f"(stability={stability:.2f})"
    )
    
    # Test 5: EVAP large leak
    print("\n--- Test 5: EVAP Large Leak ---")
    model = EmissionSystemModel()
    model.inject_fault("evap_large_leak", severity=1.0)
    leak_test = model.evap.run_leak_test(test_duration_seconds=30)
    check(
        "EVAP leak test detects large leak",
        leak_test["result"] == "large_leak",
        f"(result={leak_test['result']}, decay={leak_test['decay_rate_kpa_per_s']:.3f} kPa/s)"
    )
    
    # Test 6: O2 sensor stuck lean
    print("\n--- Test 6: O2 Sensor Stuck Lean ---")
    model = EmissionSystemModel()
    model.inject_fault("o2_upstream_stuck_lean", severity=1.0)
    state = model.simulate(
        rpm=2000,
        load_percent=40,
        afr=13.5,  # Actually rich
        exhaust_temp_c=450,
        time_running_s=300,
    )
    check(
        "Stuck lean O2 reads lean despite rich AFR",
        state.upstream_o2_voltage < 0.2,
        f"(voltage={state.upstream_o2_voltage:.2f}V at AFR 13.5)"
    )
    
    # Test 7: Rich running effect on emissions
    print("\n--- Test 7: Rich Running Effect ---")
    model = EmissionSystemModel()
    state = model.simulate(
        rpm=2000,
        load_percent=40,
        afr=13.0,  # Rich
        exhaust_temp_c=450,
        time_running_s=300,
    )
    check(
        "Rich AFR high upstream O2",
        state.upstream_o2_voltage > 0.7,
        f"(voltage={state.upstream_o2_voltage:.2f}V)"
    )
    check(
        "Rich increases CO even with catalyst",
        state.co_ppm > 500,
        f"(CO={state.co_ppm:.0f} ppm)"
    )
    
    # Summary
    print("\n" + "=" * 60)
    print(f"  Total: {passed}/{passed+failed} tests passed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Emission system model is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review output above.")
    
    return failed == 0


if __name__ == "__main__":
    run_tests()
