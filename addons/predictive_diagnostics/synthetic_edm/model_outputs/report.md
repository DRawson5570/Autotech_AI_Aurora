# EDM Diagnosis Experiment Report

**Total scenarios:** 10
**Top-1 accuracy:** 80.00%
**Top-3 accuracy:** 80.00%

## Per-scenario details

### EDM_001 — Synthetic: cooling_pump_failure
- Ground truth: ['Cooling pump failure']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - Cooling pump failure (prob: 0.65) — ['high coolant temp (8029\u202fK)', 'inverter THERMAL_DERATE', 'elevated Ia_max (681\u202fA)']
- Interaction trace:
  - Round 1: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_temp_inlet_history', 'coolant_temp_outlet_history'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_temp_inlet_history': 'NOT_AVAILABLE', 'coolant_temp_outlet_history': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_temp_inlet_history', 'coolant_temp_outlet_history', 'pump_motor_temp'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_temp_inlet_history': 'NOT_AVAILABLE', 'coolant_temp_outlet_history': 'NOT_AVAILABLE', 'pump_motor_temp': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_temp_inlet_history', 'coolant_temp_outlet_history', 'pump_motor_temp'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_temp_inlet_history': 'NOT_AVAILABLE', 'coolant_temp_outlet_history': 'NOT_AVAILABLE', 'pump_motor_temp': 'NOT_AVAILABLE'}

