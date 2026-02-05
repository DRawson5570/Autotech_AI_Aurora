#!/bin/bash
# ELM327 Simulator Service Control Script
# Usage: elm327_simulator.sh {start|stop|restart|status}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PID_FILE="/tmp/elm327_simulator.pid"
LOG_FILE="/tmp/elm327_simulator.log"

# Default settings (can be overridden with environment variables)
PORT="${ELM327_SIM_PORT:-35000}"
HOST="${ELM327_SIM_HOST:-0.0.0.0}"
STATE="${ELM327_SIM_STATE:-lean_both_banks}"

# Detect conda environment
if [ -d "$HOME/anaconda3/envs/open-webui" ]; then
    PYTHON="$HOME/anaconda3/envs/open-webui/bin/python"
elif [ -d "$HOME/miniconda3/envs/open-webui" ]; then
    PYTHON="$HOME/miniconda3/envs/open-webui/bin/python"
else
    PYTHON="python"
fi

start() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "ELM327 Simulator is already running (PID: $PID)"
            return 1
        fi
        rm -f "$PID_FILE"
    fi

    echo "Starting ELM327 Simulator..."
    echo "  Port: $PORT"
    echo "  Host: $HOST"
    echo "  State: $STATE"
    echo "  Log: $LOG_FILE"

    cd "$PROJECT_ROOT"
    nohup "$PYTHON" -m addons.scan_tool.simulator \
        --port "$PORT" \
        --host "$HOST" \
        --state "$STATE" \
        > "$LOG_FILE" 2>&1 &
    
    PID=$!
    echo $PID > "$PID_FILE"
    
    # Wait a moment and verify it started
    sleep 1
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "✅ ELM327 Simulator started (PID: $PID)"
        echo "   Connect with: nc localhost $PORT"
        return 0
    else
        echo "❌ Failed to start ELM327 Simulator"
        echo "   Check log: $LOG_FILE"
        rm -f "$PID_FILE"
        return 1
    fi
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "ELM327 Simulator is not running (no PID file)"
        # Try to find and kill any running simulator
        PIDS=$(pgrep -f "addons.scan_tool.simulator")
        if [ -n "$PIDS" ]; then
            echo "Found running simulator process(es): $PIDS"
            kill $PIDS 2>/dev/null
            echo "✅ Killed simulator process(es)"
        fi
        return 0
    fi

    PID=$(cat "$PID_FILE")
    if ps -p "$PID" > /dev/null 2>&1; then
        echo "Stopping ELM327 Simulator (PID: $PID)..."
        kill "$PID" 2>/dev/null
        
        # Wait for graceful shutdown
        for i in {1..5}; do
            if ! ps -p "$PID" > /dev/null 2>&1; then
                break
            fi
            sleep 1
        done
        
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            kill -9 "$PID" 2>/dev/null
        fi
        
        echo "✅ ELM327 Simulator stopped"
    else
        echo "ELM327 Simulator was not running"
    fi
    
    rm -f "$PID_FILE"
}

status() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "✅ ELM327 Simulator is running (PID: $PID)"
            echo "   Port: $PORT"
            
            # Check if port is actually listening
            if nc -z localhost "$PORT" 2>/dev/null; then
                echo "   Status: Accepting connections"
            else
                echo "   Status: Not accepting connections (may still be starting)"
            fi
            return 0
        fi
    fi
    
    # Check for orphaned process
    PIDS=$(pgrep -f "addons.scan_tool.simulator")
    if [ -n "$PIDS" ]; then
        echo "⚠️ ELM327 Simulator running but PID file missing"
        echo "   PIDs: $PIDS"
        return 0
    fi
    
    echo "❌ ELM327 Simulator is not running"
    return 1
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -f "$LOG_FILE"
    else
        echo "No log file found at $LOG_FILE"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 1
        start
        ;;
    status)
        status
        ;;
    logs)
        logs
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs}"
        echo ""
        echo "Environment variables:"
        echo "  ELM327_SIM_PORT  - Port to listen on (default: 35000)"
        echo "  ELM327_SIM_HOST  - Host to bind to (default: 0.0.0.0)"
        echo "  ELM327_SIM_STATE - Vehicle state to simulate (default: lean_both_banks)"
        echo ""
        echo "Available states:"
        echo "  normal, overheating, running_cold, lean_both_banks, lean_bank1,"
        echo "  rich_both_banks, misfire_cyl3, random_misfire, cat_degraded,"
        echo "  o2_sensor_lazy, maf_dirty"
        exit 1
        ;;
esac

exit $?
