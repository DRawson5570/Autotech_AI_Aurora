#!/bin/bash
# Mitchell Agent Start Script
# Supports multiple scaling modes: single, pool, ondemand

set -e

# Load environment variables from mitchell_agent/.env
ENV_FILE="addons/mitchell_agent/.env"
if [ -f "$ENV_FILE" ]; then
    set -a  # auto-export all variables
    source "$ENV_FILE"
    set +a
    echo "✓ Loaded environment from $ENV_FILE"
else
    echo "✗ Environment file not found: $ENV_FILE"
    exit 1
fi

# Force headless mode (override .env setting)
export MITCHELL_LOG_LEVEL=trace
export MITCHELL_HEADLESS=true
export MITCHELL_SCALING_MODE=ondemand

# Verify Gemini API key is set
if [ -z "$GEMINI_API_KEY" ]; then
    echo "✗ GEMINI_API_KEY not set in .env"
    exit 1
fi
echo "✓ Gemini API key configured"
echo "✓ Backend: ${NAVIGATOR_BACKEND:-gemini}"

# Show scaling mode
SCALING_MODE=${MITCHELL_SCALING_MODE:-single}
echo "✓ Scaling mode: $SCALING_MODE"
if [ "$SCALING_MODE" = "pool" ] || [ "$SCALING_MODE" = "ondemand" ]; then
    echo "  Min workers: ${MITCHELL_POOL_MIN_WORKERS:-1}"
    echo "  Max workers: ${MITCHELL_POOL_MAX_WORKERS:-3}"
    echo "  Idle timeout: ${MITCHELL_POOL_IDLE_TIMEOUT:-300}s"
    echo "  Base port: ${MITCHELL_POOL_BASE_PORT:-9222}"
fi

# Activate conda environment
echo "Activating conda environment: open-webui"
eval "$(conda shell.bash hook)"
conda activate open-webui

# Run the agent
echo ""
echo "Starting Mitchell Agent..."
echo "=========================================="

# Use pooled agent if pool or ondemand mode
if [ "$SCALING_MODE" = "pool" ] || [ "$SCALING_MODE" = "ondemand" ]; then
    python -m addons.mitchell_agent.agent.pooled_agent
else
    python -m addons.mitchell_agent.agent.service
fi
