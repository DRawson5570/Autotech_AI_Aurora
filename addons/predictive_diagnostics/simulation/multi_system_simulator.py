"""
Multi-system simulators for training data generation.

Adapts the physics models to the SystemSimulator interface
so they can be used for generating ML training data.
"""

from typing import Dict, List, Optional, Any
import random
import math

from .engine import SystemSimulator, SimulationConfig, OperatingCondition


def get_operating_params(condition: OperatingCondition) -> Dict[str, Any]:
    """Get engine parameters for an operating condition."""
    return {
        OperatingCondition.COLD_START: {
            "rpm": 1200, "load": 0.2, "speed_mph": 0,
        },
        OperatingCondition.IDLE: {
            "rpm": 800, "load": 0.15, "speed_mph": 0,
        },
        OperatingCondition.CITY_DRIVING: {
            "rpm": 2000, "load": 0.4, "speed_mph": 35,
        },
        OperatingCondition.HIGHWAY: {
            "rpm": 3000, "load": 0.6, "speed_mph": 70,
        },
        OperatingCondition.HEAVY_LOAD: {
            "rpm": 4000, "load": 0.9, "speed_mph": 50,
        },
        OperatingCondition.HOT_AMBIENT: {
            "rpm": 2500, "load": 0.5, "speed_mph": 45,
        },
    }[condition]


class FuelSystemSimulator(SystemSimulator):
    """
    Fuel system simulator for training data.
    
    State variables:
    - fuel_pressure_kpa: Fuel rail pressure
    - stft: Short-term fuel trim (%)
    - ltft: Long-term fuel trim (%)
    - afr: Air-fuel ratio
    - injector_pw_ms: Injector pulse width
    - maf_reading: MAF sensor reading (g/s)
    """
    
    def __init__(self):
        super().__init__("fuel")
        
        self.state_variables = {
            "fuel_pressure_kpa": 380.0,
            "stft": 0.0,
            "ltft": 0.0,
            "afr": 14.7,
            "injector_pw_ms": 3.0,
            "maf_reading": 10.0,
        }
        
        # DTC thresholds
        self.dtc_thresholds = [
            ("fuel_pressure_kpa", "<", 300.0, "P0087"),  # Fuel rail pressure low
            ("fuel_pressure_kpa", ">", 500.0, "P0088"),  # Fuel rail pressure high
            ("stft", ">", 20.0, "P0171"),    # System too lean bank 1
            ("stft", "<", -20.0, "P0172"),   # System too rich bank 1
            ("ltft", ">", 25.0, "P0170"),    # Fuel trim malfunction
            ("ltft", "<", -25.0, "P0170"),   # Fuel trim malfunction
        ]
        
        # Physical parameters
        self.target_afr = 14.7
        self.pump_max_pressure = 450.0
        self.pump_min_pressure = 350.0
        
    def initialize_state(self, config: SimulationConfig) -> Dict[str, float]:
        """Initialize fuel system state."""
        state = self.state_variables.copy()
        
        # Adjust for operating condition
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Higher load = more fuel flow
        state["maf_reading"] = 5.0 + load * 30.0
        state["injector_pw_ms"] = 1.5 + load * 4.0
        
        return state
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step fuel system physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Base airflow and fuel calculation
        base_airflow = 5.0 + load * 30.0
        base_fuel = base_airflow / self.target_afr
        
        # Fuel pressure based on demand
        fuel_demand = base_fuel * rpm / 1000  # Simplified demand
        base_pressure = 380.0
        
        # Apply failures (using knowledge base IDs)
        # Make each failure produce DISTINCT, MEASURABLE signatures
        maf_error = 0.0
        injector_flow_error = 0.0
        pressure_error = 0.0
        direct_stft_override = None
        direct_ltft_override = None
        direct_afr_override = None
        
        if failure == "maf_sensor_contaminated":
            # MAF reads LOW (dirty element) -> ECU sees less air than actual
            # Result: Lean running, POSITIVE fuel trims, high AFR
            maf_error = -0.35 * severity  # 35% under-reading
            # Trims will go positive to compensate (ECU adds fuel)
            
        elif failure == "fuel_pump_weak":
            # DISTINCT: Very low fuel pressure, especially at high load
            # Result: Lean at high load, pressure drops dramatically
            pressure_error = -0.35 * severity * (1 + load * 1.5)  # Up to 50% drop
            # Trims positive but pressure is the key indicator
            
        elif failure == "fuel_injector_clogged":
            # DISTINCT: Negative trims (ECU sees too lean, tries to add fuel)
            # But injector can't flow more, so STFT stays negative
            injector_flow_error = -0.35 * severity  # 35% flow reduction
            direct_stft_override = -18 * severity  # Strong negative STFT
            direct_ltft_override = -10 * severity  # LTFT follows
            
        elif failure == "fuel_injector_leaking":
            # DISTINCT: Rich at idle/light load, normal at high load
            # Positive LTFT, low AFR
            if load < 0.4:
                injector_flow_error = 0.30 * severity  # 30% extra fuel at idle
                direct_afr_override = 12.5 - severity * 1.5  # Rich AFR (11-12.5)
            else:
                injector_flow_error = 0.1 * severity  # Less rich at load
                
        elif failure == "o2_sensor_failed":
            # DISTINCT: STFT stuck near 0 (no correction), AFR drifts
            # LTFT may be high/low from before failure
            direct_stft_override = 0.0  # No correction
            # AFR wanders randomly since no feedback
            direct_afr_override = 14.7 + random.uniform(-2, 2) * severity
            
        elif failure == "vacuum_leak":
            # DISTINCT: Lean at IDLE, normal at high load (leak insignificant)
            # High positive trims at idle
            if load < 0.3:
                maf_error = -0.30 * severity  # Unmetered air = MAF reads low
                direct_stft_override = 15 * severity  # Strong positive
            else:
                maf_error = -0.05 * severity  # Minimal effect at load
        
        # Calculate readings with errors
        maf_reading = base_airflow * (1 + maf_error)
        actual_pressure = base_pressure * (1 + pressure_error)
        actual_fuel = base_fuel * (1 + injector_flow_error)
        
        # Calculate AFR - allow direct override for certain failures
        if direct_afr_override is not None:
            actual_afr = direct_afr_override
        elif actual_fuel > 0:
            actual_afr = base_airflow / actual_fuel
        else:
            actual_afr = 20.0  # Very lean
        
        # Fuel trims - allow direct override for certain failures
        if direct_stft_override is not None:
            stft = direct_stft_override + random.uniform(-2, 2)  # Add noise
        else:
            # STFT compensates for errors
            afr_error = actual_afr / self.target_afr - 1.0
            stft_target = -afr_error * 100  # Compensate for error
            stft_target = max(-25, min(25, stft_target))
            current_stft = state["stft"]
            stft = current_stft + (stft_target - current_stft) * 0.1 * dt
        
        if direct_ltft_override is not None:
            ltft = direct_ltft_override + random.uniform(-1, 1)  # Add noise
        else:
            # LTFT adapts slowly
            current_ltft = state["ltft"]
            ltft = current_ltft + stft * 0.001 * dt
            ltft = max(-25, min(25, ltft))
        
        # Injector pulse width (ECU commanded)
        fuel_with_trim = base_fuel * (1 + (stft + ltft) / 100)
        injector_pw = 1.0 + fuel_with_trim * 5.0
        
        return {
            "fuel_pressure": actual_pressure,
            "stft": stft,
            "ltft": ltft,
            "afr": actual_afr,
            "injector_pw": injector_pw,
            "maf_reading": maf_reading,
        }


