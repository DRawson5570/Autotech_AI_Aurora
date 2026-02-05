"""
Transmission System Physics Model

Models the physics of automatic transmission systems:
- Torque converter (fluid coupling)
- Planetary gear sets
- Clutch packs and bands
- Hydraulic control system
- Shift quality and timing

Physics principles:
- Torque multiplication = f(speed ratio)
- Gear ratios determine mechanical advantage
- Clutch slip = torque capacity vs input torque
- Shift timing = f(vehicle speed, throttle position, load)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import math


class GearState(Enum):
    """Current gear state."""
    PARK = "P"
    REVERSE = "R"
    NEUTRAL = "N"
    DRIVE_1 = "1"
    DRIVE_2 = "2"
    DRIVE_3 = "3"
    DRIVE_4 = "4"
    DRIVE_5 = "5"
    DRIVE_6 = "6"


class ShiftQuality(Enum):
    """Shift quality assessment."""
    SMOOTH = "smooth"
    NORMAL = "normal"
    FIRM = "firm"
    HARSH = "harsh"
    SLIPPING = "slipping"
    FLARE = "flare"  # RPM flare during shift


@dataclass
class TorqueConverterModel:
    """
    Torque converter physics model.
    
    The torque converter is a fluid coupling that:
    - Multiplies torque at low speed ratios
    - Acts as a clutch for smooth engagement
    - Has a lockup clutch for efficiency
    
    Key physics:
    - Torque ratio = f(speed ratio) where speed_ratio = turbine/impeller
    - Efficiency = speed_ratio * torque_ratio
    - Stall torque ratio typically 2.0-2.5x
    """
    
    # Design parameters
    stall_torque_ratio: float = 2.2        # Torque multiplication at stall
    coupling_point: float = 0.85           # Speed ratio where torque_ratio = 1.0
    lockup_min_speed_ratio: float = 0.9    # Minimum for lockup engagement
    
    # Current state
    impeller_rpm: float = 0.0              # Engine side
    turbine_rpm: float = 0.0               # Transmission side
    lockup_engaged: bool = False
    lockup_slip_rpm: float = 0.0           # Slip when lockup engaged
    
    # Fault injection
    _fault: str = None
    _fault_severity: float = 0.0
    
    def reset(self):
        """Reset to default state."""
        self.impeller_rpm = 0.0
        self.turbine_rpm = 0.0
        self.lockup_engaged = False
        self.lockup_slip_rpm = 0.0
        self._fault = None
        self._fault_severity = 0.0
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """Inject a fault."""
        self._fault = fault
        self._fault_severity = min(1.0, max(0.0, severity))
    
    def get_speed_ratio(self) -> float:
        """Calculate turbine/impeller speed ratio."""
        if self.impeller_rpm < 100:
            return 0.0
        return self.turbine_rpm / self.impeller_rpm
    
    def get_torque_ratio(self) -> float:
        """
        Calculate torque multiplication.
        
        Torque ratio is highest at stall (speed_ratio=0) and
        decreases to 1.0 at the coupling point.
        """
        speed_ratio = self.get_speed_ratio()
        
        if self._fault == "tc_worn":
            # Reduced torque multiplication
            stall_ratio = self.stall_torque_ratio - (0.5 * self._fault_severity)
        else:
            stall_ratio = self.stall_torque_ratio
        
        if speed_ratio >= self.coupling_point:
            return 1.0  # Past coupling point
        
        # Linear interpolation from stall to coupling
        fraction = speed_ratio / self.coupling_point
        return stall_ratio - (stall_ratio - 1.0) * fraction
    
    def get_efficiency(self) -> float:
        """
        Calculate torque converter efficiency.
        
        Efficiency = speed_ratio * torque_ratio
        Maximum efficiency is at coupling point (~85%)
        """
        if self.lockup_engaged:
            # Nearly 100% when locked
            if self._fault == "tc_lockup_slipping":
                return 0.95 - 0.1 * self._fault_severity
            return 0.98
        
        speed_ratio = self.get_speed_ratio()
        torque_ratio = self.get_torque_ratio()
        
        return speed_ratio * torque_ratio
    
    def update(self, engine_rpm: float, load_torque_nm: float, engine_torque_nm: float):
        """
        Update torque converter state.
        
        Args:
            engine_rpm: Engine/impeller RPM
            load_torque_nm: Load on turbine
            engine_torque_nm: Engine output torque
        """
        self.impeller_rpm = engine_rpm
        
        # For steady state operation, estimate turbine speed based on load
        # Light load = high speed ratio, heavy load = low speed ratio
        if engine_torque_nm > 0:
            # Approximate speed ratio based on torque ratio needed
            torque_ratio_needed = load_torque_nm / engine_torque_nm if engine_torque_nm > 0 else 1.0
            torque_ratio_needed = max(1.0, min(self.stall_torque_ratio, torque_ratio_needed))
            
            # Invert the torque ratio curve to find speed ratio
            # torque_ratio = stall - (stall - 1.0) * (speed_ratio / coupling_point)
            # speed_ratio = (stall - torque_ratio) / (stall - 1.0) * coupling_point
            if torque_ratio_needed >= self.stall_torque_ratio:
                speed_ratio = 0.0  # Stall
            elif torque_ratio_needed <= 1.0:
                speed_ratio = self.coupling_point  # Coupling
            else:
                speed_ratio = (self.stall_torque_ratio - torque_ratio_needed) / (self.stall_torque_ratio - 1.0) * self.coupling_point
            
            self.turbine_rpm = engine_rpm * speed_ratio
        else:
            self.turbine_rpm = 0
        
        # Faults
        if self._fault == "tc_shudder":
            # Oscillation in lockup
            if self.lockup_engaged:
                self.lockup_slip_rpm = 50 * self._fault_severity * math.sin(engine_rpm * 0.01)
        elif self._fault == "tc_lockup_not_engaging":
            self.lockup_engaged = False


@dataclass
class PlanetaryGearSet:
    """
    Planetary gear set model.
    
    A planetary set has:
    - Sun gear (center)
    - Planet gears (orbit around sun)
    - Ring gear (outer)
    - Planet carrier (holds planets)
    
    Different gear ratios achieved by holding different elements.
    """
    
    # Gear tooth counts
    sun_teeth: int = 30
    ring_teeth: int = 70
    
    # Calculated ratios
    @property
    def ring_to_sun_ratio(self) -> float:
        """Ratio of ring teeth to sun teeth."""
        return self.ring_teeth / self.sun_teeth
    
    def get_ratio_sun_input_ring_held(self) -> float:
        """Gear ratio when sun is input, ring is held, carrier is output."""
        # Reduction ratio
        return 1 + self.ring_to_sun_ratio
    
    def get_ratio_ring_input_sun_held(self) -> float:
        """Gear ratio when ring is input, sun is held, carrier is output."""
        # Reduction ratio
        return 1 + (1 / self.ring_to_sun_ratio)


@dataclass
class ClutchPackModel:
    """
    Clutch pack (friction element) model.
    
    Clutch packs and bands are used to hold or connect
    gear set elements for different gear ratios.
    
    Key physics:
    - Torque capacity = f(apply pressure, friction area, friction coefficient)
    - Slip occurs when input torque > capacity
    """
    
    # Design parameters - sized for typical passenger car transmission
    friction_coefficient: float = 0.12     # Typical for ATF
    num_friction_surfaces: int = 8         # Number of clutch plates
    mean_radius_m: float = 0.08            # Mean friction radius
    piston_area_m2: float = 0.012          # Hydraulic piston area (larger)
    
    # Current state
    apply_pressure_kpa: float = 0.0        # Hydraulic pressure
    input_torque_nm: float = 0.0           # Torque being transmitted
    slip_rpm: float = 0.0                  # Slip speed
    
    # Fault injection
    _fault: str = None
    _fault_severity: float = 0.0
    
    def reset(self):
        """Reset clutch state."""
        self.apply_pressure_kpa = 0.0
        self.input_torque_nm = 0.0
        self.slip_rpm = 0.0
        self._fault = None
        self._fault_severity = 0.0
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """Inject a fault."""
        self._fault = fault
        self._fault_severity = min(1.0, max(0.0, severity))
    
    def get_torque_capacity(self) -> float:
        """
        Calculate maximum torque the clutch can hold.
        
        T = μ * F * r * n
        where:
            μ = friction coefficient
            F = clamping force (pressure * area)
            r = mean radius
            n = number of friction surfaces
        """
        if self.apply_pressure_kpa <= 0:
            return 0.0
        
        mu = self.friction_coefficient
        
        # Apply faults
        if self._fault == "clutch_worn":
            mu *= (1.0 - 0.5 * self._fault_severity)  # Reduced friction (50% at full severity)
        elif self._fault == "clutch_burnt":
            mu *= (1.0 - 0.7 * self._fault_severity)  # Glazed surfaces (70% at full)
        
        # Clamping force (N) = pressure (kPa) * 1000 * area (m²)
        force_n = self.apply_pressure_kpa * 1000 * self.piston_area_m2
        
        # Torque capacity
        capacity = mu * force_n * self.mean_radius_m * self.num_friction_surfaces
        
        return capacity
    
    def is_slipping(self, input_torque: float) -> bool:
        """Check if clutch is slipping."""
        capacity = self.get_torque_capacity()
        
        if self._fault == "clutch_apply_circuit_leak":
            # Pressure can't build properly
            return input_torque > capacity * 0.3
        
        return input_torque > capacity
    
    def get_slip_rpm(self, input_torque: float, input_rpm: float) -> float:
        """
        Calculate slip RPM.
        
        Args:
            input_torque: Input torque (Nm)
            input_rpm: Input speed (RPM)
            
        Returns:
            Slip speed (RPM)
        """
        capacity = self.get_torque_capacity()
        
        if capacity <= 0:
            return input_rpm  # Full slip
        
        if input_torque <= capacity:
            return 0.0  # No slip
        
        # Slip proportional to torque excess
        excess_ratio = (input_torque - capacity) / capacity
        self.slip_rpm = min(input_rpm, excess_ratio * 500)
        
        return self.slip_rpm


@dataclass
class TransmissionState:
    """Current transmission state."""
    gear: GearState = GearState.NEUTRAL
    gear_ratio: float = 0.0
    input_rpm: float = 0.0
    output_rpm: float = 0.0
    torque_converter_speed_ratio: float = 0.0
    torque_converter_efficiency: float = 0.0
    lockup_engaged: bool = False
    line_pressure_kpa: float = 0.0
    atf_temp_c: float = 80.0
    shift_quality: ShiftQuality = ShiftQuality.NORMAL
    slip_detected: bool = False


@dataclass
class TransmissionModel:
    """
    Complete automatic transmission model.
    
    Models a 6-speed automatic with:
    - Torque converter with lockup
    - Multiple clutch packs
    - Shift scheduling
    - Line pressure control
    """
    
    # Design parameters - typical 6-speed ratios
    gear_ratios: Dict[GearState, float] = field(default_factory=lambda: {
        GearState.PARK: 0.0,
        GearState.REVERSE: -3.22,
        GearState.NEUTRAL: 0.0,
        GearState.DRIVE_1: 4.17,
        GearState.DRIVE_2: 2.34,
        GearState.DRIVE_3: 1.52,
        GearState.DRIVE_4: 1.14,
        GearState.DRIVE_5: 0.87,
        GearState.DRIVE_6: 0.69,
    })
    final_drive_ratio: float = 3.42
    
    # Components
    torque_converter: TorqueConverterModel = field(default_factory=TorqueConverterModel)
    clutch_packs: Dict[str, ClutchPackModel] = field(default_factory=lambda: {
        "forward": ClutchPackModel(),
        "direct": ClutchPackModel(),
        "low_reverse": ClutchPackModel(),
        "overdrive": ClutchPackModel(),
        "2_4_band": ClutchPackModel(),
    })
    
    # Current state
    current_gear: GearState = GearState.PARK
    line_pressure_kpa: float = 500.0
    atf_temp_c: float = 80.0
    
    # Shift state
    target_gear: GearState = GearState.PARK
    shift_in_progress: bool = False
    shift_progress: float = 0.0  # 0-1
    
    # Fault tracking
    _injected_faults: Dict[str, float] = field(default_factory=dict)
    
    def reset(self):
        """Reset transmission state."""
        self.current_gear = GearState.PARK
        self.target_gear = GearState.PARK
        self.line_pressure_kpa = 500.0
        self.atf_temp_c = 80.0
        self.shift_in_progress = False
        self.shift_progress = 0.0
        
        self.torque_converter.reset()
        for clutch in self.clutch_packs.values():
            clutch.reset()
        
        self._injected_faults.clear()
    
    def inject_fault(self, fault: str, severity: float = 1.0):
        """
        Inject a transmission fault.
        
        Supported faults:
        - tc_worn: Worn torque converter
        - tc_shudder: Torque converter shudder
        - tc_lockup_slipping: Lockup clutch slipping
        - tc_lockup_not_engaging: Lockup won't engage
        - low_line_pressure: Low hydraulic pressure
        - high_line_pressure: Excessive line pressure
        - clutch_forward_worn: Forward clutch worn
        - clutch_forward_burnt: Forward clutch burnt
        - clutch_direct_worn: Direct clutch worn
        - shift_solenoid_stuck: Shift solenoid stuck
        - pressure_control_failed: Pressure control solenoid failed
        - valve_body_wear: Worn valve body
        - atf_degraded: Degraded transmission fluid
        """
        self._injected_faults[fault] = severity
        
        if fault.startswith("tc_"):
            self.torque_converter.inject_fault(fault, severity)
        elif fault.startswith("clutch_forward"):
            clutch_fault = fault.replace("clutch_forward_", "clutch_")
            self.clutch_packs["forward"].inject_fault(clutch_fault, severity)
        elif fault.startswith("clutch_direct"):
            clutch_fault = fault.replace("clutch_direct_", "clutch_")
            self.clutch_packs["direct"].inject_fault(clutch_fault, severity)
    
    def get_effective_gear_ratio(self) -> float:
        """Get total gear ratio including final drive."""
        gear_ratio = self.gear_ratios.get(self.current_gear, 0.0)
        return gear_ratio * self.final_drive_ratio
    
    def determine_target_gear(
        self,
        vehicle_speed_kph: float,
        throttle_percent: float,
        engine_rpm: float
    ) -> GearState:
        """
        Determine target gear based on shift schedule.
        
        Args:
            vehicle_speed_kph: Vehicle speed
            throttle_percent: Throttle position (0-100)
            engine_rpm: Current engine RPM
            
        Returns:
            Target gear state
        """
        if self.current_gear in [GearState.PARK, GearState.REVERSE, GearState.NEUTRAL]:
            return self.current_gear
        
        # Simplified shift schedule
        # Upshift points increase with throttle (more aggressive driving = later shifts)
        upshift_base = 20.0  # Base upshift speed increment per gear
        upshift_throttle_factor = 0.3  # Speed increase per % throttle
        
        # Downshift points
        downshift_base = 15.0
        
        current_gear_num = int(self.current_gear.value)
        
        # Calculate upshift and downshift thresholds
        upshift_speed = upshift_base * current_gear_num + throttle_percent * upshift_throttle_factor
        downshift_speed = downshift_base * (current_gear_num - 1)
        
        # Check for shift
        if vehicle_speed_kph > upshift_speed and current_gear_num < 6:
            # Upshift
            return GearState(str(current_gear_num + 1))
        elif vehicle_speed_kph < downshift_speed and current_gear_num > 1:
            # Downshift
            return GearState(str(current_gear_num - 1))
        
        return self.current_gear
    
    def calculate_line_pressure(self, throttle_percent: float, engine_torque_nm: float) -> float:
        """
        Calculate required line pressure.
        
        Line pressure increases with load to prevent clutch slip.
        """
        base_pressure = 400.0  # kPa at idle
        
        # Increase with throttle/load
        load_pressure = throttle_percent * 8.0  # Up to 800 kPa at WOT
        
        # Minimum pressure based on torque
        torque_pressure = engine_torque_nm * 1.5
        
        required = max(base_pressure + load_pressure, torque_pressure)
        
        # Apply faults
        if "low_line_pressure" in self._injected_faults:
            severity = self._injected_faults["low_line_pressure"]
            required *= (1.0 - 0.5 * severity)
        elif "high_line_pressure" in self._injected_faults:
            severity = self._injected_faults["high_line_pressure"]
            required *= (1.0 + 0.5 * severity)
        elif "pressure_control_failed" in self._injected_faults:
            required = 400.0  # Stuck at limp mode pressure
        
        return min(1500.0, required)  # Max pressure limit
    
    def get_shift_quality(self, input_torque: float) -> ShiftQuality:
        """Assess shift quality based on conditions."""
        # High line pressure = harsh shifts (check first)
        if "high_line_pressure" in self._injected_faults:
            return ShiftQuality.HARSH
        
        # Valve body wear = firm shifts
        if "valve_body_wear" in self._injected_faults:
            return ShiftQuality.FIRM
        
        # Check for clutch slip
        forward_clutch = self.clutch_packs["forward"]
        if forward_clutch.is_slipping(input_torque):
            return ShiftQuality.SLIPPING
        
        # Low line pressure = slip/flare (if not already slipping)
        if "low_line_pressure" in self._injected_faults:
            severity = self._injected_faults["low_line_pressure"]
            if severity > 0.7:
                return ShiftQuality.SLIPPING
            elif severity > 0.3:
                return ShiftQuality.FLARE
            return ShiftQuality.FIRM
        
        return ShiftQuality.NORMAL
    
    def simulate(
        self,
        engine_rpm: float = 1500,
        engine_torque_nm: float = 150,
        vehicle_speed_kph: float = 50,
        throttle_percent: float = 20,
        selected_range: str = "D",  # P, R, N, D
    ) -> TransmissionState:
        """
        Simulate transmission state.
        
        Args:
            engine_rpm: Engine RPM
            engine_torque_nm: Engine output torque
            vehicle_speed_kph: Vehicle speed
            throttle_percent: Throttle position (0-100)
            selected_range: Selector position
            
        Returns:
            Current transmission state
        """
        state = TransmissionState()
        
        # Handle selector position
        if selected_range == "P":
            self.current_gear = GearState.PARK
        elif selected_range == "R":
            self.current_gear = GearState.REVERSE
        elif selected_range == "N":
            self.current_gear = GearState.NEUTRAL
        elif selected_range == "D" and self.current_gear in [GearState.PARK, GearState.NEUTRAL, GearState.REVERSE]:
            self.current_gear = GearState.DRIVE_1
        
        state.gear = self.current_gear
        
        # Calculate line pressure
        self.line_pressure_kpa = self.calculate_line_pressure(throttle_percent, engine_torque_nm)
        state.line_pressure_kpa = self.line_pressure_kpa
        
        # Apply line pressure to clutches
        for clutch in self.clutch_packs.values():
            clutch.apply_pressure_kpa = self.line_pressure_kpa
        
        # Update torque converter
        # Estimate load torque based on speed and grade
        load_torque = vehicle_speed_kph * 2.0  # Simplified
        self.torque_converter.update(engine_rpm, load_torque, engine_torque_nm)
        
        state.torque_converter_speed_ratio = self.torque_converter.get_speed_ratio()
        state.torque_converter_efficiency = self.torque_converter.get_efficiency()
        
        # Lockup control - engage at cruise
        if vehicle_speed_kph > 60 and throttle_percent < 50:
            if "tc_lockup_not_engaging" not in self._injected_faults:
                self.torque_converter.lockup_engaged = True
        else:
            self.torque_converter.lockup_engaged = False
        
        state.lockup_engaged = self.torque_converter.lockup_engaged
        
        # Determine if shift needed (in Drive)
        if selected_range == "D":
            target = self.determine_target_gear(vehicle_speed_kph, throttle_percent, engine_rpm)
            if target != self.current_gear:
                # Simple shift - just change gear
                # Real model would simulate shift overlap
                self.current_gear = target
                state.gear = self.current_gear
        
        # Calculate ratios and speeds
        state.gear_ratio = self.get_effective_gear_ratio()
        state.input_rpm = engine_rpm
        
        if abs(state.gear_ratio) > 0:
            state.output_rpm = engine_rpm / abs(state.gear_ratio)
        else:
            state.output_rpm = 0.0
        
        # Check for slip
        forward_clutch = self.clutch_packs["forward"]
        transmitted_torque = engine_torque_nm * self.torque_converter.get_torque_ratio()
        state.slip_detected = forward_clutch.is_slipping(transmitted_torque)
        
        # Assess shift quality
        state.shift_quality = self.get_shift_quality(transmitted_torque)
        
        # ATF temperature
        state.atf_temp_c = self.atf_temp_c
        if "atf_degraded" in self._injected_faults:
            # Degraded fluid runs hotter
            state.atf_temp_c += 20 * self._injected_faults["atf_degraded"]
        
        return state


def run_tests():
    """Run transmission system tests."""
    print("=" * 60)
    print("TRANSMISSION SYSTEM PHYSICS MODEL TESTS")
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
    
    # Test 1: Normal operation
    print("\n--- Test 1: Normal Operation ---")
    model = TransmissionModel()
    state = model.simulate(
        engine_rpm=2000,
        engine_torque_nm=200,
        vehicle_speed_kph=80,
        throttle_percent=30,
        selected_range="D"
    )
    check(
        "In drive gear",
        state.gear not in [GearState.PARK, GearState.NEUTRAL, GearState.REVERSE],
        f"(gear={state.gear.value})"
    )
    check(
        "Torque converter coupling",
        state.torque_converter_speed_ratio > 0.8,
        f"(speed_ratio={state.torque_converter_speed_ratio:.2f})"
    )
    check(
        "Lockup engaged at cruise",
        state.lockup_engaged,
        f"(lockup={state.lockup_engaged})"
    )
    check(
        "No slip detected",
        not state.slip_detected,
        f"(slip={state.slip_detected})"
    )
    check(
        "Normal shift quality",
        state.shift_quality == ShiftQuality.NORMAL,
        f"(quality={state.shift_quality.value})"
    )
    
    # Test 2: Low line pressure - slipping
    print("\n--- Test 2: Low Line Pressure ---")
    model = TransmissionModel()
    model.inject_fault("low_line_pressure", severity=0.8)
    state = model.simulate(
        engine_rpm=3000,
        engine_torque_nm=350,  # High torque
        vehicle_speed_kph=60,
        throttle_percent=80,
        selected_range="D"
    )
    check(
        "Low pressure causes slip or flare",
        state.shift_quality in [ShiftQuality.SLIPPING, ShiftQuality.FLARE],
        f"(quality={state.shift_quality.value})"
    )
    
    # Test 3: Torque converter shudder
    print("\n--- Test 3: Torque Converter Shudder ---")
    model = TransmissionModel()
    model.inject_fault("tc_shudder", severity=1.0)
    # With shudder, simulate multiple cycles to see oscillation
    slip_values = []
    for rpm in [1800, 1850, 1900, 1950, 2000]:
        state = model.simulate(
            engine_rpm=rpm,
            engine_torque_nm=200,
            vehicle_speed_kph=70,
            throttle_percent=25,
            selected_range="D"
        )
        slip_values.append(model.torque_converter.lockup_slip_rpm)
    # Shudder should cause varying slip values
    slip_range = max(slip_values) - min(slip_values)
    check(
        "TC shudder causes slip variation",
        slip_range > 5 or any(abs(s) > 0.1 for s in slip_values),
        f"(slip_range={slip_range:.1f}, values={[f'{s:.1f}' for s in slip_values]})"
    )
    
    # Test 4: Lockup not engaging
    print("\n--- Test 4: Lockup Not Engaging ---")
    model = TransmissionModel()
    model.inject_fault("tc_lockup_not_engaging", severity=1.0)
    state = model.simulate(
        engine_rpm=2500,
        engine_torque_nm=150,
        vehicle_speed_kph=100,
        throttle_percent=20,
        selected_range="D"
    )
    check(
        "Lockup stays disengaged",
        not state.lockup_engaged,
        f"(lockup={state.lockup_engaged})"
    )
    check(
        "Lower TC efficiency without lockup",
        state.torque_converter_efficiency < 0.95,
        f"(efficiency={state.torque_converter_efficiency:.2f})"
    )
    
    # Test 5: High line pressure - harsh shifts
    print("\n--- Test 5: High Line Pressure ---")
    model = TransmissionModel()
    model.inject_fault("high_line_pressure", severity=0.8)
    state = model.simulate(
        engine_rpm=2000,
        engine_torque_nm=200,
        vehicle_speed_kph=50,
        throttle_percent=40,
        selected_range="D"
    )
    check(
        "High pressure causes harsh shifts",
        state.shift_quality == ShiftQuality.HARSH,
        f"(quality={state.shift_quality.value})"
    )
    
    # Test 6: Forward clutch worn
    print("\n--- Test 6: Forward Clutch Worn ---")
    model = TransmissionModel()
    model.inject_fault("clutch_forward_worn", severity=0.9)
    # Use high torque but moderate throttle so line pressure doesn't compensate fully
    state = model.simulate(
        engine_rpm=2500,
        engine_torque_nm=500,  # Very high torque (like towing)
        vehicle_speed_kph=30,  # Low speed for torque multiplication
        throttle_percent=40,   # Moderate throttle = moderate line pressure
        selected_range="D"
    )
    # Check if either slip is detected or clutch capacity is exceeded
    clutch = model.clutch_packs["forward"]
    transmitted_torque = 500 * model.torque_converter.get_torque_ratio()
    capacity = clutch.get_torque_capacity()
    check(
        "Worn clutch slips under load",
        state.slip_detected or state.shift_quality == ShiftQuality.SLIPPING or transmitted_torque > capacity,
        f"(slip={state.slip_detected}, quality={state.shift_quality.value}, torque={transmitted_torque:.0f}Nm, capacity={capacity:.0f}Nm)"
    )
    
    # Test 7: Gear ratio calculation
    print("\n--- Test 7: Gear Ratio Calculation ---")
    model = TransmissionModel()
    model.current_gear = GearState.DRIVE_1
    ratio_1st = model.get_effective_gear_ratio()
    model.current_gear = GearState.DRIVE_6
    ratio_6th = model.get_effective_gear_ratio()
    check(
        "1st gear has higher ratio than 6th",
        ratio_1st > ratio_6th,
        f"(1st={ratio_1st:.2f}, 6th={ratio_6th:.2f})"
    )
    check(
        "Reasonable ratio range",
        ratio_1st > 10 and ratio_6th < 5,
        f"(ratios cover 5x-15x range)"
    )
    
    # Summary
    print("\n" + "=" * 60)
    print(f"  Total: {passed}/{passed+failed} tests passed")
    print("=" * 60)
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED! Transmission system model is working correctly.")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review output above.")
    
    return failed == 0


if __name__ == "__main__":
    run_tests()
