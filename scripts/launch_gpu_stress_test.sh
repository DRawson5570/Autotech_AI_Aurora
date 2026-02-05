#!/usr/bin/env bash
set -euo pipefail

# Wrapper to run the GPU stress helper from the scripts dir
# Usage: ./launch_gpu_stress_test.sh [args...]
# Example: ./launch_gpu_stress_test.sh --requests 20 --concurrency 5 --max-tokens 2000

SCRIPT_DIR=$(dirname "$0")
"$SCRIPT_DIR/run_gpu_stress.sh" "$@"
