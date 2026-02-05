"""Model adapter layer for experiment runner.

Provides pluggable adapters. Currently implemented:
- mock_predict: quick heuristic predictor (no external API)
- (placeholder) openai_predict: simple wrapper if you add OpenAI key & package
"""

import json
import os
import subprocess
import re
import numpy as np

try:
    import requests
except Exception:
    requests = None


def mock_predict(scenario_json_path, csv_path=None):
    """Produce a simple heuristic prediction based on CSV/inverter/BMS tags.

    Heuristics:
    - If inverter_status contains THERMAL_DERATE -> Cooling pump failure
    - If any Ia has a spike > 5x baseline -> Phase FET short
    - If BMS_status == DERATE or Vdc drops > 20V -> BMS cell imbalance
    - If CAN_drops > 0 -> CAN message loss

    Returns the structured JSON expected by evaluator.
    """
    import pandas as pd

    with open(scenario_json_path) as f:
        scenario = json.load(f)

    df = None
    try:
        if csv_path and os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
    except Exception:
        df = None

    preds = []

    # Check inverter_status
    if df is not None and 'inverter_status' in df.columns:
        if df['inverter_status'].astype(str).str.contains('THERMAL_DERATE').any():
            preds.append(("Cooling pump failure", 0.7, "Inverter reports THERMAL_DERATE in log"))

    # Check for large Ia spike
    if df is not None and 'Ia' in df.columns:
        ia = df['Ia'].abs()
        if len(ia) >= 10:
            baseline = ia.median()
            if ia.max() > baseline * 5 + 1e-6:
                preds.append(("Phase FET short (phase A)", 0.8, "Large spike in Ia observed"))

    # Check Vdc sag or BMS derate
    if df is not None and 'Vdc' in df.columns:
        if df['Vdc'].max() - df['Vdc'].min() > 20:
            preds.append(("BMS cell imbalance / high internal resistance cell", 0.6, "Significant Vdc sag detected"))
    if df is not None and 'BMS_status' in df.columns:
        if df['BMS_status'].astype(str).str.contains('DERATE').any():
            preds.append(("BMS cell imbalance / high internal resistance cell", 0.75, "BMS status DERATE in log"))

    # CAN drops
    if df is not None and 'CAN_drops' in df.columns:
        if (df['CAN_drops'] > 0).any():
            preds.append(("CAN message loss / gateway fault", 0.7, "CAN drop count observed in log"))

    # Fallback: generic "No fault" with low confidence
    if not preds:
        preds.append(("No fault identified", 0.2, "No clear signature in logs"))

    # Sort by confidence desc
    preds.sort(key=lambda x: x[1], reverse=True)

    predictions = []
    for hyp, prob, reason in preds:
        predictions.append({
            "hypothesis": hyp,
            "prob": float(prob),
            "reason": [reason],
            "tests": [],
            "mitigation": "See recommended fix in scenario and FMEA",
        })

    out = {
        "scenario_id": scenario.get('scenario_id'),
        "predictions": predictions,
        "explanation": "Mock heuristic predictions; replace with real model adapter for experiments",
    }
    return out


def _summarize_csv(csv_path):
    """Return a small summary dict of key signals to keep prompts compact."""
    import pandas as pd
    if not csv_path or not os.path.exists(csv_path):
        return {}
    try:
        df = pd.read_csv(csv_path)
    except Exception:
        return {}
    summary = {}
    if 'coolant_temp' in df.columns:
        summary['coolant_temp_max'] = float(df['coolant_temp'].max())
        summary['coolant_temp_last'] = float(df['coolant_temp'].iloc[-1])
    if 'inverter_status' in df.columns:
        summary['inverter_status_unique'] = list(df['inverter_status'].unique())
    if 'Ia' in df.columns:
        summary['Ia_max'] = float(df['Ia'].abs().max())
        summary['Ia_median'] = float(df['Ia'].abs().median())
    if 'Vdc' in df.columns:
        summary['Vdc_min'] = float(df['Vdc'].min())
        summary['Vdc_max'] = float(df['Vdc'].max())
    if 'CAN_drops' in df.columns:
        summary['CAN_drops_total'] = int(df['CAN_drops'].sum())
    return summary


