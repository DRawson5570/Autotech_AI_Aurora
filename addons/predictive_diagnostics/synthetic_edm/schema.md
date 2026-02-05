# Scenario Schema & Dataset Specification

## Scenario JSON
Each scenario is a JSON object with these fields:
- `scenario_id` (str)
- `title` (str)
- `difficulty` ("easy"|"medium"|"hard")
- `system_doc` (object) — structured minimal doc (component list, interface summary)
- `observability` (object) — which sensors present / missing
- `textual_symptom_summary` (str)
- `ground_truth_root_causes` (list of str)
- `recommended_fix` (str)
- `metadata` (object)

Example:
```
{
  "scenario_id": "EDM_001",
  "title": "Inverter thermal derate due to pump failure",
  "difficulty": "easy",
  "textual_symptom_summary": "High torque request, measured torque limited; inverter reports THERMAL_DERATE; coolant_temp rising",
  "ground_truth_root_causes": ["Cooling pump failure"],
  "recommended_fix": "Replace cooling pump and verify flow"
}
```

## Time-series CSV
Columns (timestamp, sec), numeric series typically sampled at 1Hz or higher:
- `timestamp` (ISO string) or seconds
- `torque_request` (Nm)
- `measured_torque` (Nm)
- `Ia`, `Ib`, `Ic` (A)
- `Vdc` (V)
- `coolant_temp` (C)
- `inverter_status` (string tags: OK, THERMAL_DERATE, FAULT)
- `BMS_status` (string tags: OK, DERATE, FAULT)
- `CAN_drops` (int)

## Failure Mode Template
Each generator implements a failure template that modifies baseline signals and injects signature anomalies (spikes, gradual drift, saturations).

## Metadata & Reproducibility
- Each scenario should include a `random_seed` in metadata
- `difficulty` controls multiplicity of faults, noise, and missing sensors


---
Notes: The schema is intentionally minimal and extensible. Let me know what additional fields you'd like (images, waveform attachments, binary traces).