### EDM_002 — Synthetic: phase_fet_short
- Ground truth: ['Phase FET short (phase A)']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - Phase FET short (phase A) (prob: 0.6) — ['OVERCURRENT_FAULT in inverter_status_unique', 'Ia_max far above median', 'Vdc_min low relative to Vdc_max']
- Interaction trace:
  - Round 1: requested_measurements=['Ia_max_last_60s_mean', 'Ia_history', 'Vdc_history'], provided={'Ia_max_last_60s_mean': 'NOT_AVAILABLE', 'Ia_history': 'NOT_AVAILABLE', 'Vdc_history': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['Ia_max_last_60s_mean', 'Ia_history', 'Vdc_history'], provided={'Ia_max_last_60s_mean': 'NOT_AVAILABLE', 'Ia_history': 'NOT_AVAILABLE', 'Vdc_history': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['Ia_max_last_60s_mean', 'Ia_history', 'Vdc_history', 'inverter_status_history'], provided={'Ia_max_last_60s_mean': 'NOT_AVAILABLE', 'Ia_history': 'NOT_AVAILABLE', 'Vdc_history': 'NOT_AVAILABLE', 'inverter_status_history': 'NOT_AVAILABLE'}

### EDM_003 — Synthetic: bms_cell_imbalance
- Ground truth: ['BMS cell imbalance / high internal resistance cell']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - BMS cell imbalance / high internal resistance cell (prob: 0.6) — ['high Ia_max (681\u202fA)', 'low Vdc_min (318\u202fV)', 'cell voltage data missing']
- Interaction trace:
  - Round 1: requested_measurements=['cell_voltage_1_history', 'cell_voltage_2_history', 'cell_voltage_3_history', 'cell_voltage_1_last_60s_mean', 'cell_voltage_2_last_60s_mean', 'cell_voltage_3_last_60s_mean'], provided={'cell_voltage_1_history': 'NOT_AVAILABLE', 'cell_voltage_2_history': 'NOT_AVAILABLE', 'cell_voltage_3_history': 'NOT_AVAILABLE', 'cell_voltage_1_last_60s_mean': 'NOT_AVAILABLE', 'cell_voltage_2_last_60s_mean': 'NOT_AVAILABLE', 'cell_voltage_3_last_60s_mean': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=[], provided={}

### EDM_004 — Synthetic: can_message_loss
- Ground truth: ['CAN message loss / gateway fault']
- Top-1 correct: False
- Top-3 correct: False
- Top predictions:
  - CAN gateway fault causing message loss (prob: 0.9) — ['210 CAN drops recorded', 'inverter status OK', 'no voltage/temperature anomalies']
- Interaction trace:
  - Round 1: requested_measurements=['gateway_fault_code', 'CAN_bus_error_count_last_60s'], provided={'gateway_fault_code': 'NOT_AVAILABLE', 'CAN_bus_error_count_last_60s': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['CAN_error_rate_last_60s', 'gateway_health_status'], provided={'CAN_error_rate_last_60s': 'NOT_AVAILABLE', 'gateway_health_status': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['CAN_drops_total', 'inverter_status_unique'], provided={'CAN_drops_total': 210, 'inverter_status_unique': ['OK']}

### EDM_005 — Synthetic: cooling_pump_failure
- Ground truth: ['Cooling pump failure']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - Cooling pump failure (prob: 0.85) — ['high coolant_temp_max (~8k)', 'inverter THERMAL_DERATE', 'Ia_max elevated']
- Interaction trace:
  - Round 1: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_inlet_temp_history'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_inlet_temp_history': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['coolant_temp_last_60s_mean', 'pump_motor_current_last_60s_mean'], provided={'coolant_temp_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_temp_last_60s_mean'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_temp_last_60s_mean': 'NOT_AVAILABLE'}

### EDM_006 — Synthetic: phase_fet_short
- Ground truth: ['Phase FET short (phase A)']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - Phase FET short (phase A) (prob: 0.75) — ['Ia_max 6667A & inverter overcurrent fault', 'Vdc_min near lower limit', 'missing current waveform reduces certainty']
- Interaction trace:
  - Round 1: requested_measurements=['phase_A_current_history'], provided={'phase_A_current_history': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['phase_A_fet_temperature', 'phase_A_gate_drive_voltage', 'phase_A_current_waveform', 'phase_B_current_history', 'phase_C_current_history'], provided={'phase_A_fet_temperature': 'NOT_AVAILABLE', 'phase_A_gate_drive_voltage': 'NOT_AVAILABLE', 'phase_A_current_waveform': 'NOT_AVAILABLE', 'phase_B_current_history': 'NOT_AVAILABLE', 'phase_C_current_history': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['phase_A_current_waveform', 'phase_A_fet_temperature', 'phase_A_gate_drive_voltage', 'phase_A_fet_current', 'phase_B_current_history', 'phase_C_current_history'], provided={'phase_A_current_waveform': 'NOT_AVAILABLE', 'phase_A_fet_temperature': 'NOT_AVAILABLE', 'phase_A_gate_drive_voltage': 'NOT_AVAILABLE', 'phase_A_fet_current': 'NOT_AVAILABLE', 'phase_B_current_history': 'NOT_AVAILABLE', 'phase_C_current_history': 'NOT_AVAILABLE'}

### EDM_007 — Synthetic: bms_cell_imbalance
- Ground truth: ['BMS cell imbalance / high internal resistance cell']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - BMS cell imbalance / high internal resistance cell (prob: 0.68) — ['high Ia, low Vdc_min', 'normal coolant temp', 'inverter status OK']
- Interaction trace:
  - Round 1: requested_measurements=['cell_voltage_history', 'cell_internal_resistance_last_60s_mean'], provided={'cell_voltage_history': 'NOT_AVAILABLE', 'cell_internal_resistance_last_60s_mean': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['cell_voltage_history', 'cell_internal_resistance_last_60s_mean'], provided={'cell_voltage_history': 'NOT_AVAILABLE', 'cell_internal_resistance_last_60s_mean': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['cell_voltage_1_history', 'cell_voltage_1_last_60s_mean', 'cell_voltage_2_history', 'cell_voltage_2_last_60s_mean', 'Vdc_min_last_60s_mean', 'Vdc_max_last_60s_mean'], provided={'cell_voltage_1_history': 'NOT_AVAILABLE', 'cell_voltage_1_last_60s_mean': 'NOT_AVAILABLE', 'cell_voltage_2_history': 'NOT_AVAILABLE', 'cell_voltage_2_last_60s_mean': 'NOT_AVAILABLE', 'Vdc_min_last_60s_mean': 'NOT_AVAILABLE', 'Vdc_max_last_60s_mean': 'NOT_AVAILABLE'}

### EDM_008 — Synthetic: can_message_loss
- Ground truth: ['CAN message loss / gateway fault']
- Top-1 correct: False
- Top-3 correct: False
- Top predictions:
  - CAN gateway fault causing message loss (prob: 0.82) — ['high CAN_drops_total (210)', 'inverter and power metrics normal', 'root‑cause list includes CAN fault']
- Interaction trace:
  - Round 1: requested_measurements=['CAN_drops_total'], provided={'CAN_drops_total': 210}
  - Round 2: requested_measurements=['CAN_error_frames', 'CAN_bus_error_counters'], provided={'CAN_error_frames': 'NOT_AVAILABLE', 'CAN_bus_error_counters': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['CAN_error_frames_last_60s', 'CAN_bus_error_counters_last_60s', 'CAN_drops_last_60s_mean', 'gateway_health_status'], provided={'CAN_error_frames_last_60s': 'NOT_AVAILABLE', 'CAN_bus_error_counters_last_60s': 'NOT_AVAILABLE', 'CAN_drops_last_60s_mean': 'NOT_AVAILABLE', 'gateway_health_status': 'NOT_AVAILABLE'}

### EDM_009 — Synthetic: cooling_pump_failure
- Ground truth: ['Cooling pump failure']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - Cooling pump failure (prob: 0.85) — ['inverter THERMAL_DERATE', 'coolant_temp_max high', 'Vdc_min low', 'Ia_max high']
- Interaction trace:
  - Round 1: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_temp_history'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_temp_history': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_flow_rate', 'pump_motor_temperature'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_flow_rate': 'NOT_AVAILABLE', 'pump_motor_temperature': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['pump_motor_current_last_60s_mean', 'pump_motor_current_history', 'coolant_flow_rate', 'pump_motor_temperature'], provided={'pump_motor_current_last_60s_mean': 'NOT_AVAILABLE', 'pump_motor_current_history': 'NOT_AVAILABLE', 'coolant_flow_rate': 'NOT_AVAILABLE', 'pump_motor_temperature': 'NOT_AVAILABLE'}

### EDM_010 — Synthetic: phase_fet_short
- Ground truth: ['Phase FET short (phase A)']
- Top-1 correct: True
- Top-3 correct: True
- Top predictions:
  - Phase FET short (phase A) (prob: 0.7) — ['inverter_status shows OVERCURRENT_FAULT', 'Ia_max unusually high (6783\u202fA)', 'Vdc_min low (298\u202fV)']
- Interaction trace:
  - Round 1: requested_measurements=['Ia_history', 'Vdc_min_last_60s_mean'], provided={'Ia_history': 'NOT_AVAILABLE', 'Vdc_min_last_60s_mean': 'NOT_AVAILABLE'}
  - Round 2: requested_measurements=['Ia_max_last_60s_mean', 'Vdc_min_last_60s_mean', 'inverter_status_last_60s'], provided={'Ia_max_last_60s_mean': 'NOT_AVAILABLE', 'Vdc_min_last_60s_mean': 'NOT_AVAILABLE', 'inverter_status_last_60s': 'NOT_AVAILABLE'}
  - Round 3: requested_measurements=['Ia_max_history', 'Vdc_min_history', 'inverter_status_last_60s'], provided={'Ia_max_history': 'NOT_AVAILABLE', 'Vdc_min_history': 'NOT_AVAILABLE', 'inverter_status_last_60s': 'NOT_AVAILABLE'}
