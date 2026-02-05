#!/usr/bin/env bash
set -euo pipefail

# Run a long baseline and a concurrent stress test while capturing GPU telemetry and ollama logs.
# Usage: sudo --tt not required; run as repo owner and you'll be prompted when needed for systemctl/journalctl
# Example:
# ./scripts/run_gpu_stress.sh --port 11434 --model gpt-oss:120b --prompt-file ./long_prompt.txt --requests 20 --concurrency 5 --duration 300

REPO_DIR=/prod/autotech_ai
URL=http://127.0.0.1:11434/api/generate
MODEL=gpt-oss:120b
PROMPT_FILE=""
REQUESTS=20
CONCURRENCY=5
TIMEOUT=600
MAX_TOKENS=2000
DURATION=300
OUTDIR=./tmp/gpu-stress-$(date +%s)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --url) URL="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --prompt-file) PROMPT_FILE="$2"; shift 2;;
    --requests) REQUESTS="$2"; shift 2;;
    --concurrency) CONCURRENCY="$2"; shift 2;;
    --max-tokens) MAX_TOKENS="$2"; shift 2;;
    --timeout) TIMEOUT="$2"; shift 2;;
    --duration) DURATION="$2"; shift 2;;
    --outdir) OUTDIR="$2"; shift 2;;
    -h|--help) echo "Usage: $0 [--url URL] [--model MODEL] [--prompt-file FILE] [--requests N] [--concurrency N] [--max-tokens N]"; exit 0;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

mkdir -p "$OUTDIR"

if [ -z "$PROMPT_FILE" ]; then
  PROMPT="Write a long, detailed essay of about 2000 tokens on the topic of test load for large language models. Include many paragraphs and details to force a long generation."
else
  PROMPT=$(cat "$PROMPT_FILE")
fi

echo "Output directory: $OUTDIR"

# Start GPU telemetry collection
echo "Starting nvidia-smi logging..."
nohup bash -c "nvidia-smi --query-gpu=timestamp,name,utilization.gpu,utilization.memory,memory.used,power.draw --format=csv -l 1 > $OUTDIR/nvidia.log" &
NVSMI_PID=$!

# Start ollama (or other runner) journal capture (if service exists)
echo "Starting ollama journal capture (if available)..."
nohup bash -c "sudo journalctl -u ollama -f > $OUTDIR/ollama.log" &
JOURNAL_PID=$!

# Run baseline (long)
echo "Running baseline long inference..."
python3 "$REPO_DIR/scripts/stress_test_model.py" --url "$URL" --model "$MODEL" --prompt "$PROMPT" --baseline --timeout $TIMEOUT --max-tokens $MAX_TOKENS --save-output "$OUTDIR/baseline_response.bin"

# Short pause
sleep 2

# Run concurrent stress test
echo "Running concurrent stress test: requests=$REQUESTS concurrency=$CONCURRENCY max_tokens=$MAX_TOKENS"
python3 "$REPO_DIR/scripts/stress_test_model.py" --url "$URL" --model "$MODEL" --prompt "$PROMPT" --requests $REQUESTS --concurrency $CONCURRENCY --timeout $TIMEOUT --max-tokens $MAX_TOKENS > "$OUTDIR/stress_summary.txt"

# Wait a bit to collect telemetry
sleep 3

# Stop telemetry background processes
echo "Stopping telemetry collectors (nvidia-smi pid $NVSMI_PID, journal pid $JOURNAL_PID)"
kill $NVSMI_PID || true
kill $JOURNAL_PID || true

echo "Collected logs in $OUTDIR"
ls -l "$OUTDIR"

echo "You can inspect GPU telemtery in $OUTDIR/nvidia.log and runner logs in $OUTDIR/ollama.log and summary in $OUTDIR/stress_summary.txt"

exit 0
