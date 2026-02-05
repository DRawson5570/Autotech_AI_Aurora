# Synthetic EDM Dataset

This folder contains a synthetic dataset generator and example scenarios for the Electric Drive Module (EDM) diagnostic experiment.

Contents:
- `generate_scenarios.py` — generator script to create scenarios and time-series logs (CSV + scenario JSON)
- `schema.md` — scenario/schema specification
- `example_scenarios/EDM_001.json` — worked example scenario (cooling pump failure)
- `example_scenarios/EDM_001_log.csv` — corresponding time-series log
- `prompts.md` — prompt templates for model queries and interactive diagnosis
- `evaluate.py` — simple evaluation script (Top-1/Top-3 accuracy)

Quick start
1. Install dependencies: `pip install numpy pandas`
2. Generate scenarios: `python generate_scenarios.py --count 10 --outdir example_scenarios/`
3. Use `prompts.md` for model queries and `evaluate.py` to score outputs.
---

## Running experiments (mock model)

Use the provided runner to generate model outputs from the built-in mock model and score results:

```bash
python run_experiment.py --scenarios example_scenarios --outputs model_outputs --model mock --score
```

This will:
- Generate mock predictions for each scenario and write them to `model_outputs/`
- Run the scorer to print Top-1 and Top-3 accuracy

If you'd like, I can add a real adapter for OpenAI/HuggingFace models or implement an interactive measurement-response loop.
If you'd like, I can add unit tests or a small CLI to run full experiments and scoring.