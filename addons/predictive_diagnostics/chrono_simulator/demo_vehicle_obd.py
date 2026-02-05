#!/usr/bin/env python3
"""
PyChrono Vehicle Simulation for Automotive Diagnostics
Based on official HMMWV demo from Project Chrono

This demonstrates how to:
1. Create a full vehicle with powertrain
2. Run physics simulation
3. Extract OBD-II style sensor data
4. (Future) Inject faults for training data generation
"""

import pychrono as chrono
import pychrono.vehicle as veh
import math

def main():
    print("=" * 60)
    print("PyChrono Vehicle Simulation Test")
    print("=" * 60)
    
    # -------------------------
    # Configuration
    # -------------------------
    contact_method = chrono.ChContactMethod_NSC  # Non-smooth contact
    step_size = 1e-3  # 1ms timestep
    sim_time = 5.0    # 5 seconds simulation
    
    # Initial position
    init_loc = chrono.ChVector3d(0, 0, 1.6)  # 1.6m above ground
    init_rot = chrono.ChQuaterniond(1, 0, 0, 0)  # Identity rotation
    
    # -------------------------
    # Create HMMWV Vehicle
    # -------------------------
    print("\n[1] Creating HMMWV vehicle...")
    
    hmmwv = veh.HMMWV_Full()
    hmmwv.SetContactMethod(contact_method)
    hmmwv.SetChassisCollisionType(veh.CollisionType_NONE)
    hmmwv.SetChassisFixed(False)
    hmmwv.SetInitPosition(chrono.ChCoordsysd(init_loc, init_rot))
    
    # Powertrain configuration
    hmmwv.SetEngineType(veh.EngineModelType_SIMPLE_MAP)  # Simpler engine model
    hmmwv.SetTransmissionType(veh.TransmissionModelType_AUTOMATIC_SIMPLE_MAP)
    hmmwv.SetDriveType(veh.DrivelineTypeWV_AWD)  # All-wheel drive
    
    # Tire configuration
    hmmwv.SetTireType(veh.TireModelType_TMEASY)
    hmmwv.SetTireStepSize(step_size)
    
    # Initialize vehicle
    hmmwv.Initialize()
    
    print(f"    Vehicle mass: {hmmwv.GetVehicle().GetMass():.0f} kg")
    print(f"    Wheelbase: {hmmwv.GetVehicle().GetWheelbase():.3f} m")
    
    # -------------------------
    # Create Terrain
    # -------------------------
    print("\n[2] Creating terrain...")
    
    terrain = veh.RigidTerrain(hmmwv.GetSystem())
    patch_mat = chrono.ChContactMaterialNSC()
    patch_mat.SetFriction(0.9)
    patch_mat.SetRestitution(0.01)
    
    patch = terrain.AddPatch(patch_mat, chrono.CSYSNORM, 200, 200)
    terrain.Initialize()
    
    print("    Created 200x200m flat terrain")
    
    # -------------------------
    # Create Driver (programmatic inputs)
    # -------------------------
    print("\n[3] Setting up driver inputs...")
    
    # We'll use direct input values instead of interactive driver
    # This allows us to script acceleration, braking scenarios
    
    # -------------------------
    # Simulation Loop
    # -------------------------
    print("\n[4] Running simulation...")
    print(f"    Duration: {sim_time}s, Step: {step_size*1000:.1f}ms")
    
    time = 0
    step_number = 0
    log_interval = 0.5  # Log every 0.5 seconds
    last_log_time = -log_interval
    
    data_log = []
    
    # Scenario: accelerate for 3s, then coast
    while time < sim_time:
        # Define driver inputs based on scenario
        if time < 3.0:
            throttle = 0.5  # 50% throttle for 3 seconds
            braking = 0.0
        else:
            throttle = 0.0  # Coast
            braking = 0.0
            
        steering = 0.0  # Straight ahead
        
        # Create driver inputs struct
        driver_inputs = veh.DriverInputs()
        driver_inputs.m_steering = steering
        driver_inputs.m_throttle = throttle
        driver_inputs.m_braking = braking
        
        # Synchronize systems
        terrain.Synchronize(time)
        hmmwv.Synchronize(time, driver_inputs, terrain)
        
        # Advance systems
        terrain.Advance(step_size)
        hmmwv.Advance(step_size)
        
        time += step_size
        step_number += 1
        
        # Log data periodically
        if time - last_log_time >= log_interval:
            last_log_time = time
            
            vehicle = hmmwv.GetVehicle()
            engine = vehicle.GetEngine()
            trans = vehicle.GetTransmission()
            
            # Extract OBD-II style data
            data = {
                'time': time,
                'speed_ms': vehicle.GetSpeed(),
                'speed_kmh': vehicle.GetSpeed() * 3.6,
                'throttle_pos': throttle * 100,  # percentage
                'engine_rpm': engine.GetMotorSpeed() * 60 / (2*math.pi) if engine else 0,
                'engine_torque_nm': engine.GetOutputMotorshaftTorque() if engine else 0,
                'gear': trans.GetCurrentGear() if trans else 0,
                'pos_x': vehicle.GetPos().x,
                'pos_y': vehicle.GetPos().y,
            }
            data_log.append(data)
    
    # -------------------------
    # Results
    # -------------------------
    print("\n[5] Simulation Results (OBD-II Style Data):")
    print("-" * 80)
    print(f"{'Time':>6} | {'Speed':>8} | {'RPM':>8} | {'Torque':>8} | {'Gear':>4} | {'Throttle':>8} | {'Pos X':>8}")
    print(f"{'(s)':>6} | {'(km/h)':>8} | {'':>8} | {'(Nm)':>8} | {'':>4} | {'(%)':>8} | {'(m)':>8}")
    print("-" * 80)
    
    for d in data_log:
        print(f"{d['time']:6.1f} | {d['speed_kmh']:8.1f} | {d['engine_rpm']:8.0f} | "
              f"{d['engine_torque_nm']:8.1f} | {d['gear']:4d} | {d['throttle_pos']:8.0f} | {d['pos_x']:8.1f}")
    
    # Summary
    max_speed = max(d['speed_kmh'] for d in data_log)
    max_rpm = max(d['engine_rpm'] for d in data_log)
    total_distance = data_log[-1]['pos_x']
    
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Max speed: {max_speed:.1f} km/h ({max_speed/3.6:.1f} m/s)")
    print(f"  Max RPM: {max_rpm:.0f}")
    print(f"  Distance traveled: {total_distance:.1f} m")
    print("=" * 60)
    
    return True


