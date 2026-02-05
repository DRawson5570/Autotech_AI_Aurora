"""Analyze failures: for scenarios where the model missed the ground truth, inspect logs and model reasoning
and produce a short natural-language analysis with suggested diagnostic tests.

Usage:
  python analyze_failures.py --scenarios synthetic_edm/example_scenarios --outputs synthetic_edm/model_outputs

Produces: synthetic_edm/model_outputs/failure_analysis.md
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


def check_signatures(df):
    # returns signatures found in a dict
    sig = {}
    try:
        if 'inverter_status' in df.columns:
            sig['thermal_derate'] = df['inverter_status'].astype(str).str.contains('THERMAL_DERATE').any()
            sig['overcurrent'] = df['inverter_status'].astype(str).str.contains('OVERCURRENT').any()
        if 'coolant_temp' in df.columns:
            sig['coolant_temp_max'] = float(df['coolant_temp'].max())
            sig['coolant_temp_trend'] = float(df['coolant_temp'].iloc[-1] - df['coolant_temp'].iloc[0])
        if 'Ia' in df.columns:
            ia = df['Ia'].abs()
            sig['Ia_max'] = float(ia.max())
            sig['Ia_median'] = float(ia.median())
            sig['Ia_spike'] = ia.max() > ia.median() * 5 if ia.median() > 0 else False
        if 'Vdc' in df.columns:
            sig['Vdc_min'] = float(df['Vdc'].min())
            sig['Vdc_delta'] = float(df['Vdc'].max() - df['Vdc'].min())
        if 'CAN_drops' in df.columns:
            sig['CAN_drops_total'] = int(df['CAN_drops'].sum())
    except Exception:
        pass
    return sig


def explain_missed(scenario, outp, trace, df):
    gt = [g.lower() for g in scenario.get('ground_truth_root_causes', [])]
    preds = []
    if outp:
        p = outp.get('predictions') if isinstance(outp, dict) else outp
        if isinstance(p, list):
            preds = [( (x.get('hypothesis') if isinstance(x, dict) else str(x)), (x.get('prob') if isinstance(x, dict) else None), (x.get('reason') if isinstance(x, dict) else None) ) for x in p]
    sig = check_signatures(df) if df is not None else {}

    note_lines = []
    note_lines.append(f"Ground truth: {scenario.get('ground_truth_root_causes')}")
    note_lines.append(f"Model top predictions: {[p[0] for p in preds]} (reasons preserved when available)")

    # For known GT types, check if signature present
    gt_tag = gt[0] if gt else ''
    if 'cooling pump' in gt_tag or 'thermal' in gt_tag:
        # expect thermal_derate and coolant_temp rise
        if sig.get('thermal_derate') or sig.get('coolant_temp_max', 0) > 80 or sig.get('coolant_temp_trend',0) > 5:
            note_lines.append("Log signatures consistent with cooling/heat issue (thermal derate or high coolant temp present).")
            # Did model include cooling in any prediction?
            if not any('cool' in (p[0] or '').lower() or 'pump' in (p[0] or '').lower() for p in preds):
                note_lines.append("Model did NOT prioritize cooling/pump failure despite signature present — likely misattribution or over-weighting of alternate causes.")
            else:
                note_lines.append("Model considered cooling/pump failure.")
            note_lines.append("Suggested tests: measure pump current/flow, inlet/outlet coolant temps, radiator pressure.")
        else:
            note_lines.append("No clear thermal signature in logs; model may be right to be uncertain. Consider adding more detailed coolant measurements.")

    if 'phase fet' in gt_tag or 'phase' in gt_tag or 'fet' in gt_tag:
        if sig.get('Ia_spike') or sig.get('overcurrent') or sig.get('Vdc_delta',0) > 20:
            note_lines.append("Log signatures indicate a phase short / overcurrent (large Ia spike or inverter overcurrent).")
            if not any('fet' in (p[0] or '').lower() or 'overcurrent' in (p[0] or '').lower() or 'phase' in (p[0] or '').lower() for p in preds):
                note_lines.append("Model did NOT prioritize a phase FET short though signatures exist — it may have suggested related hardware faults instead.")
            else:
                note_lines.append("Model did consider a FET/phase short.")
            note_lines.append("Suggested tests: capture Phase-A Vds, gate-drive waveform, and short-circuit current tracing.")
        else:
            note_lines.append("No strong phase short signature — check sampling resolution and look for short spikes in raw traces.")

    if 'bms' in gt_tag or 'cell' in gt_tag:
        if sig.get('Vdc_delta',0) > 15 or sig.get('Ia_max',0) > 1000 or 'DERATE' in str(scenario.get('textual_symptom_summary','')).upper() or 'DERATE' in ''.join([str(x) for x in scenario.get('textual_symptom_summary','')]):
            note_lines.append("Symptoms point to a pack voltage sag or BMS derate.")
            if not any('bms' in (p[0] or '').lower() or 'cell' in (p[0] or '').lower() for p in preds):
                note_lines.append("Model did NOT emphasize BMS/cell imbalance despite pack voltage sag — may need to be prompted to consider pack-level issues.")
            else:
                note_lines.append("Model considered BMS/cell imbalance.")
            note_lines.append("Suggested tests: measure per-cell voltages and internal resistances, and check BMS logs for balancing/derate events.")
        else:
            note_lines.append("No clear pack-level voltage sag detected; consider longer duration traces or load tests.")

    if 'can' in gt_tag or 'gateway' in gt_tag:
        if sig.get('CAN_drops_total',0) > 0:
            note_lines.append("Significant CAN drops observed in logs — consistent with CAN/gateway fault.")
            if not any('can' in (p[0] or '').lower() or 'gateway' in (p[0] or '').lower() for p in preds):
                note_lines.append("Model did NOT list CAN/gateway faults — it may have favored component faults with similar secondary symptoms.")
            else:
                note_lines.append("Model considered a CAN/gateway issue.")
            note_lines.append("Suggested tests: read gateway error counters, test bus voltages, try loopback diagnostics.")
        else:
            note_lines.append("No CAN drops in summary; consider searching raw log for intermittent message gaps.")

    # Generic guidance: compare model reasons to signature list
    # If model gave reasons, indicate whether they match signatures
    for hyp, prob, reason in preds[:3]:
        rtxt = ' '.join(reason) if reason else ''
        matches = []
        if 'thermal' in rtxt.lower() or 'coolant' in rtxt.lower() or 'temp' in rtxt.lower():
            matches.append('thermal')
        if 'overcurrent' in rtxt.lower() or 'ia' in rtxt.lower() or 'spike' in rtxt.lower() or 'fet' in rtxt.lower():
            matches.append('phase/overcurrent')
        if 'vdc' in rtxt.lower() or 'pack' in rtxt.lower() or 'bms' in rtxt.lower():
            matches.append('bms/pack')
        if 'can' in rtxt.lower() or 'gateway' in rtxt.lower():
            matches.append('can')
        if matches:
            note_lines.append(f"Model's hypothesis '{hyp}' cites signals: {matches} (reason snippet: {rtxt[:160]})")

    return '\n'.join(note_lines)


def analyze(scenarios_dir, outputs_dir):
    scenarios = sorted(glob.glob(os.path.join(scenarios_dir, "*.json")))
    analyses = []
    for s in scenarios:
        stem = os.path.splitext(os.path.basename(s))[0]
        scenario = load_json(s)
        outp = load_json(os.path.join(outputs_dir, f"model_output_{stem}.json"))
        trace = load_json(os.path.join(outputs_dir, f"model_trace_{stem}.json"))
        csv_path = os.path.join(scenarios_dir, f"{stem}_log.csv")
        try:
            import pandas as pd
            df = pd.read_csv(csv_path) if os.path.exists(csv_path) else None
        except Exception:
            df = None

        # determine correctness
        gt = [g.lower() for g in scenario.get('ground_truth_root_causes', [])]
        preds = []
        if outp:
            p = outp.get('predictions') if isinstance(outp, dict) else outp
            if isinstance(p, list):
                preds = [( (x.get('hypothesis') if isinstance(x, dict) else str(x)).lower(), x.get('prob') if isinstance(x, dict) else None ) for x in p]
        top1 = preds[0][0] if preds else None
        top3 = [p[0] for p in preds[:3]]
        correct = top1 in gt if top1 else False
        if not correct:
            analysis = explain_missed(scenario, outp, trace, df)
            analyses.append({"scenario_id": scenario.get('scenario_id'), "analysis": analysis})
    return analyses


def write_md(analyses, outputs_dir):
    lines = ["# Failure Mode Analysis\n"]
    for a in analyses:
        lines.append(f"## {a['scenario_id']}")
        lines.append(a['analysis'])
        lines.append('')
    out = os.path.join(outputs_dir, 'failure_analysis.md')
    with open(out, 'w') as f:
        f.write('\n'.join(lines))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenarios', required=True)
    parser.add_argument('--outputs', required=True)
    args = parser.parse_args()

    analyses = analyze(args.scenarios, args.outputs)
    out = write_md(analyses, args.outputs)
    print(f"Wrote failure analysis: {out}")

if __name__ == '__main__':
    main()
