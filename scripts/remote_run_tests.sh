#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 --host <ssh-host> [options]

Options:
  --host USER@HOST or HOST (required)
  --remote-dir PATH       Remote repo path (default: /prod/autotech_ai)
  --model MODEL           Model to test (default: gpt-oss:120b)
  --prompt PROMPT         Prompt to send (quoted string)
  --concurrency N         Concurrency for stress test (default: 2)
  --requests N            Total requests per worker (default: 8)
  --max-tokens N          Max tokens for generation (default: 8192)
  --port N                Alternate Ollama/runner port (passed through) (optional)
  -h, --help              Show this message

Example:
  bash scripts/remote_run_tests.sh --host poweredge2 --model 'gpt-oss:120b' --concurrency 2 --requests 4

This script will:
  - SCP the local `scripts/` files to remote:<remote-dir>/scripts/
  - SSH and run `./scripts/launch_gpu_stress_test.sh` remotely with provided options
  - Archive remote logs to /tmp/remote_test_results_<timestamp>.tar.gz and SCP them back locally into ./remote_test_results/

Note: I cannot SSH from this environment. Run this script on your workstation which has SSH access to the target host.
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

# defaults
REMOTE_DIR='/prod/autotech_ai'
MODEL='gpt-oss:120b'
PROMPT='Benchmarking GPU utilization — please ignore.'
CONCURRENCY=2
REQUESTS=8
MAX_TOKENS=8192
PORT=''

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --host) HOST="$2"; shift 2;;
    --remote-dir) REMOTE_DIR="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --prompt) PROMPT="$2"; shift 2;;
    --concurrency) CONCURRENCY="$2"; shift 2;;
    --requests) REQUESTS="$2"; shift 2;;
    --max-tokens) MAX_TOKENS="$2"; shift 2;;
    --port) PORT="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

if [[ -z "${HOST:-}" ]]; then
  echo "--host is required"
  usage
  exit 2
fi

TS=$(date -u +%Y%m%dT%H%M%SZ)
REMOTE_TMP="/tmp/remote_test_results_${TS}"
REMOTE_TAR="/tmp/remote_test_results_${TS}.tar.gz"
LOCAL_DIR="remote_test_results"
mkdir -p "$LOCAL_DIR"

echo "Copying scripts/ to ${HOST}:${REMOTE_DIR}/scripts/ ..."
scp -r scripts/* "${HOST}:${REMOTE_DIR}/scripts/"

echo "Running remote stress test on ${HOST} (remote dir: ${REMOTE_DIR})..."

# Build the remote command
REMOTE_CMD="set -euo pipefail; mkdir -p ${REMOTE_TMP}; cd ${REMOTE_DIR}; \
  ./scripts/launch_gpu_stress_test.sh --model '${MODEL}' --prompt \"${PROMPT}\" --concurrency ${CONCURRENCY} --requests ${REQUESTS} --max-tokens ${MAX_TOKENS}"
if [[ -n "$PORT" ]]; then
  REMOTE_CMD+=" --port ${PORT}"
fi

# Run it on remote; wrap in a nohup so it can run detached but we also capture the wrapper output
SSH_CMD="mkdir -p ${REMOTE_TMP} && nohup bash -lc \"${REMOTE_CMD} > ${REMOTE_TMP}/remote_test.log 2>&1\" & echo \$! > ${REMOTE_TMP}/remote_test.pid"

ssh "$HOST" "$SSH_CMD"

# Wait a short moment for job to start
sleep 2

echo "Remote wrapper started. Waiting for remote wrapper to finish (this may take a long time depending on tests)."

# Poll remote for pid and completion
while true; do
  if ssh "$HOST" "[ -f ${REMOTE_TMP}/remote_test.pid ] && ! kill -0 \$(cat ${REMOTE_TMP}/remote_test.pid) 2>/dev/null"; then
    echo "Remote test process has exited. Collecting logs..."
    break
  fi
  # if no pid yet, or still running, sleep
  sleep 10
  echo -n '.'
done

# On completion, archive logs we expect
echo "Archiving remote logs to ${REMOTE_TAR}..."
ssh "$HOST" "cd ${REMOTE_TMP} || true; tar -czf ${REMOTE_TAR} --ignore-failed-read --warning=no-file-changed *.log *.txt || true"

LOCAL_TAR="$LOCAL_DIR/${HOST//[:@]/_}-${TS}.tar.gz"
scp "$HOST:${REMOTE_TAR}" "$LOCAL_TAR" || { echo "Failed to fetch ${REMOTE_TAR}"; exit 3; }

echo "Fetched results to ${LOCAL_TAR}"

# Optionally, fetch specific files if desired
echo "Done. Extract results with: tar -xzf ${LOCAL_TAR} -C ${LOCAL_DIR}"

exit 0
