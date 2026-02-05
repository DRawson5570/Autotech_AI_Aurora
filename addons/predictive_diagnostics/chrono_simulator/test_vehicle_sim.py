#!/usr/bin/env python3
"""
Test PyChrono vehicle simulation for automotive diagnostics.

This demonstrates:
1. Creating a vehicle model (BMW E90)
2. Running physics simulation
3. Extracting OBD-II style sensor data
4. Injecting faults (future work)
"""

import pychrono as chrono
import pychrono.vehicle as veh

def test_basic_vehicle():
    """Test basic vehicle creation and simulation."""
    print("=" * 60)
    print("PyChrono Vehicle Simulation Test")
    print("=" * 60)
    
    # Create the simulation system
    system = chrono.ChSystemNSC()
    system.SetGravitationalAcceleration(chrono.ChVector3d(0, 0, -9.81))
    
    print("\n[1] Creating BMW E90 vehicle model...")
    
    # Create vehicle - use simplified construction
    # The BMW_E90 is a template vehicle included in PyChrono
    try:
        vehicle = veh.BMW_E90_Vehicle(
            system,                          # physics system
            False,                           # fixed chassis? 
            veh.ChContactMethod_NSC          # contact method
        )
        print(f"    Vehicle created: {type(vehicle).__name__}")
        
        # Get vehicle info
        print(f"    Mass: {vehicle.GetMass():.1f} kg")
        print(f"    Wheelbase: {vehicle.GetWheelbase():.3f} m")
        
        # Initialize at origin
        vehicle.Initialize(chrono.ChCoordsysd(chrono.ChVector3d(0, 0, 0.5)))
        print("    Initialized at origin")
        
    except Exception as e:
        print(f"    Error creating BMW E90: {e}")
        print("\n    Trying generic wheeled vehicle...")
        # Fall back to basic vehicle components
        return test_basic_components()
    
    print("\n[2] Running simulation (1 second)...")
    
    # Simulation parameters
    step_size = 0.001  # 1ms timestep
    sim_time = 1.0     # 1 second
    
    # Collect sensor data
    sensor_log = []
    
    t = 0
    while t < sim_time:
        # Step the simulation
        system.DoStepDynamics(step_size)
        t += step_size
        
        # Log data every 100ms
        if int(t * 10) != int((t - step_size) * 10):
            data = {
                'time': t,
                'speed': vehicle.GetSpeed(),  # m/s
                'pos': vehicle.GetPos(),
            }
            sensor_log.append(data)
            
    print(f"    Completed {len(sensor_log)} samples")
    
    print("\n[3] Sensor data (OBD-II style):")
    for sample in sensor_log[:5]:
        print(f"    t={sample['time']:.1f}s: speed={sample['speed']*3.6:.1f} km/h, "
              f"pos=({sample['pos'].x:.2f}, {sample['pos'].y:.2f}, {sample['pos'].z:.2f})")
    
    print("\n" + "=" * 60)
    print("SUCCESS: Vehicle simulation working!")
    print("=" * 60)
    return True


def test_basic_components():
    """Test basic vehicle components if full vehicle fails."""
    print("\n[1b] Testing individual vehicle components...")
    
    # Test engine
    print("\n  Engine components:")
    engine_items = [x for x in dir(veh) if 'Engine' in x]
    print(f"    Available: {engine_items[:5]}...")
    
    # Test powertrain
    print("\n  Powertrain components:")  
    pt_items = [x for x in dir(veh) if 'Transmission' in x or 'Driveline' in x]
    print(f"    Available: {pt_items[:5]}...")
    
    # Test tire
    print("\n  Tire/Wheel components:")
    tire_items = [x for x in dir(veh) if 'Tire' in x or 'Wheel' in x]
    print(f"    Available: {tire_items[:5]}...")
    
    return False


def list_available_vehicles():
    """List all available vehicle templates."""
    print("\n" + "=" * 60)
    print("Available Vehicle Templates in PyChrono")
    print("=" * 60)
    
    # Find all vehicle classes
    vehicles = []
    for name in dir(veh):
        if name.endswith('_Vehicle') and not name.startswith('Ch'):
            vehicles.append(name.replace('_Vehicle', ''))
    
    print(f"\nFound {len(vehicles)} vehicle templates:")
    for v in sorted(vehicles):
        print(f"  - {v}")
    
    # Find all engine types
    print("\nEngine types:")
    engines = [x for x in dir(veh) if 'Engine' in x and 'Simple' in x]
    for e in engines[:5]:
        print(f"  - {e}")
    
    return vehicles


def explore_fault_injection():
    """Explore how we might inject faults."""
    print("\n" + "=" * 60)
    print("Fault Injection Exploration")
    print("=" * 60)
    
    print("\nApproaches for fault simulation:")
    print("""
1. SENSOR FAULTS:
   - Add noise/drift to sensor readings (post-process output)
   - Example: O2 sensor drift = add 10% bias to lambda value
   
2. ACTUATOR FAULTS:
   - Modify throttle/brake inputs before passing to vehicle
   - Example: Stuck throttle = clamp to fixed value
   
3. MECHANICAL FAULTS:
   - Modify tire friction (simulates worn tires, blowout)
   - Change suspension stiffness (simulates worn shocks)
   - Add losses to drivetrain (simulates failing transmission)
   
4. ENGINE FAULTS:
   - Reduce engine torque curve (simulates misfire)
   - Add torque fluctuations (simulates rough idle)
   - Modify fuel consumption (simulates lean/rich condition)
""")
    
    # Check what we can modify
    print("Modifiable components in PyChrono:")
    modifiable = [
        ('Tire friction', 'ChTire.SetFrictionCoefficient'),
        ('Engine torque', 'ChEngine torque map'),
        ('Suspension', 'ChSuspension spring/damper'),
        ('Brake', 'ChBrake max torque'),
    ]
    for name, method in modifiable:
        print(f"  - {name}: via {method}")


if __name__ == '__main__':
    # List what's available
    vehicles = list_available_vehicles()
    
    # Test vehicle simulation
    test_basic_vehicle()
    
    # Explore fault injection
    explore_fault_injection()