class IgnitionSystemSimulator(SystemSimulator):
    """
    Ignition system simulator for training data.
    
    State variables:
    - spark_advance_deg: Ignition timing (degrees BTDC)
    - misfire_count: Cumulative misfire counter
    - knock_sensor_mv: Knock sensor voltage (mV)
    - coil_dwell_ms: Coil charge time (ms)
    - battery_voltage: Battery voltage (V)
    - rpm_stability: RPM variation (0=stable, 1=unstable)
    - timing_variance: How much timing jumps around
    """
    
    def __init__(self):
        super().__init__("ignition")
        
        self.state_variables = {
            "spark_advance_deg": 25.0,
            "misfire_count": 0.0,
            "knock_sensor_mv": 50.0,
            "coil_dwell_ms": 3.0,
            "battery_voltage": 14.2,
            "rpm_stability": 0.0,
            "timing_variance": 0.0,
        }
        
        self.dtc_thresholds = [
            ("misfire_count", ">", 10.0, "P0300"),  # Random misfire
            ("knock_sensor_mv", ">", 200.0, "P0325"),  # Knock sensor circuit
            ("battery_voltage", "<", 12.0, "P0562"),  # Low voltage
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step ignition system physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Base timing - advances with RPM, retards with load
        base_advance = 10.0 + (rpm / 6000) * 25.0 - load * 10.0
        
        misfire_rate = 0.0
        knock_mv = 50.0 + random.uniform(-5, 5)  # Normal noise
        coil_dwell = 3.0
        battery = 14.2
        rpm_stability = 0.05  # Normal small variation
        timing_variance = 0.5  # Normal small variance
        
        # Use knowledge base failure IDs - MAXIMALLY DISTINCT signatures
        if failure == "spark_plug_fouled":
            # SIGNATURE: High misfires at IDLE, drops at load
            # RPM unstable at idle, timing normal, coil dwell normal
            idle_factor = max(0, 1.5 - load * 2)  # 1.5 at idle, 0 at high load
            misfire_rate = 0.6 * severity * idle_factor
            rpm_stability = 0.4 * severity * idle_factor  # Rough idle
            knock_mv = 50 + 20 * severity * idle_factor  # Slight knock at idle
            # Key differentiator: coil dwell NORMAL
            coil_dwell = 3.0
            timing_variance = 1.0  # Slightly more variance
            
        elif failure == "ignition_coil_failed":
            # SIGNATURE: Misfires at HIGH RPM, extended dwell time
            # Coil can't charge fast enough at high RPM
            rpm_factor = rpm / 3000  # 0.27 at idle, 1.0 at 3000, 1.33 at 4000
            misfire_rate = 0.7 * severity * rpm_factor
            coil_dwell = 3.0 + 2.0 * severity  # KEY: Extended dwell (4-5ms)
            rpm_stability = 0.25 * severity * rpm_factor  # Rough at high RPM
            knock_mv = 50  # Normal knock sensor
            timing_variance = 0.5  # Normal
            
        elif failure == "ckp_sensor_failed":
            # SIGNATURE: MASSIVE misfires, VERY LOW timing, HIGH knock
            # ECU has no idea where crankshaft is
            misfire_rate = 0.95 * severity  # Almost every event
            base_advance = 5.0 - 15 * severity  # Timing very retarded/erratic
            knock_mv = 50 + 150 * severity  # KEY: Very high knock (bad timing)
            rpm_stability = 0.8 * severity  # Very rough
            timing_variance = 10.0 * severity  # KEY: Huge timing jumps
            coil_dwell = 3.0  # Normal
            
        elif failure == "cmp_sensor_failed":
            # SIGNATURE: Moderate misfires, timing slightly retarded
            # Less severe than CKP - can still run but rough
            misfire_rate = 0.4 * severity
            base_advance -= 8 * severity  # Some timing retard
            knock_mv = 50 + 40 * severity  # Some knock
            rpm_stability = 0.3 * severity  # Moderately rough
            timing_variance = 3.0 * severity  # Some timing variance
            coil_dwell = 3.0  # Normal
        
        # Calculate misfire count (cumulative)
        misfires_this_step = misfire_rate * (rpm / 60) * dt
        new_misfire_count = state["misfire_count"] + misfires_this_step
        
        # Add timing jitter based on variance
        actual_advance = base_advance + random.uniform(-1, 1) * timing_variance
        
        return {
            "spark_advance": actual_advance,
            "misfire_count": new_misfire_count,
            "knock_sensor": knock_mv,
            "coil_dwell": coil_dwell,
            "battery_voltage": battery,
            "rpm_stability": rpm_stability,
            "timing_variance": timing_variance,
        }


class ChargingSystemSimulator(SystemSimulator):
    """
    Charging system simulator for training data.
    
    MAXIMALLY DISTINCT SIGNATURES:
    - alternator_failing: LOW alternator_output (9-12V), battery draining, LOW charge_current
    - battery_weak: NORMAL alternator output, LOW battery_soc (<50%), LOW battery_voltage at rest
    - starter_failing: Everything NORMAL while running (starter only matters at start)
      This one is tricky - mark with slightly different SOC pattern
    
    State variables:
    - battery_voltage: Battery terminal voltage
    - alternator_output_v: Alternator output voltage
    - charge_current_a: Charging current
    - battery_soc: State of charge (%)
    """
    
    def __init__(self):
        super().__init__("charging")
        
        self.state_variables = {
            "battery_voltage": 12.6,
            "alternator_output_v": 14.2,
            "charge_current_a": 20.0,
            "battery_soc": 80.0,
        }
        
        self.dtc_thresholds = [
            ("battery_voltage", "<", 12.0, "P0562"),  # Low voltage
            ("battery_voltage", ">", 16.0, "P0563"),  # High voltage
            ("alternator_output_v", "<", 13.5, "P0620"),  # Alternator performance
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step charging system physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Base alternator output - increases with RPM
        rpm_factor = min(rpm / 2000, 1.0)
        base_alt_output = 14.2 * rpm_factor
        
        # Electrical load (lights, AC, etc.)
        elec_load_a = 30 + load * 50
        
        # Default normal values
        alt_output = base_alt_output
        soc = state.get("battery_soc", 80.0)
        charge_current = 20.0
        battery_v = 12.6
        
        # MAXIMALLY DISTINCT failure signatures
        if failure == "alternator_failing":
            # KEY SIGNATURE: LOW alternator output (9-12V), causing system to run on battery
            # This is THE defining feature - alternator can't produce voltage
            alt_output = 9.0 + 3.0 * (1 - severity)  # KEY: 9-12V (should be 14+)
            # Battery drains because alternator can't keep up
            soc = max(10, 80 - severity * 40)  # Dropping SOC
            charge_current = -10 - severity * 20  # KEY: NEGATIVE (discharging!)
            battery_v = 11.0 + (1 - severity) * 1.5  # Dropping voltage
            # Intermittent drops make it worse
            if random.random() < severity * 0.2:
                alt_output = 8.0  # Severe drop
                
        elif failure == "battery_weak":
            # KEY SIGNATURE: NORMAL alternator, but battery can't hold charge
            # Alternator works fine! But SOC stays low and voltage sags
            alt_output = base_alt_output + random.uniform(-0.2, 0.2)  # KEY: NORMAL (14V+)
            soc = 15 + 25 * (1 - severity)  # KEY: LOW SOC (15-40%)
            # Battery accepts charge but can't hold it - internal resistance high
            charge_current = 10 + random.uniform(-5, 5)  # Moderate charge current
            # At rest, battery voltage is low
            battery_v = 11.5 + (1 - severity) * 0.8  # KEY: LOW resting voltage (11.5-12.3V)
            
        elif failure == "starter_failing":
            # KEY SIGNATURE: Everything NORMAL while running!
            # Starter only matters at engine start - while running, all is well
            # BUT: We encode a "cranking weakness" indicator via slightly elevated current draw
            alt_output = base_alt_output + random.uniform(-0.2, 0.2)  # NORMAL
            soc = 75 + random.uniform(-5, 5)  # KEY: NORMAL SOC (70-80%)
            charge_current = 15 + random.uniform(-3, 3)  # NORMAL-ish
            battery_v = 12.5 + random.uniform(-0.2, 0.2)  # KEY: NORMAL voltage (12.3-12.7V)
            # The only hint: battery takes longer to recover after cranking
            # Encoded as slightly lower SOC trend
            soc = max(65, soc - severity * 8)  # Slightly lower (65-75%)
        else:
            # Normal operation
            if alt_output > 12.6:
                charge_current = (alt_output - 12.6) * 10
            else:
                charge_current = -elec_load_a
            soc_change = charge_current * dt / 360
            soc = max(0, min(100, soc + soc_change))
            battery_v = 11.5 + (soc / 100) * 1.1
            if charge_current > 0:
                battery_v = alt_output - 0.2
        
        return {
            "battery_voltage": max(8, min(battery_v, 16)),
            "alternator_output_v": max(0, min(alt_output, 16)),
            "charge_current": max(-50, min(charge_current, 50)),
            "battery_soc": max(0, min(soc, 100)),
        }


class TransmissionSystemSimulator(SystemSimulator):
    """
    Transmission system simulator for training data.
    
    State variables:
    - trans_temp: Transmission fluid temperature
    - line_pressure: Transmission line pressure
    - slip_percent: Torque converter slip
    - shift_time: Shift duration
    - current_gear: Current gear
    """
    
    def __init__(self):
        super().__init__("transmission")
        
        self.state_variables = {
            "trans_temp": 80.0,
            "line_pressure": 150.0,
            "slip_percent": 5.0,
            "shift_time": 200.0,
            "current_gear": 3.0,
        }
        
        self.dtc_thresholds = [
            ("trans_temp", ">", 130.0, "P0218"),  # Trans temp high
            ("slip_percent", ">", 15.0, "P0740"),  # TCC circuit
            ("line_pressure", "<", 100.0, "P0868"),  # Trans pressure low
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step transmission physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        speed = op["speed_mph"]
        
        # Gear selection based on speed
        if speed < 15:
            target_gear = 1
        elif speed < 30:
            target_gear = 2
        elif speed < 45:
            target_gear = 3
        elif speed < 60:
            target_gear = 4
        else:
            target_gear = 5
        
        # Trans temp increases with load
        ambient = config.ambient_temp_c
        heat_gen = 100 + load * 300  # Watts
        cooling = (state["trans_temp"] - ambient) * 5  # Simple cooling
        temp_change = (heat_gen - cooling) / 5000 * dt  # Simplified thermal mass
        trans_temp = state["trans_temp"] + temp_change
        
        # Base values
        line_pressure = 150.0
        slip = 5.0
        shift_time = 200.0
        
        # Use knowledge base failure IDs
        if failure == "shift_solenoid_failed":
            # Harsh or delayed shifts
            shift_time = 400 + severity * 300
            slip = 8 + severity * 8
        elif failure == "torque_converter_shudder":
            # High slip, shudder vibration
            slip = 10 + severity * 15
        elif failure == "trans_fluid_low":
            # Low pressure, high temp, slip
            line_pressure = 120 - severity * 40
            trans_temp += severity * 25
            slip = 8 + severity * 10
        
        return {
            "trans_temp": trans_temp,
            "line_pressure": line_pressure,
            "slip_percent": slip,
            "shift_time": shift_time,
            "current_gear": float(target_gear),
        }


class BrakingSystemSimulator(SystemSimulator):
    """
    Braking system simulator for training data.
    
    State variables:
    - brake_pressure_psi: Brake line pressure when braking
    - rotor_temp: Brake rotor temperature
    - pad_thickness_mm: Brake pad thickness
    - abs_active: ABS activation level (0-1)
    - pedal_travel_mm: Brake pedal travel distance
    - pedal_feel: Pedal firmness (0=spongy, 1=firm)
    - stopping_distance_factor: Relative stopping distance (1=normal)
    """
    
    def __init__(self):
        super().__init__("brakes")
        
        self.state_variables = {
            "brake_pressure_psi": 0.0,
            "rotor_temp": 50.0,
            "pad_thickness_mm": 10.0,
            "abs_active": 0.0,
            "pedal_travel_mm": 5.0,
            "pedal_feel": 1.0,
            "stopping_distance_factor": 1.0,
        }
        
        self.dtc_thresholds = [
            ("brake_pressure_psi", "<", 100.0, "C0035"),  # Pressure low
            ("pad_thickness_mm", "<", 3.0, "B1015"),  # Pad wear
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step braking system physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        speed = op["speed_mph"]
        
        # Simulate occasional braking
        braking = random.random() < 0.15  # 15% chance each step
        brake_force = 0.5 if braking else 0.0
        
        # Base values for normal operation
        base_pressure = 1500 * brake_force if braking else 0.0
        
        # Rotor temperature - track cumulative heat
        ambient = config.ambient_temp_c
        if braking:
            heat_gen = speed * brake_force * 100
        else:
            heat_gen = 0
        cooling = (state["rotor_temp"] - ambient) * 2
        temp_change = (heat_gen - cooling) / 500 * dt
        rotor_temp = state["rotor_temp"] + temp_change
        
        # Default normal values
        pressure = base_pressure
        pedal_travel = 5.0 if not braking else 30.0
        abs_active = 0.0
        pad_thickness = state.get("pad_thickness_mm", 10.0)
        pedal_feel = 1.0  # Firm
        stopping_distance = 1.0  # Normal
        
        # Use knowledge base failure IDs - MAXIMALLY DISTINCT signatures
        if failure == "master_cylinder_failing":
            # KEY SIGNATURE: Spongy pedal, low pressure, long travel
            # Pedal goes to floor, internal leak
            pressure *= (1 - 0.6 * severity)
            pedal_travel = 40 + severity * 50  # KEY: Very long travel (40-90mm)
            pedal_feel = 1.0 - 0.8 * severity  # KEY: Very spongy (0.2)
            stopping_distance = 1.0 + 0.5 * severity  # Longer stops
            rotor_temp = state["rotor_temp"]  # Normal temp
            pad_thickness = 10.0  # Normal pads
            
        elif failure == "brake_caliper_sticking":
            # KEY SIGNATURE: Very high rotor temp, residual pressure when not braking
            # Brakes drag constantly
            rotor_temp = state["rotor_temp"] + severity * 8 * dt  # KEY: Heat buildup
            rotor_temp = min(rotor_temp, 350)  # Can get very hot (up to 350C)
            if not braking:
                pressure = 300 * severity  # KEY: Residual pressure (up to 300 psi)
            pedal_feel = 1.0  # Pedal feels normal
            pedal_travel = 25 if not braking else 30  # Normal travel
            stopping_distance = 0.9  # Actually stops quicker (dragging)
            pad_thickness = 10.0 - severity * 1.5  # Slightly accelerated wear
            
        elif failure == "brake_pads_worn":
            # KEY SIGNATURE: Very thin pads, longer travel, metal-on-metal
            pad_thickness = 10 - severity * 9  # KEY: Down to 1mm
            pad_thickness = max(pad_thickness, 0.5)
            pedal_travel = 15 + severity * 30  # KEY: More travel (15-45mm)
            stopping_distance = 1.0 + 0.3 * severity  # Longer stops
            rotor_temp = state["rotor_temp"]  # Normal temp
            pedal_feel = 0.9  # Slightly less firm
            if not braking:
                pressure = 0  # No residual
            
        elif failure == "brake_rotor_warped":
            # KEY SIGNATURE: ABS pulsing, pedal pulsation
            if braking:
                abs_active = 0.7 * severity  # KEY: ABS activates (pulsing)
                pressure *= (1 + random.uniform(-0.3, 0.3) * severity)  # Pressure varies
                pedal_feel = 1.0 - 0.3 * severity  # Pulsating feel
            pedal_travel = 30 if braking else 5  # Normal travel
            rotor_temp = state["rotor_temp"]  # Normal temp
            pad_thickness = 10.0  # Normal pads
            stopping_distance = 1.1  # Slightly longer
                
        elif failure == "abs_sensor_failed":
            # KEY SIGNATURE: ABS light on, ABS NEVER activates
            abs_active = 0.0  # KEY: Always 0 (even when it should activate)
            # Simulate that ABS would have activated in hard braking
            if braking and speed > 30:
                # Normal ABS would activate, but can't
                stopping_distance = 1.0 + 0.4 * severity  # KEY: Longer stops at speed
            pedal_travel = 30 if braking else 5  # Normal travel
            pedal_feel = 1.0  # Normal feel
            rotor_temp = state["rotor_temp"]  # Normal temp
            pad_thickness = 10.0  # Normal pads
        
        return {
            "brake_pressure": max(0, min(pressure, 3000)),      # Clamp
            "rotor_temp": max(20, min(rotor_temp, 400)),        # Clamp  
            "pad_thickness": max(0.5, min(pad_thickness, 12)),  # Clamp
            "abs_active": max(0, min(abs_active, 1)),           # Clamp
            "pedal_travel": max(5, min(pedal_travel, 100)),     # Clamp
            "pedal_feel": max(0, min(pedal_feel, 1)),           # Clamp
            "stopping_distance": max(0.5, min(stopping_distance, 2)),  # Clamp
        }


class EngineSystemSimulator(SystemSimulator):
    """
    Engine mechanical system simulator.
    
    Models internal engine issues:
    - Low compression (worn rings, valves)
    - Head gasket failure
    - Timing chain issues
    - Oil pump failure
    - PCV system problems
    
    State variables (matched to SYSTEM_SENSORS in train_hierarchical.py):
    - oil_pressure: Oil pressure in psi
    - manifold_vacuum: Manifold vacuum in inHg
    - compression_variation: Variation between cylinders (%)
    - blow_by_pressure: Crankcase pressure (inH2O)
    - timing_deviation: Timing deviation from commanded (degrees)
    - power_balance: Power balance between cylinders (%)
    """
    
    def __init__(self):
        super().__init__("engine")
        
        self.state_variables = {
            "oil_pressure": 45.0,           # psi - normal is 25-65 psi
            "manifold_vacuum": 20.0,        # inHg - normal is 17-22 at idle
            "compression_variation": 5.0,   # % - normal is <10%
            "blow_by_pressure": 0.5,        # inH2O - normal is <1
            "timing_deviation": 0.0,        # degrees from commanded
            "power_balance": 100.0,         # % - 100 = all cylinders equal
        }
        
        # DTC thresholds
        self.dtc_thresholds = [
            ("oil_pressure", "<", 15.0, "P0520"),        # Low oil pressure
            ("manifold_vacuum", "<", 12.0, "P0300"),     # Rough idle/misfire
            ("compression_variation", ">", 20.0, "P030X"),  # Misfire
        ]
    
    def initialize_state(self, config: SimulationConfig) -> Dict[str, float]:
        """Initialize engine state."""
        state = self.state_variables.copy()
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Oil pressure increases with RPM
        state["oil_pressure"] = 25 + (rpm / 100)
        
        # Manifold vacuum decreases with load
        state["manifold_vacuum"] = 22 - (load * 15)
        
        return state
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step engine physics with failure-specific signatures."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Calculate base values
        base_oil_pressure = 25 + (rpm / 100)  # 25-65 psi
        base_vacuum = 22 - (load * 15)        # 7-22 inHg
        
        # Default normal values
        oil_pressure = base_oil_pressure
        manifold_vacuum = base_vacuum
        compression_variation = 5.0 + random.uniform(-2, 2)
        blow_by_pressure = 0.5 + random.uniform(-0.2, 0.2)
        timing_deviation = random.uniform(-1, 1)
        power_balance = 100.0
        
        # =========================================================
        # FAILURE SIGNATURES - Each must be MAXIMALLY DISTINCT
        # =========================================================
        
        if failure == "low_compression":
            # KEY: High compression variation, low vacuum, poor power balance
            # One or more cylinders have worn rings/valves
            compression_variation = 15 + severity * 25  # KEY: 15-40% variation
            manifold_vacuum = base_vacuum - severity * 8  # Lower vacuum (more leak)
            power_balance = 100 - severity * 30  # KEY: Uneven power (70-100)
            blow_by_pressure = 0.5 + severity * 3  # Increased blow-by
            # Oil pressure normal, timing normal
            
        elif failure == "head_gasket_failure":
            # KEY: Very high blow-by, compression loss, coolant intrusion
            # Combustion gases leak into cooling system
            blow_by_pressure = 0.5 + severity * 6  # KEY: Very high (up to 6.5 inH2O)
            compression_variation = 10 + severity * 20  # Elevated variation
            manifold_vacuum = base_vacuum - severity * 5  # Reduced vacuum
            power_balance = 95 - severity * 15  # Slightly uneven
            # May have steam/white smoke (not modeled here)
            
        elif failure == "timing_chain_stretched":
            # KEY: Large timing deviation, rough idle, rattling
            # Chain slack causes variable valve timing
            timing_deviation = 5 + severity * 15  # KEY: 5-20° deviation
            power_balance = 90 - severity * 20  # KEY: Poor balance (70-90)
            manifold_vacuum = base_vacuum - severity * 4  # Lower vacuum
            # Compression normal, blow-by normal
            
        elif failure == "oil_pump_failure":
            # KEY: Very low oil pressure, normal everything else
            # Pump can't maintain pressure
            oil_pressure = base_oil_pressure * (1 - 0.7 * severity)  # KEY: Low (8-45 psi)
            oil_pressure = max(oil_pressure, 5)  # Minimum from residual
            # Everything else normal - this is purely an oil pressure issue
            # Engine may knock under load if oil starvation severe
            
        elif failure == "pcv_valve_stuck":
            # KEY: Abnormal crankcase pressure, oil consumption
            # PCV stuck closed = high crankcase pressure
            # PCV stuck open = vacuum leak
            if random.random() < 0.5:
                # Stuck closed - high crankcase pressure
                blow_by_pressure = 2 + severity * 4  # KEY: Elevated (2-6 inH2O)
            else:
                # Stuck open - vacuum leak
                manifold_vacuum = base_vacuum - severity * 6  # KEY: Low vacuum
                blow_by_pressure = -0.5 * severity  # Negative (vacuum in crankcase)
            # Compression normal, timing normal, power balance normal
        
        return {
            "oil_pressure": max(5, min(oil_pressure, 80)),
            "manifold_vacuum": max(5, min(manifold_vacuum, 25)),
            "compression_variation": max(0, min(compression_variation, 50)),
            "blow_by_pressure": max(-2, min(blow_by_pressure, 10)),
            "timing_deviation": max(-25, min(timing_deviation, 25)),
            "power_balance": max(50, min(power_balance, 100)),
        }


class SteeringSystemSimulator(SystemSimulator):
    """
    Power steering system simulator.
    
    Models:
    - Power steering pump failures
    - Rack and pinion issues  
    - Steering angle sensor problems
    - Electronic power steering (EPS) faults
    
    State variables:
    - steering_assist: Power assist level (0-100%)
    - ps_pressure: Power steering pressure (psi)
    - steering_effort: Required steering effort (normalized 0-1)
    - steering_play: Free play in steering (degrees)
    - steering_noise: Noise level (0-1)
    - steering_response: How quickly steering responds (0-1, 1=instant)
    """
    
    def __init__(self):
        super().__init__("steering")
        
        self.state_variables = {
            "steering_assist": 100.0,       # % - normal is 100%
            "ps_pressure": 1200.0,          # psi - normal is 1000-1500
            "steering_effort": 0.2,         # normalized - lower is easier
            "steering_play": 1.0,           # degrees - normal is <3
            "steering_noise": 0.0,          # 0-1 - normal is 0
            "steering_response": 1.0,       # 0-1 - normal is 1.0
        }
        
        self.dtc_thresholds = [
            ("ps_pressure", "<", 800.0, "P0550"),     # PS pressure circuit
            ("steering_assist", "<", 50.0, "C0545"),  # Steering assist fault
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step steering system physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        speed = op["speed_mph"]
        
        # Base values - assist decreases with speed (normal behavior)
        speed_factor = max(0.3, 1 - speed / 100)  # Less assist at high speed
        base_assist = 100.0 * speed_factor
        base_pressure = 1200.0
        base_effort = 0.2 + (1 - speed_factor) * 0.3  # More effort at high speed
        
        # Default normal values
        steering_assist = base_assist
        ps_pressure = base_pressure
        steering_effort = base_effort
        steering_play = 1.0 + random.uniform(-0.3, 0.3)
        steering_noise = 0.0
        steering_response = 1.0
        
        if failure == "ps_pump_failing":
            # KEY: Low pressure, high effort, whining noise
            ps_pressure = base_pressure * (1 - 0.5 * severity)  # 600-1200 psi
            steering_assist = base_assist * (1 - 0.6 * severity)  # 40-100%
            steering_effort = 0.3 + 0.5 * severity  # KEY: High effort (0.3-0.8)
            steering_noise = 0.3 + 0.5 * severity  # KEY: Whining noise (0.3-0.8)
            steering_play = 1.0  # Normal play
            
        elif failure == "rack_wear":
            # KEY: Excessive play, delayed response
            steering_play = 3 + severity * 8  # KEY: 3-11 degrees (spec is <3)
            steering_response = 1 - 0.4 * severity  # KEY: Delayed (0.6-1.0)
            steering_effort = base_effort + 0.2 * severity  # Slightly more effort
            ps_pressure = base_pressure  # Normal pressure
            steering_noise = 0.1 * severity  # Slight clunk
            
        elif failure == "steering_angle_sensor_failed":
            # KEY: Stability control errors, erratic response
            steering_response = 0.5 - 0.3 * severity  # KEY: Very poor (0.2-0.5)
            # Assist may be reduced (safety mode)
            steering_assist = base_assist * (1 - 0.4 * severity)
            steering_effort = base_effort + 0.3 * severity
            steering_play = 1.0  # Normal play
            ps_pressure = base_pressure  # Normal pressure
            
        elif failure == "eps_motor_failing":
            # KEY: Intermittent assist, motor noise
            # EPS = Electronic Power Steering
            if random.random() < severity * 0.3:  # Intermittent
                steering_assist = 0  # Complete assist loss (intermittent)
                steering_effort = 0.9  # Very hard to steer
            else:
                steering_assist = base_assist * (1 - 0.3 * severity)
                steering_effort = base_effort + 0.2 * severity
            steering_noise = 0.4 + 0.4 * severity  # KEY: Motor whine
            steering_response = 1 - 0.2 * severity
            ps_pressure = 0  # EPS has no hydraulic pressure
            steering_play = 1.0  # Normal
            
        elif failure == "tie_rod_worn":
            # KEY: Clunking, excessive play, wander
            steering_play = 4 + severity * 6  # KEY: 4-10 degrees
            steering_noise = 0.3 + 0.4 * severity  # KEY: Clunk over bumps
            steering_response = 1 - 0.3 * severity  # Vague center feel
            steering_effort = base_effort  # Normal effort
            ps_pressure = base_pressure  # Normal pressure
        
        return {
            "steering_assist": max(0, min(steering_assist, 100)),
            "ps_pressure": max(0, min(ps_pressure, 2000)),
            "steering_effort": max(0, min(steering_effort, 1)),
            "steering_play": max(0, min(steering_play, 15)),
            "steering_noise": max(0, min(steering_noise, 1)),
            "steering_response": max(0, min(steering_response, 1)),
        }


class SuspensionSystemSimulator(SystemSimulator):
    """
    Suspension system simulator.
    
    Models:
    - Shock/strut wear
    - Spring failures
    - Control arm/bushing wear
    - Wheel bearing issues
    - Alignment problems
    
    State variables:
    - ride_height: Vehicle ride height deviation (inches from spec)
    - damping_coefficient: Shock damping effectiveness (0-1)
    - body_roll: Cornering body roll (degrees)
    - bounce_count: Oscillations after bump (lower is better)
    - suspension_noise: Clunks, squeaks (0-1)
    - wheel_bearing_temp: Wheel bearing temperature (°C)
    """
    
    def __init__(self):
        super().__init__("suspension")
        
        self.state_variables = {
            "ride_height": 0.0,            # inches deviation - normal is 0
            "damping_coefficient": 1.0,    # 0-1 - normal is 1.0
            "body_roll": 2.0,              # degrees - normal is 2-4
            "bounce_count": 1.0,           # oscillations - normal is 1-2
            "suspension_noise": 0.0,       # 0-1 - normal is 0
            "wheel_bearing_temp": 40.0,    # °C - normal is ambient+20
        }
        
        self.dtc_thresholds = [
            ("ride_height", ">", 2.0, "C1760"),    # Ride height sensor
            ("ride_height", "<", -2.0, "C1760"),
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step suspension physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        speed = op["speed_mph"]
        load = op["load"]
        ambient = config.ambient_temp_c
        
        # Base values
        base_ride_height = 0.0
        base_damping = 1.0
        base_roll = 2.0 + load * 2  # More roll under load
        base_bounce = 1.0
        
        # Default normal values
        ride_height = base_ride_height + random.uniform(-0.1, 0.1)
        damping_coefficient = base_damping
        body_roll = base_roll + random.uniform(-0.5, 0.5)
        bounce_count = base_bounce
        suspension_noise = 0.0
        # Wheel bearing heats with speed
        wheel_bearing_temp = ambient + 20 + speed * 0.3
        
        if failure == "shock_worn":
            # KEY: Poor damping, excessive bounce, nose dive
            damping_coefficient = 1 - 0.7 * severity  # KEY: 0.3-1.0
            bounce_count = 1 + severity * 4  # KEY: 1-5 oscillations
            body_roll = base_roll + severity * 4  # More body roll
            ride_height = -0.5 * severity  # Slight sag
            suspension_noise = 0.1 * severity  # Minor noise
            
        elif failure == "spring_broken":
            # KEY: Severe ride height drop on one corner
            ride_height = -2 - severity * 3  # KEY: -2 to -5 inches
            body_roll = base_roll + severity * 6  # KEY: Severe lean
            suspension_noise = 0.5 + 0.3 * severity  # Clunking
            damping_coefficient = 0.8  # Shock may bottom
            bounce_count = 2 + severity * 2
            
        elif failure == "control_arm_bushing_worn":
            # KEY: Clunking, vague steering, alignment drift
            suspension_noise = 0.4 + 0.4 * severity  # KEY: Clunk over bumps
            damping_coefficient = 1 - 0.2 * severity  # Slightly less controlled
            body_roll = base_roll + severity * 2
            # Alignment wanders causing tire wear
            
        elif failure == "wheel_bearing_failing":
            # KEY: High bearing temp, growling noise at speed
            wheel_bearing_temp = ambient + 40 + severity * 60  # KEY: 60-120°C above ambient
            suspension_noise = 0.3 + 0.5 * severity  # KEY: Growl/hum at speed
            # Speed-dependent - louder at higher speed
            if speed > 40:
                suspension_noise += 0.2
            damping_coefficient = base_damping  # Normal
            ride_height = base_ride_height  # Normal
            
        elif failure == "strut_mount_worn":
            # KEY: Clunk over bumps, noise when turning
            suspension_noise = 0.5 + 0.4 * severity  # KEY: Clunk/creak
            damping_coefficient = 1 - 0.3 * severity
            ride_height = -0.3 * severity  # Slight sag
            body_roll = base_roll + severity * 2
            bounce_count = 1 + severity * 2
        
        return {
            "ride_height": max(-6, min(ride_height, 3)),
            "damping_coefficient": max(0, min(damping_coefficient, 1)),
            "body_roll": max(0, min(body_roll, 15)),
            "bounce_count": max(1, min(bounce_count, 8)),
            "suspension_noise": max(0, min(suspension_noise, 1)),
            "wheel_bearing_temp": max(ambient, min(wheel_bearing_temp, 200)),
        }


class HVACSystemSimulator(SystemSimulator):
    """
    HVAC (Heating, Ventilation, Air Conditioning) system simulator.
    
    Models:
    - A/C compressor issues - HIGH low-side pressure, low high-side (can't compress)
    - Refrigerant leaks - BOTH pressures low (system depleted)
    - Blend door problems - NORMAL pressures, wrong vent temp for mode
    - Blower motor failures - Low blower speed, normal everything else
    - Heater core issues - NORMAL pressures, cold air in HEAT mode only
    
    MAXIMALLY DISTINCT SIGNATURES:
    - compressor_failing: Low-side HIGH (40-70), High-side LOW (100-150), warm vent
    - refrigerant_leak: BOTH pressures LOW (<50), warm vent
    - blend_door_stuck: Pressures NORMAL, vent temp WRONG for mode
    - blower_motor_failing: ONLY blower_speed affected, everything else NORMAL
    - heater_core_clogged: A/C works fine, ONLY fails in heat mode
    
    State variables:
    - vent_temp: Air temperature at vents (°C)
    - refrigerant_pressure_high: High side pressure (psi)
    - refrigerant_pressure_low: Low side pressure (psi)
    - compressor_clutch: Clutch engaged (0/1)
    - blower_speed: Blower motor speed (0-100%)
    - cabin_temp: Cabin temperature (°C)
    """
    
    def __init__(self):
        super().__init__("hvac")
        
        self.state_variables = {
            "vent_temp": 20.0,                  # °C at vents
            "refrigerant_pressure_high": 200.0, # psi - normal 150-250
            "refrigerant_pressure_low": 35.0,   # psi - normal 25-45
            "compressor_clutch": 1.0,           # 0 or 1
            "blower_speed": 75.0,               # 0-100%
            "cabin_temp": 22.0,                 # °C
        }
        
        self.dtc_thresholds = [
            ("refrigerant_pressure_low", "<", 15.0, "B1421"),   # Low refrigerant
            ("refrigerant_pressure_high", ">", 350.0, "B1422"), # High pressure
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step HVAC physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        ambient = config.ambient_temp_c
        
        # Simulate A/C mode (hot ambient = A/C on)
        ac_mode = ambient > 25
        heat_mode = ambient < 15
        
        # Base values for A/C mode
        if ac_mode:
            base_vent_temp = 8.0  # Cold air
            base_high_pressure = 200 + (ambient - 25) * 5  # Pressure rises with heat
            base_low_pressure = 35.0
            base_clutch = 1.0
        elif heat_mode:
            base_vent_temp = 50.0  # Hot air from heater
            base_high_pressure = 0  # A/C off
            base_low_pressure = 0
            base_clutch = 0.0
        else:
            base_vent_temp = ambient
            base_high_pressure = 0
            base_low_pressure = 0
            base_clutch = 0.0
        
        # Default values
        vent_temp = base_vent_temp + random.uniform(-1, 1)
        refrigerant_pressure_high = base_high_pressure
        refrigerant_pressure_low = base_low_pressure
        compressor_clutch = base_clutch
        blower_speed = 75.0
        cabin_temp = ambient + random.uniform(-2, 2)
        
        if failure == "ac_compressor_failing":
            # KEY SIGNATURE: HIGH low-side (50-70), LOW high-side (100-150), can't compress
            # Compressor can't build pressure differential - ALWAYS SHOWS
            # In any mode, we can see the abnormal pressure pattern
            refrigerant_pressure_high = 100 + 50 * (1 - severity)  # LOW: 100-150 psi
            refrigerant_pressure_low = 50 + severity * 20  # HIGH: 50-70 psi
            vent_temp = 15 + severity * 10 + random.uniform(-2, 2)  # Warm: 15-27°C
            compressor_clutch = 1.0 if random.random() > severity * 0.3 else 0.0
            cabin_temp = ambient + random.uniform(-2, 2)
            blower_speed = 75.0  # NORMAL
                
        elif failure == "refrigerant_leak":
            # KEY SIGNATURE: BOTH pressures VERY LOW (<20), system depleted
            # This shows in ANY mode - system has no refrigerant
            refrigerant_pressure_high = max(5, 20 * (1 - severity))  # VERY LOW: 0-20 psi
            refrigerant_pressure_low = max(2, 7 * (1 - severity))    # VERY LOW: 0-7 psi
            compressor_clutch = 0.0 if severity > 0.4 else base_clutch  # Low pressure cutoff
            vent_temp = ambient + random.uniform(-3, 3)  # Nearly ambient (no cooling)
            cabin_temp = ambient + random.uniform(-2, 2)
            blower_speed = 75.0  # NORMAL
                
        elif failure == "blend_door_stuck":
            # KEY SIGNATURE: NORMAL pressures, but vent temp EXTREMELY WRONG
            # Pressures are perfect (A/C system fine), but temp is way off
            refrigerant_pressure_high = base_high_pressure + random.uniform(-5, 5)  # NORMAL!
            refrigerant_pressure_low = base_low_pressure + random.uniform(-2, 2)    # NORMAL!
            compressor_clutch = base_clutch  # NORMAL!
            blower_speed = 75.0  # NORMAL!
            # KEY: Vent temp is EXTREMELY wrong - 50-65°C hot OR 0-10°C cold
            stuck_hot = random.random() < 0.5
            if stuck_hot:
                vent_temp = 50 + severity * 15  # KEY: Very hot (50-65°C)
            else:
                vent_temp = 10 - severity * 10  # KEY: Very cold (0-10°C)
            cabin_temp = ambient  # Can't regulate
            
        elif failure == "blower_motor_failing":
            # KEY SIGNATURE: ONLY blower_speed is LOW (0-30%), EVERYTHING else PERFECT
            refrigerant_pressure_high = base_high_pressure + random.uniform(-5, 5)  # NORMAL!
            refrigerant_pressure_low = base_low_pressure + random.uniform(-2, 2)    # NORMAL!
            compressor_clutch = base_clutch  # NORMAL!
            vent_temp = base_vent_temp + random.uniform(-1, 1)  # NORMAL!
            # ONLY blower speed is affected - KEY DISTINGUISHER
            blower_speed = max(0, 30 * (1 - severity) + random.uniform(-5, 5))  # KEY: 0-30%
            cabin_temp = ambient  # Cabin doesn't change (no airflow)
            
        elif failure == "heater_core_clogged":
            # KEY SIGNATURE: NORMAL pressures, NORMAL blower, but SPECIFICALLY LUKEWARM vent (30-42°C)
            # Distinct from ac_compressor_failing (15-27°C) and blend_door_stuck (0-10 or 50-65)
            refrigerant_pressure_high = base_high_pressure + random.uniform(-5, 5)  # NORMAL!
            refrigerant_pressure_low = base_low_pressure + random.uniform(-2, 2)    # NORMAL!
            compressor_clutch = base_clutch  # NORMAL
            blower_speed = 75.0  # NORMAL!
            # KEY: Vent temp is LUKEWARM (30-42°C) - heater can't get hot enough
            vent_temp = 30 + 12 * (1 - severity) + random.uniform(-2, 2)  # 30-42°C
            cabin_temp = ambient + random.uniform(-2, 2)
            
        return {
            "vent_temp": max(-10, min(vent_temp, 80)),
            "refrigerant_pressure_high": max(0, min(refrigerant_pressure_high, 500)),
            "refrigerant_pressure_low": max(0, min(refrigerant_pressure_low, 100)),
            "compressor_clutch": 1.0 if compressor_clutch > 0.5 else 0.0,
            "blower_speed": max(0, min(blower_speed, 100)),
            "cabin_temp": max(-20, min(cabin_temp, 60)),
        }


class EmissionsSystemSimulator(SystemSimulator):
    """
    Emissions control system simulator.
    
    Models:
    - Catalytic converter issues
    - O2 sensor failures
    - EGR system problems
    - EVAP system leaks
    - PCV valve issues
    
    State variables:
    - catalyst_efficiency: Cat converter efficiency (%)
    - o2_upstream_mv: Pre-cat O2 sensor voltage (mV)
    - o2_downstream_mv: Post-cat O2 sensor voltage (mV)
    - egr_flow: EGR valve flow (%)
    - evap_pressure: EVAP system pressure (inH2O)
    - nox_level: NOx emissions level (ppm)
    """
    
    def __init__(self):
        super().__init__("emissions")
        
        self.state_variables = {
            "catalyst_efficiency": 95.0,     # % - normal >85%
            "o2_upstream_mv": 450.0,         # mV - oscillates 100-900
            "o2_downstream_mv": 600.0,       # mV - steady ~600 (good cat)
            "egr_flow": 15.0,                # % - varies with load
            "evap_pressure": 0.5,            # inH2O - near 0 is sealed
            "nox_level": 50.0,               # ppm - normal <100
        }
        
        self.dtc_thresholds = [
            ("catalyst_efficiency", "<", 80.0, "P0420"),   # Cat below threshold
            ("evap_pressure", ">", 2.0, "P0455"),          # EVAP gross leak
            ("egr_flow", "<", 5.0, "P0401"),               # Insufficient EGR
        ]
    
    def step(self, state: Dict[str, float], dt: float, config: SimulationConfig) -> Dict[str, float]:
        """Step emissions system physics."""
        failure = config.failure_id
        severity = config.failure_severity
        
        op = get_operating_params(config.operating_condition)
        rpm = op["rpm"]
        load = op["load"]
        
        # Normal O2 sensor behavior - upstream oscillates, downstream steady
        # Upstream: rich/lean cycling 100-900mV
        o2_cycle = math.sin(state.get("_o2_phase", 0) + dt * 3) * 400 + 500
        
        # Base values
        base_cat_efficiency = 95.0
        base_egr = 5 + load * 20  # More EGR at load
        base_nox = 30 + load * 40  # More NOx at load
        
        # Default values
        catalyst_efficiency = base_cat_efficiency
        o2_upstream_mv = o2_cycle + random.uniform(-30, 30)
        o2_downstream_mv = 600 + random.uniform(-50, 50)  # Steady if cat good
        egr_flow = base_egr + random.uniform(-2, 2)
        evap_pressure = 0.5 + random.uniform(-0.2, 0.2)
        nox_level = base_nox + random.uniform(-10, 10)
        
        if failure == "catalytic_converter_degraded":
            # KEY: Low efficiency, downstream O2 mirrors upstream
            catalyst_efficiency = 95 - severity * 50  # KEY: 45-95%
            # Downstream starts oscillating like upstream (cat not working)
            o2_downstream_mv = o2_cycle * (0.3 + 0.6 * severity)  # KEY: Oscillating
            nox_level = base_nox + severity * 200  # Higher emissions
            
        elif failure == "o2_sensor_upstream_failed":
            # KEY: Stuck or slow O2 sensor, trims affected
            if random.random() < 0.5:
                o2_upstream_mv = 450  # KEY: Stuck at mid-point
            else:
                o2_upstream_mv = 100 if random.random() < 0.5 else 900  # KEY: Stuck lean/rich
            # Cat efficiency appears low because O2 doesn't switch
            catalyst_efficiency = base_cat_efficiency  # Actually fine
            
        elif failure == "o2_sensor_downstream_failed":
            # KEY: Downstream stuck, but trims OK (uses upstream)
            if random.random() < 0.5:
                o2_downstream_mv = 100  # KEY: Stuck lean
            else:
                o2_downstream_mv = 900  # KEY: Stuck rich
            catalyst_efficiency = base_cat_efficiency  # Actually fine
            
        elif failure == "egr_valve_stuck_closed":
            # KEY: No EGR flow, high NOx, detonation at load
            egr_flow = severity * 3  # KEY: Very low (0-3%)
            nox_level = base_nox + severity * 300  # KEY: High NOx
            # May cause knock
            
        elif failure == "egr_valve_stuck_open":
            # KEY: Excessive EGR, rough idle, surging
            egr_flow = 30 + severity * 20  # KEY: Very high (30-50%)
            nox_level = base_nox * (1 - 0.5 * severity)  # Low NOx (too much EGR)
            # Causes rough idle, misfire at idle
            
        elif failure == "evap_leak_large":
            # KEY: High EVAP pressure (no vacuum)
            evap_pressure = 2 + severity * 3  # KEY: High (2-5 inH2O)
            # Fuel smell possible
            
        elif failure == "evap_purge_valve_stuck":
            # KEY: EVAP pressure either too high or vacuum
            if random.random() < 0.5:
                # Stuck closed - no purge
                evap_pressure = 1.5 + severity * 2  # Elevated
            else:
                # Stuck open - vacuum leak
                evap_pressure = -1 - severity * 2  # Negative (vacuum)
        
        return {
            "catalyst_efficiency": max(0, min(catalyst_efficiency, 100)),
            "o2_upstream_mv": max(0, min(o2_upstream_mv, 1000)),
            "o2_downstream_mv": max(0, min(o2_downstream_mv, 1000)),
            "egr_flow": max(0, min(egr_flow, 60)),
            "evap_pressure": max(-5, min(evap_pressure, 10)),
            "nox_level": max(0, min(nox_level, 1000)),
        }