def list_available_sensors():
    """List what sensor data we can extract from the vehicle."""
    print("\n" + "=" * 60)
    print("Available Sensor Data (OBD-II Mapping)")
    print("=" * 60)
    
    sensors = [
        ("Vehicle Speed", "GetSpeed()", "PID 0x0D"),
        ("Engine RPM", "GetEngine().GetMotorSpeed()", "PID 0x0C"),
        ("Throttle Position", "driver_inputs.m_throttle", "PID 0x11"),
        ("Engine Load", "Derived from torque/max_torque", "PID 0x04"),
        ("Gear", "GetTransmission().GetCurrentGear()", "N/A"),
        ("Wheel Speeds", "GetTire().GetWheelOmega()", "ABS system"),
        ("Tire Forces", "GetTire().ReportTireForce()", "N/A"),
        ("Vehicle Position", "GetPos()", "GPS"),
        ("Vehicle Orientation", "GetRot()", "IMU"),
    ]
    
    print(f"\n{'Sensor':<25} | {'Chrono Method':<35} | {'OBD-II'}")
    print("-" * 75)
    for name, method, obd in sensors:
        print(f"{name:<25} | {method:<35} | {obd}")


def explore_fault_injection():
    """Demonstrate how we could inject faults."""
    print("\n" + "=" * 60)
    print("Fault Injection Examples")
    print("=" * 60)
    
    print("""
Faults we can simulate in PyChrono:

1. ENGINE MISFIRE:
   - Reduce torque output periodically
   - Add torque fluctuations at idle
   - Code: engine_torque *= (1.0 - misfire_rate * random())

2. SENSOR DRIFT (e.g., O2 sensor, MAF):
   - Post-process readings with bias
   - Code: o2_reading = actual_value * (1.0 + drift_percentage)

3. TIRE ISSUES:
   - Reduce friction coefficient → tire slip
   - Code: patch_mat.SetFriction(0.3)  # Worn/wet tires

4. THROTTLE PROBLEMS:
   - Stuck throttle: throttle = min(throttle, 0.8)
   - Delayed response: throttle = 0.9 * prev_throttle + 0.1 * requested

5. TRANSMISSION ISSUES:
   - Lock in gear: override transmission output
   - Slipping: reduce torque transmission efficiency

6. BRAKE ISSUES:
   - Reduced braking force
   - Uneven braking (pull to side)
""")


if __name__ == '__main__':
    # Run main simulation
    success = main()
    
    # Show additional info
    list_available_sensors()
    explore_fault_injection()
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE" if success else "TEST FAILED")
    print("=" * 60)
