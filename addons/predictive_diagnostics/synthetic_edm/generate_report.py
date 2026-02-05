"""Generate a per-scenario diagnostic report from scenarios, model outputs, and traces.

Produces:
- JSON report: `model_outputs/report.json`
- Markdown report: `model_outputs/report.md`

Usage:
  python generate_report.py --scenarios synthetic_edm/example_scenarios --outputs synthetic_edm/model_outputs
"""
import argparse
import glob
import json
import os
from pathlib import Path


def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def summarize(scenarios_dir, outputs_dir):
    scenarios = sorted(glob.glob(os.path.join(scenarios_dir, "*.json")))
    report = {"total": 0, "top1_correct": 0, "top3_correct": 0, "scenarios": []}

    for s in scenarios:
        stem = os.path.splitext(os.path.basename(s))[0]
        scenario = load_json(s)
        outp = load_json(os.path.join(outputs_dir, f"model_output_{stem}.json"))
        trace = load_json(os.path.join(outputs_dir, f"model_trace_{stem}.json"))
        debug_raw = f"/tmp/ollama_raw_{os.path.basename(s)}.txt"
        debug_exists = os.path.exists(debug_raw)

        gt = [g.lower() for g in scenario.get("ground_truth_root_causes", [])]

        predictions = []
        top1_correct = False
        top3_correct = False
        if outp:
            preds = outp.get("predictions") if isinstance(outp, dict) else outp
            if isinstance(preds, list):
                for p in preds[:5]:
                    if isinstance(p, dict):
                        hypothesis = p.get("hypothesis")
                        prob = p.get("prob")
                        reason = p.get("reason")
                    else:
                        hypothesis = str(p)
                        prob = None
                        reason = []
                    predictions.append({"hypothesis": hypothesis, "prob": prob, "reason": reason})
                preds_lower = [ (p.get("hypothesis") if isinstance(p, dict) else str(p)).lower() for p in preds ]
                top1_correct = len(preds_lower) > 0 and preds_lower[0] in gt
                top3_correct = any(p in gt for p in preds_lower[:3])
        report["total"] += 1
        if top1_correct:
            report["top1_correct"] += 1
        if top3_correct:
            report["top3_correct"] += 1

        # trace details
        trace_steps = []
        if trace and isinstance(trace, dict) and trace.get('trace'):
            for step in trace.get('trace'):
                model_resp = step[0]
                meas = step[1]
                trace_steps.append({"model_resp": model_resp, "measurements": meas})

        report_entry = {
            "scenario_id": scenario.get("scenario_id"),
            "title": scenario.get("title"),
            "ground_truth": scenario.get("ground_truth_root_causes"),
            "top_predictions": predictions,
            "top1_correct": top1_correct,
            "top3_correct": top3_correct,
            "trace_steps": trace_steps,
            "debug_raw_exists": debug_exists,
            "model_output_path": os.path.join(outputs_dir, f"model_output_{stem}.json"),
            "trace_path": os.path.join(outputs_dir, f"model_trace_{stem}.json") if trace else None,
        }
        report["scenarios"].append(report_entry)

    # aggregate stats
    report_summary = {
        "total": report["total"],
        "top1_accuracy": report["top1_correct"] / report["total"] if report["total"] else 0.0,
        "top3_accuracy": report["top3_correct"] / report["total"] if report["total"] else 0.0,
    }
    return report, report_summary


def write_reports(report, summary, outputs_dir):
    os.makedirs(outputs_dir, exist_ok=True)
    json_path = os.path.join(outputs_dir, "report.json")
    md_path = os.path.join(outputs_dir, "report.md")
    with open(json_path, "w") as f:
        json.dump({"report": report, "summary": summary}, f, indent=2)

    # write a simple markdown
    lines = []
    lines.append(f"# EDM Diagnosis Experiment Report\n")
    lines.append(f"**Total scenarios:** {summary['total']}")
    lines.append(f"**Top-1 accuracy:** {summary['top1_accuracy']:.2%}")
    lines.append(f"**Top-3 accuracy:** {summary['top3_accuracy']:.2%}\n")

    lines.append("## Per-scenario details\n")
    for sc in report['scenarios']:
        lines.append(f"### {sc['scenario_id']} — {sc.get('title')}")
        lines.append(f"- Ground truth: {sc['ground_truth']}")
        lines.append(f"- Top-1 correct: {sc['top1_correct']}")
        lines.append(f"- Top-3 correct: {sc['top3_correct']}")
        lines.append(f"- Top predictions:")
        for p in sc['top_predictions']:
            lines.append(f"  - {p.get('hypothesis')} (prob: {p.get('prob')}) — {p.get('reason')}")
        if sc['trace_steps']:
            lines.append(f"- Interaction trace:")
            for i, t in enumerate(sc['trace_steps']):
                mr = t.get('model_resp', {})
                reqs = mr.get('requested_measurements') if isinstance(mr, dict) else []
                lines.append(f"  - Round {i+1}: requested_measurements={reqs}, provided={t.get('measurements')}")
        if sc['debug_raw_exists']:
            lines.append(f"- Raw parse debug file exists at /tmp/ollama_raw_{sc['scenario_id']}.json (inspect for parsing failures)")
        lines.append('')

    with open(md_path, 'w') as f:
        f.write('\n'.join(lines))

    return json_path, md_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenarios', required=True)
    parser.add_argument('--outputs', required=True)
    args = parser.parse_args()

    report, summary = summarize(args.scenarios, args.outputs)
    json_path, md_path = write_reports(report, summary, args.outputs)
    print(f"Wrote report JSON: {json_path}")
    print(f"Wrote report MD: {md_path}")


if __name__ == '__main__':
    main()