def robust_parse_json(text):
    """Attempt to extract and repair JSON from messy model output text.

    Tries multiple strategies in order:
    1. Direct json.loads on the full text.
    2. Remove markdown fences and search for balanced { ... } or [ ... ] substrings.
    3. For each candidate, try json.loads, then progressively apply repairs:
       - remove trailing commas
       - replace single quotes with double quotes
       - quote unquoted keys
       - replace Python booleans/null with JSON literals
       - strip comments (// and /* */)
       - fallback to ast.literal_eval for Python-like dicts
    Raises ValueError with diagnostic info if parsing fails.
    """
    import ast

    # quick direct attempt
    try:
        return json.loads(text)
    except Exception:
        pass

    # strip code fences and common prefixes
    s = re.sub(r'```(?:json)?\n', '\n', text)
    s = s.replace('```', '')
    # remove leading lines like 'Answer:' or 'OUTPUT:'
    s = re.sub(r'^[^\{\[]*', '', s, count=1)

    # find candidate JSON substrings by scanning for balanced braces/brackets
    candidates = []
    for i, ch in enumerate(s):
        if ch not in '{[':
            continue
        stack = []
        in_str = False
        esc = False
        for j in range(i, len(s)):
            c = s[j]
            if c == '\\' and not esc:
                esc = True
                continue
            if c == '"' and not esc:
                in_str = not in_str
            if not in_str:
                if c in '{[':
                    stack.append(c)
                elif c in '}]':
                    if not stack:
                        break
                    open_c = stack.pop()
                    # basic match check
                    if (open_c == '{' and c != '}') or (open_c == '[' and c != ']'):
                        # mismatch, but continue
                        pass
                    if not stack:
                        candidate = s[i:j+1]
                        candidates.append(candidate)
                        break
            if esc:
                esc = False

    # helper repairs
    def try_load(cand):
        try:
            return json.loads(cand)
        except Exception:
            return None

    def repair_trailing_commas(cand):
        cand2 = re.sub(r',\s*(?=[}\]])', '', cand)
        return cand2

    def repair_single_quotes(cand):
        # naive replacement, but try after other repairs
        return cand.replace("'", '"')

    def quote_unquoted_keys(cand):
        # Add quotes around unquoted keys (very heuristic)
        cand2 = re.sub(r'([\{,\s])(\w[\w\d_]*)\s*:', r'\1"\2":', cand)
        return cand2

    def remove_comments(cand):
        cand2 = re.sub(r'//.*?$','', cand, flags=re.MULTILINE)
        cand2 = re.sub(r'/\*.*?\*/','', cand2, flags=re.DOTALL)
        return cand2

    def fix_python_literals(cand):
        cand2 = re.sub(r'\bTrue\b', 'true', cand)
        cand2 = re.sub(r'\bFalse\b', 'false', cand2)
        cand2 = re.sub(r'\bNone\b', 'null', cand2)
        return cand2

    def quote_unquoted_string_values(cand):
        # naive: quote bareword values that appear after a colon and are not numbers, booleans, null, objects, arrays, or quoted
        def repl(match):
            prefix, val, suffix = match.group(1), match.group(2), match.group(3)
            # if looks like number, do not quote
            if re.match(r'^-?\d+(?:\.\d+)?$', val):
                return prefix + val + suffix
            if val.lower() in ('true', 'false', 'null'):
                return prefix + val + suffix
            # otherwise, quote
            return f"{prefix}\"{val}\"{suffix}"
        cand2 = re.sub(r'(:\s*)([A-Za-z_][A-Za-z0-9_\-]*)(\s*[,}\]])', repl, cand)
        return cand2

    # prefer larger / object-like candidates (likely outer dict); sort candidates accordingly
    candidates = sorted(candidates, key=lambda c: (-len(c), 0 if c.lstrip().startswith('{') else 1, 0 if 'scenario_id' in c else 1))

    # try candidates with strategy sequence
    for cand in candidates:
        attempts = []
        # try raw
        parsed = try_load(cand)
        attempts.append(('raw', parsed is not None))
        if parsed is not None:
            return parsed

        # strip comments, trailing commas, then try
        t = remove_comments(cand)
        t2 = repair_trailing_commas(t)
        parsed = try_load(t2)
        attempts.append(('comments+trailing', parsed is not None))
        if parsed is not None:
            return parsed

        # fix single quotes
        t3 = repair_single_quotes(t2)
        parsed = try_load(t3)
        attempts.append(('single_quotes', parsed is not None))
        if parsed is not None:
            return parsed

        # quote unquoted keys
        t4 = quote_unquoted_keys(t3)
        parsed = try_load(t4)
        attempts.append(('quote_keys', parsed is not None))
        if parsed is not None:
            return parsed

        # quote unquoted string values (turn: scenario_id: EDM_003 -> "scenario_id": "EDM_003")
        t4b = quote_unquoted_string_values(t4)
        parsed = try_load(t4b)
        attempts.append(('quote_values', parsed is not None))
        if parsed is not None:
            return parsed

        # fix python literals
        t5 = fix_python_literals(t4b)
        parsed = try_load(t5)
        attempts.append(('py_literals', parsed is not None))
        if parsed is not None:
            return parsed

        # last resort: ast.literal_eval
        try:
            obj = ast.literal_eval(cand)
            # convert to JSON via dumps/loads to ensure types
            j = json.loads(json.dumps(obj))
            return j
        except Exception:
            attempts.append(('ast_literal_eval', False))

    # If nothing worked, raise informative error
    raise ValueError(f"Could not parse JSON from model output. Tried {len(candidates)} candidate(s) and repairs.")



