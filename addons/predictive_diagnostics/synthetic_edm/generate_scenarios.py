"""Synthetic EDM scenario generator

Produces scenario JSON and time-series CSV logs.

Usage:
  python generate_scenarios.py --count 5 --outdir example_scenarios/

Dependencies: numpy, pandas
"""

import argparse
import json
import os
import random
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

# Baseline system parameters
BASELINE = {
    "motor_k": 0.1,  # torque per amp
    "dc_voltage": 350.0,
    "coolant_temp_nominal": 50.0,
}

FAILURES = [
    "cooling_pump_failure",
    "phase_fet_short",
    "bms_cell_imbalance",
    "can_message_loss",
]


def make_baseline_log(duration_s=600, sample_hz=1, torque_request_profile=None, seed=None):
    rng = np.random.default_rng(seed)
    n = int(duration_s * sample_hz)
    t0 = datetime.utcnow()
    timestamps = [ (t0 + timedelta(seconds=i/sample_hz)).isoformat() for i in range(n) ]

    if torque_request_profile is None:
        # simple ramp then plateau
        torque_request = np.clip(np.concatenate([np.linspace(0,200, n//3), np.ones(n - n//3)*200]), 0, 200)
    else:
        torque_request = torque_request_profile

    # baseline currents and torque
    Ia = torque_request / BASELINE["motor_k"] / 3 + rng.normal(0, 5, n)
    Ib = Ia + rng.normal(0, 2, n)
    Ic = Ia + rng.normal(0, 2, n)
    Vdc = np.ones(n) * BASELINE["dc_voltage"] + rng.normal(0, 1.0, n)
    coolant_temp = np.ones(n) * BASELINE["coolant_temp_nominal"] + rng.normal(0, 0.5, n)
    measured_torque = torque_request + rng.normal(0, 5, n)

    # pump baseline (A) and per-cell voltages (4 cells)
    pump_motor_current = np.ones(n) * 2.0 + rng.normal(0, 0.1, n)  # nominal pump current
    # per-cell voltages - distribute Vdc approximately across 4 cells
    cell_v = np.vstack([(Vdc/4.0) + rng.normal(0, 0.05, n) for _ in range(4)])

    df = pd.DataFrame({
        "timestamp": timestamps,
        "torque_request": torque_request,
        "measured_torque": measured_torque,
        "Ia": Ia,
        "Ib": Ib,
        "Ic": Ic,
        "Vdc": Vdc,
        "coolant_temp": coolant_temp,
        "pump_motor_current": pump_motor_current,
        "inverter_status": ["OK"]*n,
        "BMS_status": ["OK"]*n,
        "CAN_drops": np.zeros(n, dtype=int),
    })

    # add cell voltages
    for i in range(4):
        df[f"cell_voltage_{i+1}"] = cell_v[i]

    return df


def inject_cooling_pump_failure(df, severity=1.0, start_idx=None):
    n = len(df)
    if start_idx is None:
        start_idx = n//3
    # coolant temp rises gradually
    for i in range(start_idx, n):
        df.loc[i:, "coolant_temp"] += (i - start_idx) * 0.1 * severity
    # pump current drops (pump failure) near start_idx
    df.loc[start_idx:, "pump_motor_current"] *= 0.05  # almost zero current (stalled)
    # at later time, inverter enters thermal derate
    derate_idx = min(n-1, start_idx + int(60))
    df.loc[derate_idx:, "inverter_status"] = "THERMAL_DERATE"
    # measured torque reduced after derate
    df.loc[derate_idx:, "measured_torque"] = df.loc[derate_idx:, "torque_request"] * 0.6
    return df


def inject_phase_fet_short(df, start_idx=None):
    n = len(df)
    if start_idx is None:
        start_idx = n//2
    # Large spike in Ia, and DC bus ripple
    df.loc[start_idx:start_idx+3, "Ia"] *= 10
    df.loc[start_idx:start_idx+10, "Vdc"] -= 50
    df.loc[start_idx:start_idx+3, "inverter_status"] = "OVERCURRENT_FAULT"
    return df


def inject_bms_cell_imbalance(df, start_idx=None):
    n = len(df)
    if start_idx is None:
        start_idx = n//4
    # pack voltage sags gradually under load
    df.loc[start_idx:, "Vdc"] -= np.linspace(0, 30, n - start_idx)
    df.loc[start_idx:, "BMS_status"] = "DERATE"
    # torque limited
    df.loc[start_idx:, "measured_torque"] = df.loc[start_idx:, "torque_request"] * 0.7
    # produce cell-specific drop on one cell
    cell_idx = 1
    df.loc[start_idx:, f"cell_voltage_{cell_idx+1}"] -= np.linspace(0, 0.5, n - start_idx)
    return df


def inject_can_message_loss(df, start_idx=None):
    n = len(df)
    if start_idx is None:
        start_idx = n//2
    # simulate CAN drops
    drop_idxs = range(start_idx, min(n, start_idx+20))
    df.loc[drop_idxs, "CAN_drops"] = np.arange(1, len(drop_idxs)+1)
    df.loc[drop_idxs, "measured_torque"] = df.loc[drop_idxs, "measured_torque"] * 0.5
    df.loc[drop_idxs, "inverter_status"] = "OK"
    return df


def generate_scenario(scenario_id, failure_type, outdir, seed=None, duration_s=600):
    rng = random.Random(seed)
    df = make_baseline_log(duration_s=duration_s, sample_hz=1, seed=seed)

    if failure_type == "cooling_pump_failure":
        df = inject_cooling_pump_failure(df)
        gt = ["Cooling pump failure"]
    elif failure_type == "phase_fet_short":
        df = inject_phase_fet_short(df)
        gt = ["Phase FET short (phase A)"]
    elif failure_type == "bms_cell_imbalance":
        df = inject_bms_cell_imbalance(df)
        gt = ["BMS cell imbalance / high internal resistance cell"]
    elif failure_type == "can_message_loss":
        df = inject_can_message_loss(df)
        gt = ["CAN message loss / gateway fault"]
    else:
        gt = ["No fault"]

    scenario = {
        "scenario_id": scenario_id,
        "title": f"Synthetic: {failure_type}",
        "difficulty": "easy",
        "textual_symptom_summary": "Autogenerated. See CSV time series for details.",
        "ground_truth_root_causes": gt,
        "recommended_fix": "See FMEA: replace/repair affected component",
        "metadata": {"random_seed": seed}
    }

    os.makedirs(outdir, exist_ok=True)
    json_path = os.path.join(outdir, f"{scenario_id}.json")
    csv_path = os.path.join(outdir, f"{scenario_id}_log.csv")
    with open(json_path, "w") as f:
        json.dump(scenario, f, indent=2)
    df.to_csv(csv_path, index=False)
    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=4)
    parser.add_argument("--outdir", type=str, default="example_scenarios")
    args = parser.parse_args()

    random.seed(0)
    failures = [f for f in FAILURES]
    for i in range(args.count):
        failure = failures[i % len(failures)]
        scenario_id = f"EDM_{i+1:03d}"
        generate_scenario(scenario_id, failure, args.outdir, seed=42 + i)
        print(f"Wrote {scenario_id} with failure {failure}")


if __name__ == "__main__":
    main()
