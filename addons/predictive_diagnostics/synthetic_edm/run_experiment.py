"""Run an experiment over a directory of scenarios, using a model adapter, and score results.

Usage examples:
  # Generate outputs with the mock model and score
  python run_experiment.py --scenarios synthetic_edm/example_scenarios --outputs synthetic_edm/model_outputs --model mock

Options:
  --scenarios: directory with scenario JSON and *_log.csv
  --outputs: directory to write model output JSON
  --model: model backend (mock|none)
  --score: if set, run scoring after generating outputs
"""

import argparse
import glob
import json
import os
from pathlib import Path

from model_adapters import mock_predict, ollama_predict, interactive_ollama_predict
from evaluate import score_prediction, score_directory


def find_scenarios(scenarios_dir):
    scenarios = glob.glob(os.path.join(scenarios_dir, "*.json"))
    return sorted(scenarios)


def corresponding_csv(json_path):
    base = os.path.splitext(json_path)[0]
    # look for *_log.csv
    candidates = [f for f in glob.glob(base + "*log*.csv")]
    return candidates[0] if candidates else None


def run_mock_for_all(scenarios_dir, outputs_dir):
    os.makedirs(outputs_dir, exist_ok=True)
    scenarios = find_scenarios(scenarios_dir)
    for s in scenarios:
        csv = corresponding_csv(s)
        out = mock_predict(s, csv)
        out_path = os.path.join(outputs_dir, f"model_output_{Path(s).stem}.json")
        with open(out_path, "w") as f:
            json.dump(out, f, indent=2)
        print("Wrote model output:", out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", required=True)
    parser.add_argument("--outputs", required=True)
    parser.add_argument("--model", choices=["mock", "ollama", "none"], default="mock")
    parser.add_argument("--ollama-model", default="gpt-oss:20b", help="Model name for local Ollama instance (default: gpt-oss:20b)")
    parser.add_argument("--score", action="store_true")
    parser.add_argument("--interactive", action="store_true", help="Enable interactive measurement request loop (Ollama only)")
    args = parser.parse_args()

    if args.model == "mock":
        run_mock_for_all(args.scenarios, args.outputs)
    elif args.model == "ollama":
        os.makedirs(args.outputs, exist_ok=True)
        scenarios = find_scenarios(args.scenarios)
        for s in scenarios:
            csv = corresponding_csv(s)
            print(f"Querying Ollama for {s} (model={args.ollama_model})... interactive={args.interactive}")
            try:
                if args.interactive:
                    out, trace = interactive_ollama_predict(s, csv, model_name=args.ollama_model)
                    # save raw trace for debugging
                    trace_path = os.path.join(args.outputs, f"model_trace_{Path(s).stem}.json")
                    with open(trace_path, 'w') as tf:
                        json.dump({"trace": trace}, tf, indent=2)
                else:
                    out = ollama_predict(s, csv, model_name=args.ollama_model)
            except Exception as e:
                print(f"Ollama call failed for {s}: {e}; falling back to mock_predict")
                out = mock_predict(s, csv)
            out_path = os.path.join(args.outputs, f"model_output_{Path(s).stem}.json")
            with open(out_path, "w") as f:
                json.dump(out, f, indent=2)
            print("Wrote model output:", out_path)
    else:
        print("model=none selected: exported prompts for manual use (not implemented)")

    if args.score:
        print("Scoring outputs...")
        score_directory(args.scenarios, args.outputs)


if __name__ == "__main__":
    main()
