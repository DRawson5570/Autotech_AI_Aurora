# Experiment runner

This document explains how to run experiments locally using the provided tools.

1) Generate scenarios

```bash
python synthetic_edm/generate_scenarios.py --count 10 --outdir synthetic_edm/example_scenarios/
```

2) Run the mock model to produce outputs and score

```bash
python synthetic_edm/run_experiment.py --scenarios synthetic_edm/example_scenarios --outputs synthetic_edm/model_outputs --model mock --score
```

This will:
- Use `model_adapters.mock_predict` to generate structured predictions for each scenario
- Write outputs to `synthetic_edm/model_outputs/model_output_<scenario>.json`
- Run `evaluate.score_directory` to print a summary with Top-1 and Top-3 accuracy
3a) Run a local Ollama model (if you have one running)

```bash
python synthetic_edm/run_experiment.py --scenarios synthetic_edm/example_scenarios --outputs synthetic_edm/model_outputs --model ollama --ollama-model gpt-oss:20b --score
```

Notes:
- The adapter will attempt to call Ollama's HTTP API at `http://127.0.0.1:11434/api/generate` first; if that fails it will try the `ollama` CLI.
- If neither method works, the adapter will fall back to the `mock_predict` behavior and include a note in the `explanation` field indicating a fallback.
- The model is instructed to return JSON only. If parsing fails, the runner will print a parse error and fall back to `mock_predict`.

3b) Run an interactive Ollama session (model can request measurements)

```bash
python synthetic_edm/run_experiment.py --scenarios synthetic_edm/example_scenarios --outputs synthetic_edm/model_outputs --model ollama --ollama-model gpt-oss:20b --interactive --score
```

Notes:
- In interactive mode the model may return `requested_measurements` (a list of keys). The runner will reply with values derived from the CSV summary (keys like `coolant_temp_max`, `Ia_max`, `Vdc_min`, etc.).
- The adapter runs up to 3 rounds of measurement requests by default and saves an execution trace to `model_outputs/model_trace_<scenario>.json`.
- This mode helps evaluate whether the model can ask for targeted diagnostics and improve its hypotheses.3) Replace mock with your own adapter

- Implement a function that accepts `(scenario_json_path, csv_path)` and returns the same structured JSON format as the mock.
- Hook it into `run_experiment.py` or call it externally and place outputs in `synthetic_edm/model_outputs/` as `model_output_<scenario>.json`.

4) Scoring and human ratings

- Use `rubric.md` to guide SME ratings for diagnostic test usefulness and explanation clarity.
- Add SME ratings to a CSV and merge into aggregated results for full scoring.

If you'd like, I can implement an OpenAI adapter and a small interactive harness to respond to follow-up measurement requests automatically using the generated CSV logs.