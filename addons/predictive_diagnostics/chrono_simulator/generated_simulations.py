# Auto-generated FailureSimulations from knowledge base
# 42 failures with PID effects need simulations

register_simulation(FailureSimulation(
    failure_mode_id="cooling.water_pump_failure",
    failure_mode_name="Water Pump Failure",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": 105.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="water.pump_belt_slipping",
    failure_mode_name="Water Pump Belt Slipping",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": 100.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="radiator.blocked_external",
    failure_mode_name="Radiator Blocked (External)",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": 100.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="cooling.radiator_blocked",
    failure_mode_name="Radiator Blocked (Internal)",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": 105.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="cooling.fan_not_operating",
    failure_mode_name="Cooling Fan Not Operating",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": 105.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="cooling.fan_always_on",
    failure_mode_name="Cooling Fan Running Constantly",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": -82.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="pressure.cap_faulty",
    failure_mode_name="Radiator Pressure Cap Faulty",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['coolant_temp=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="ect.sensor_failed_high",
    failure_mode_name="Coolant Temp Sensor Reading High",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['coolant_temp=stuck_high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="ect.sensor_failed_low",
    failure_mode_name="Coolant Temp Sensor Reading Low",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "stft_b1": 10.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=stuck_low', 'stft=positive']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="cooling.coolant_leak",
    failure_mode_name="Coolant Leak",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "coolant_temp": 105.0,
    },
    expected_patterns={
        # From knowledge: ['coolant_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="low.compression",
    failure_mode_name="Low Cylinder Compression",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['misfire_count=high', 'rpm=unstable']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="head.gasket_failure",
    failure_mode_name="Head Gasket Failure",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['coolant_temp=high', 'misfire_count=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="timing.chain_stretched",
    failure_mode_name="Timing Chain Stretched/Worn",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['cam_crank_correlation=out_of_spec']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="oil.pump_failure",
    failure_mode_name="Oil Pump Failure",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "oil_pressure": -10.0,
    },
    expected_patterns={
        # From knowledge: ['oil_pressure=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="pcv.valve_stuck",
    failure_mode_name="PCV Valve Stuck",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['stft=variable', 'map=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="vvt.solenoid_stuck",
    failure_mode_name="VVT Solenoid Stuck/Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['cam_timing=stuck', 'cam_retard=stuck']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="cam.phaser_worn",
    failure_mode_name="Cam Phaser Worn/Rattling",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['cam_timing=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="fuel.injector_leaking",
    failure_mode_name="Fuel Injector Leaking",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "stft_b1": 17.5,
    },
    expected_patterns={
        # From knowledge: ['stft=negative', 'o2_sensor=rich']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="maf.sensor_contaminated",
    failure_mode_name="MAF Sensor Contaminated/Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['maf=erratic', 'stft=variable', 'ltft=variable']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="o2.sensor_failed",
    failure_mode_name="Oxygen Sensor Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['o2_sensor=stuck', 'stft=variable']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="ignition.coil_failed",
    failure_mode_name="Ignition Coil Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['misfire_count=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="ckp.sensor_failed",
    failure_mode_name="Crankshaft Position Sensor Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['rpm=zero']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="cmp.sensor_failed",
    failure_mode_name="Camshaft Position Sensor Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['cam_signal=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="ignition.module_failed",
    failure_mode_name="Ignition Control Module Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['misfire_count=high', 'rpm=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="secondary.ignition_leak",
    failure_mode_name="Secondary Ignition Leak (Plug Wire/Boot)",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['misfire_count=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="alternator.failing",
    failure_mode_name="Alternator Failing/Weak",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "battery_voltage": -13.5,
    },
    expected_patterns={
        # From knowledge: ['battery_voltage=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="battery.weak",
    failure_mode_name="Battery Weak/Failing",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "battery_voltage": -12.4,
    },
    expected_patterns={
        # From knowledge: ['battery_voltage=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="tesla.hv_isolation_fault",
    failure_mode_name="Tesla High Voltage Isolation Fault (Leakage to Chassis)",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "insulation_resistance": -1.0,
    },
    expected_patterns={
        # From knowledge: ['insulation_resistance=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="starter.motor_failing",
    failure_mode_name="Starter Motor Failing",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "cranking_rpm": -150.0,
    },
    expected_patterns={
        # From knowledge: ['cranking_rpm=low', 'battery_voltage=drops_excessively']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="turbo.wastegate_stuck_closed",
    failure_mode_name="Wastegate Stuck Closed (Overboost)",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['boost_pressure=high', 'timing_advance=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="turbo.wastegate_stuck_open",
    failure_mode_name="Wastegate Stuck Open (Underboost)",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['boost_pressure=low', 'maf_reading=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="turbo.bearing_failure",
    failure_mode_name="Turbo Bearing Failure",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['boost_pressure=low', 'oil_consumption=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="boost.leak",
    failure_mode_name="Boost/Charge Pipe Leak",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['boost_pressure=low', 'stft=positive', 'maf_reading=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="intercooler.clogged",
    failure_mode_name="Intercooler Clogged/Damaged",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['iat=high', 'boost_pressure=may_decrease']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="trans.fluid_low",
    failure_mode_name="Transmission Fluid Low/Burnt",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "trans_temp": 200.0,
    },
    expected_patterns={
        # From knowledge: ['trans_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="tcc.stuck_off",
    failure_mode_name="Torque Converter Clutch Stuck Off",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    sensor_biases={
        "tcc_slip": 100.0,
        "trans_temp": 200.0,
    },
    expected_patterns={
        # From knowledge: ['tcc_slip=high', 'trans_temp=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="tcc.stuck_on",
    failure_mode_name="Torque Converter Clutch Stuck On",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['tcc_slip=low']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="shift.solenoid_failed",
    failure_mode_name="Shift Solenoid Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['trans_gear=stuck']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="valve.body_failure",
    failure_mode_name="Valve Body Failure/Wear",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['line_pressure=erratic', 'shift_time=high']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="trans.speed_sensor_failed",
    failure_mode_name="Transmission Speed Sensor Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['vss=erratic', 'input_speed=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="abs.sensor_failed",
    failure_mode_name="ABS Wheel Speed Sensor Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['wheel_speed=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))

register_simulation(FailureSimulation(
    failure_mode_id="wheel.speed_sensor_failed",
    failure_mode_name="Wheel Speed Sensor Failed",
    injections=[
        # Auto-generated - may need tuning
        FaultInjection(
            fault_type=FaultType.SENSOR_DRIFT,
            magnitude=0.5,
        ),
    ],
    
    expected_patterns={
        # From knowledge: ['wheel_speed=erratic']
    },
    severity_range=(0.1, 0.9),
    n_variations=50,
))


