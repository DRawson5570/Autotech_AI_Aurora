"""Simple evaluation utilities

Expect model outputs in JSON files alongside scenarios.
Model output format (JSON):
{
  "scenario_id": "EDM_001",
  "predictions": [
    {"hypothesis": "Cooling pump failure","prob": 0.75},
    {"hypothesis": "Sensor bias","prob": 0.15},
  ]
}

This script computes Top-1 and Top-3 accuracy against scenario ground truth.
"""

import json
import os
import sys


def score_prediction(scenario_json, model_out_json):
    with open(scenario_json) as f:
        scenario = json.load(f)
    with open(model_out_json) as f:
        out = json.load(f)

    # Normalize output shape: accept list of predictions or dict
    if isinstance(out, list):
        out = {"predictions": out}
    if not isinstance(out, dict):
        raise ValueError("Model output JSON must be an object or array of predictions")

    gt_set = set([g.lower() for g in scenario.get("ground_truth_root_causes", [])])
    raw_preds = out.get("predictions", [])
    preds = []
    for p in raw_preds:
        if isinstance(p, dict) and "hypothesis" in p:
            preds.append(p["hypothesis"].lower())
        elif isinstance(p, str):
            preds.append(p.lower())

    top1 = preds[0] if preds else None
    top3 = preds[:3]

    score = {
        "scenario_id": scenario["scenario_id"],
        "top1_correct": top1 in gt_set,
        "top3_correct": any(p in gt_set for p in top3),
    }
    return score


def score_directory(scenarios_dir, outputs_dir):
    """Score all scenarios in a directory and return a summary dict"""
    import glob
    scenarios = sorted(glob.glob(os.path.join(scenarios_dir, "*.json")))

    results = []
    counts = {"top1_correct": 0, "top3_correct": 0, "total": 0}
    for s in scenarios:
        stem = os.path.splitext(os.path.basename(s))[0]
        candidate = os.path.join(outputs_dir, f"model_output_{stem}.json")
        if not os.path.exists(candidate):
            print(f"Missing model output for {stem}: {candidate}")
            continue
        r = score_prediction(s, candidate)
        counts["total"] += 1
        if r["top1_correct"]:
            counts["top1_correct"] += 1
        if r["top3_correct"]:
            counts["top3_correct"] += 1
        results.append(r)

    summary = {
        "total": counts["total"],
        "top1_accuracy": counts["top1_correct"] / counts["total"] if counts["total"] else 0.0,
        "top3_accuracy": counts["top3_correct"] / counts["total"] if counts["total"] else 0.0,
        "per_scenario": results,
    }
    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Evaluate model outputs against scenarios')
    parser.add_argument('--dir', nargs=2, metavar=('SCENARIOS_DIR','OUT_DIR'),
                        help='Score all scenarios in SCENARIOS_DIR using model outputs in OUT_DIR')
    parser.add_argument('scenario', nargs='?', help='Single scenario JSON file')
    parser.add_argument('model_output', nargs='?', help='Single model output JSON file')

    args = parser.parse_args()

    if args.dir:
        scenarios_dir, outputs_dir = args.dir
        import pprint
        pprint.pprint(score_directory(scenarios_dir, outputs_dir))
        return

    if args.scenario and args.model_output:
        print(score_prediction(args.scenario, args.model_output))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