def ollama_predict(scenario_json_path, csv_path=None, model_name='gpt-oss:20b', timeout=120, previous_response=None, measurement_responses=None):
    """Call a locally running Ollama model (HTTP or CLI) to get structured JSON predictions.

    Accepts optional `previous_response` and `measurement_responses` to support multi-turn interactive sessions.
    Fallback behavior: if the Ollama HTTP API is unreachable and the `ollama` CLI isn't
    installed or fails, this function will fall back to `mock_predict`.

    The model is instructed to return only a JSON object in the expected format.
    """
    with open(scenario_json_path) as f:
        scenario = json.load(f)

    summary = _summarize_csv(csv_path)

    # Build a compact prompt with schema and examples
    schema = {
        "scenario_id": "string",
        "predictions": [
            {
                "hypothesis": "string",
                "prob": "number (0..1)",
                "reason": ["short strings (2-4 bullets)"],
                "tests": ["list of diagnostic tests or measurements to run"],
                "mitigation": "short recommended immediate mitigation"
            }
        ],
        "requested_measurements": ["list of keys to request from the system (e.g. 'pump_motor_current', 'Ia_max_last_60s', 'cell_voltage_1_history')"],
        "explanation": "short justification of reasoning"
    }

    sample_output = {
        "scenario_id": scenario.get('scenario_id'),
        "predictions": [
            {
                "hypothesis": "Cooling pump failure",
                "prob": 0.75,
                "reason": ["inverter THERMAL_DERATE", "coolant temp rising"],
                "tests": ["measure pump_motor_current last 60s mean", "measure coolant inlet/outlet temps"],
                "mitigation": "limit torque and request service for pump"
            }
        ],
        "requested_measurements": ["pump_motor_current_last_60s_mean", "pump_motor_current_history"],
        "explanation": "Model sees thermal derate and coolant temp rise; pump current can confirm pump failure."
    }

    instructions = (
        "You are an automotive diagnostic assistant. Given the scenario doc and observations, return a single JSON object that conforms to the compact schema below and matches the sample output style.\n"
        "**Measurement keys examples:** pump_motor_current, pump_motor_current_last_60s_mean, pump_motor_current_history, Ia_max_last_60s, Ia_history, cell_voltage_1_history, cell_voltage_1_last_60s_mean, Vdc_min_last_60s, coolant_temp_last_60s_mean.\n"
        "**Schema:** " + json.dumps(schema) + "\n"
        "**Sample output:** " + json.dumps(sample_output) + "\n"
        "Do NOT include any extra commentary outside the JSON. Be concise, prefer conservative confidences if uncertain, and request only measurements that you will actually use to refine hypotheses."
    )

    user_content = {
        "scenario": scenario,
        "csv_summary": summary,
        "note": "If you need additional measurements, list them in `requested_measurements`. Use keys from the provided `csv_summary` where possible.",
    }

    if previous_response is not None:
        user_content['previous_response'] = previous_response
    if measurement_responses is not None:
        user_content['measurement_responses'] = measurement_responses

    prompt = f"{instructions}\n\nINPUT: {json.dumps(user_content, indent=None)}\n\nOUTPUT (JSON only):"

    # Try HTTP API first
    ollama_url = 'http://127.0.0.1:11434/api/generate'
    payload = {
        'model': model_name,
        'prompt': prompt,
        'max_tokens': 1024,
        'temperature': 0.0,
    }

    # Helper to parse text -> JSON
    def parse_and_return(text):
        try:
            return robust_parse_json(text)
        except Exception as e:
            # Save a small debug file for inspection
            try:
                dbg_path = f"/tmp/ollama_raw_{os.path.basename(scenario_json_path)}.txt"
                with open(dbg_path, 'w') as _f:
                    _f.write("---MODEL OUTPUT START---\n")
                    _f.write(text[:10000])
                    _f.write("\n---MODEL OUTPUT END---\n")
                dbg_note = f" (raw output saved to {dbg_path})"
            except Exception:
                dbg_note = ''
            raise RuntimeError(f"Failed to parse JSON from model output: {e}{dbg_note}\nOutput snippet:\n{(text[:1000] + '...') if len(text)>1000 else text}")

    if requests is not None:
        try:
            resp = requests.post(ollama_url, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                # Ollama's HTTP API may return `result` or `choices`; handle common shapes
                text = None
                if isinstance(data, dict):
                    if 'text' in data:
                        text = data['text']
                    elif 'result' in data and isinstance(data['result'], dict):
                        # older versions
                        text = data['result'].get('output') or data['result'].get('text')
                    elif 'choices' in data and len(data['choices']):
                        text = data['choices'][0].get('message') or data['choices'][0].get('text')
                if not text:
                    text = resp.text
                return parse_and_return(text)
        except Exception:
            # fall through to CLI attempt
            pass

    # Try `ollama` CLI
    try:
        # Try multiple CLI invocation styles for compatibility
        cli_commands = [
            ['ollama', 'generate', model_name, prompt],
            ['ollama', 'run', model_name, '--prompt', prompt],
            ['ollama', 'run', model_name, prompt],
        ]
        for cmd in cli_commands:
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            except FileNotFoundError:
                # ollama CLI not found
                raise
            if proc.returncode == 0 and proc.stdout:
                return parse_and_return(proc.stdout)
            # if stdout empty, try stderr as it sometimes prints to stderr
            if proc.returncode == 0 and proc.stderr:
                try:
                    return parse_and_return(proc.stderr)
                except Exception:
                    pass
    except FileNotFoundError:
        # ollama CLI not found
        pass
    except Exception:
        # any other error with CLI - continue to fallback
        pass

    # As a last resort, fall back to mock predictor with a warning embedded
    fallback = mock_predict(scenario_json_path, csv_path)
    fallback['explanation'] = '(FALLBACK to mock_predict because Ollama was unreachable) ' + fallback.get('explanation', '')
    return fallback


def interactive_ollama_predict(scenario_json_path, csv_path=None, model_name='gpt-oss:20b', timeout=120, max_rounds=3):
    """Run a multi-turn interactive session with the Ollama model.

    The model is allowed to request measurements from a constrained set of keys (present in the CSV summary).
    We provide requested measurements from `_summarize_csv` and re-run the model, up to `max_rounds`.

    Returns the final JSON response (dict) and a `trace` list of (model_resp, measurement_responses).
    """
    with open(scenario_json_path) as f:
        scenario = json.load(f)
    summary = _summarize_csv(csv_path)

    # allowed measurement keys (expose to model)
    allowed_keys = list(summary.keys())

    def _extract_windowed_stat(column, df, window_seconds=60, sample_hz=1):
        # assume timestamps are monotonic and sampled ~sample_hz
        n = int(window_seconds * sample_hz)
        if n <= 0:
            n = 1
        if column not in df.columns:
            return None
        series = df[column].dropna()
        if series.empty:
            return None
        # ensure numeric
        try:
            series_num = pd.to_numeric(series, errors='coerce').dropna()
        except Exception:
            return None
        if series_num.empty:
            return None
        last = series_num.iloc[-n:]
        return {
            'last_mean': float(last.mean()),
            'last_min': float(last.min()),
            'last_max': float(last.max()),
            'last_std': float(last.std())
        }

    def _extract_time_series(column, df, n_points=20):
        # return last n_points sampled evenly
        if column not in df.columns:
            return None
        series = df[column].dropna()
        if series.empty:
            return None
        if len(series) <= n_points:
            return list(series.tolist())
        idxs = np.linspace(0, len(series)-1, n_points).astype(int)
        return [float(series.iloc[i]) for i in idxs]

    def fetch_measurement(req):
        key = req.strip()
        # direct exact match against known summary
        if key in summary:
            return summary[key]

        # normalize and search for column names inside the key first
        lower_key = key.lower()
        try:
            import pandas as pd
            df = pd.read_csv(csv_path) if csv_path else None
        except Exception:
            df = None

        if df is None:
            return 'NOT_AVAILABLE'

        cols = df.columns.tolist()
        matched_col = None
        # direct and fuzzy substring matches
        for c in cols:
            cl = c.lower()
            if cl == lower_key:
                matched_col = c
                break
            if cl in lower_key or lower_key in cl:
                matched_col = c
                break
        # Also check common aliases
        if not matched_col:
            alias_map = {
                'pump': ['pump', 'pump_motor_current', 'pump_motor', 'pump_current'],
                'phasea': ['phasea', 'phase_a', 'phase_a_current', 'phase_a_i', 'phase a'],
                'cell_voltage': ['cell_voltage', 'cell_voltage_1', 'cell_voltage_2', 'cell_voltage_3', 'cell_voltage_4', 'cell', 'cell1']
            }
            for c in cols:
                cl = c.lower()
                for alias, tokens in alias_map.items():
                    for t in tokens:
                        if t in lower_key and t in cl:
                            matched_col = c
                            break
                    if matched_col:
                        break
                if matched_col:
                    break

        # If still no match, try regex extraction for column name
        if not matched_col:
            m_col = re.search(r'(ia|ib|ic|vdc|coolant_temp|pump_motor_current|cell_voltage_\d+|measured_torque|torque_request|can_drops)', lower_key)
            if m_col:
                token = m_col.group(1)
                for c in cols:
                    if token in c.lower():
                        matched_col = c
                        break

        if not matched_col:
            return 'NOT_AVAILABLE'

        # extract metric and window quantities if present
        # patterns like 'last_60s', '60s', 'last_60s_mean', 'last_60s_max', 'max_last_60s'
        window_seconds = 60
        metric = None
        m_window = re.search(r'(\d+)s', lower_key)
        if m_window:
            try:
                window_seconds = int(m_window.group(1))
            except Exception:
                window_seconds = 60
        if 'mean' in lower_key or 'avg' in lower_key:
            metric = 'mean'
        elif 'max' in lower_key or 'peak' in lower_key:
            metric = 'max'
        elif 'min' in lower_key:
            metric = 'min'
        elif 'std' in lower_key:
            metric = 'std'
        elif 'history' in lower_key or 'series' in lower_key or 'time' in lower_key:
            metric = 'series'

        # compute stats or timeseries
        if metric == 'series':
            ts = _extract_time_series(matched_col, df)
            return ts if ts is not None else 'NOT_AVAILABLE'
        stats = _extract_windowed_stat(matched_col, df, window_seconds)
        if stats is None:
            return 'NOT_AVAILABLE'
        if metric == 'mean' or metric == 'last' or metric is None:
            return stats['last_mean']
        if metric == 'max':
            return stats['last_max']
        if metric == 'min':
            return stats['last_min']
        if metric == 'std':
            return stats['last_std']
        # fallback
        return stats

        # normalize column name
        col = col if col else key
        col_candidates = []
        # match column names in CSV (case-insensitive)
        try:
            import pandas as pd
            df = pd.read_csv(csv_path) if csv_path else None
        except Exception:
            df = None
        if df is None:
            return 'NOT_AVAILABLE'

        cols = df.columns.tolist()
        for c in cols:
            if c.lower() == col.lower():
                col_candidates = [c]
                break
        if not col_candidates:
            # fuzzy match
            for c in cols:
                if col.lower() in c.lower():
                    col_candidates.append(c)
        if not col_candidates:
            return 'NOT_AVAILABLE'
        col = col_candidates[0]

        # If metric is explicit
        if metric and metric.lower() in ('mean', 'last'):
            stats = _extract_windowed_stat(col, df, window_seconds)
            if stats is None:
                return 'NOT_AVAILABLE'
            return stats['last_mean'] if metric.lower() in ('mean','last') else stats
        if metric and metric.lower() == 'max':
            stats = _extract_windowed_stat(col, df, window_seconds)
            return stats['last_max'] if stats else 'NOT_AVAILABLE'
        if metric and metric.lower() == 'min':
            stats = _extract_windowed_stat(col, df, window_seconds)
            return stats['last_min'] if stats else 'NOT_AVAILABLE'
        if 'peak' in key.lower():
            stats = _extract_windowed_stat(col, df, window_seconds)
            return stats['last_max'] if stats else 'NOT_AVAILABLE'

        # If asked for timeseries or 'history'
        if 'series' in key.lower() or 'history' in key.lower() or 'time' in key.lower():
            ts = _extract_time_series(col, df)
            return ts if ts is not None else 'NOT_AVAILABLE'

        # Default: return last_mean
        stats = _extract_windowed_stat(col, df, window_seconds)
        return stats if stats is not None else 'NOT_AVAILABLE'

    trace = []
    previous = None
    measurement_responses = None
    for r in range(max_rounds):
        resp = ollama_predict(scenario_json_path, csv_path, model_name=model_name, timeout=timeout, previous_response=previous, measurement_responses=measurement_responses)
        # ensure dict
        if not isinstance(resp, dict):
            raise RuntimeError('Model response was not a JSON object')
        reqs = resp.get('requested_measurements', []) or []
        # normalize strings
        reqs = [str(x) for x in reqs]
        meas = {}
        for req in reqs:
            meas[req] = fetch_measurement(req)
        trace.append((resp, meas))
        # if no requests, return
        if not reqs:
            return resp, trace
        # otherwise feed back measurements
        previous = resp
        measurement_responses = meas
    # max rounds reached, return last
    return previous or resp, trace


def openai_predict(scenario_json_path, csv_path=None, **kwargs):
    raise NotImplementedError("OpenAI adapter not implemented in this demo. Use mock_predict, ollama_predict, or implement your own adapter.")
