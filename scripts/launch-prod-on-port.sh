#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: $0 [--port 8081] [--no-detach]

This script launches the production Open WebUI application using the existing installed
Python environment (conda env "open-webui" if present) and the production environment
file (/etc/default/open-webui) if it exists. It does NOT rebuild the frontend or (re)install
Python dependencies — exactly what you asked for.

Options:
  --port PORT      Port to listen on (default: 8081)
  --no-detach      Run in foreground (default: detached background)
  -h, --help       Show this message
EOF
}

REPO_DIR=/prod/autotech_ai
CONDA_ENV_NAME=open-webui
PORT=8081
DETACH=true
ENV_FILE=/etc/default/open-webui
PIDFILE="/tmp/open-webui-prod-test-${PORT}.pid"
LOGFILE="/tmp/open-webui-prod-test-${PORT}.log"

# parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"; shift 2;;
    --no-detach)
      DETACH=false; shift 1;;
    -h|--help)
      usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 2;;
  esac
done

# update files that depend on PORT
PIDFILE="/tmp/open-webui-prod-test-${PORT}.pid"
LOGFILE="/tmp/open-webui-prod-test-${PORT}.log"

if [ "$(id -u)" -eq 0 ]; then
  echo "Please do NOT run this script as root. Run as the regular user that owns ${REPO_DIR}."
  exit 1
fi

if [ ! -d "${REPO_DIR}" ]; then
  echo "Repo directory not found at ${REPO_DIR}"; exit 1
fi

cd "${REPO_DIR}"

# Load production env file if present (export variables)
if [ -f "${ENV_FILE}" ]; then
  echo "Loading environment file ${ENV_FILE} (will export variables)"
  # shellcheck disable=SC1090
  set -a; . "${ENV_FILE}"; set +a
else
  echo "No ${ENV_FILE} found — falling back to environment variables in the current shell."
fi

# Warn if production systemd service is running
if systemctl --type=service --state=running | grep -q '^open-webui\.service'; then
  echo "Warning: production service 'open-webui.service' appears to be running; you may be pointing at the same DB."
fi

# Prepare the command to run the app
RUN_CMD="python -m uvicorn open_webui.main:app --host 0.0.0.0 --port ${PORT}"

# Prefer conda-managed python if available
CONDA_PYTHON=$(conda run -n "${CONDA_ENV_NAME}" --no-capture-output which python 2>/dev/null || true)
if [ -n "${CONDA_PYTHON}" ]; then
  # Use conda run to ensure the correct env is active
  EXEC_PREFIX=(conda run -n "${CONDA_ENV_NAME}" --no-capture-output)
else
  EXEC_PREFIX=()
fi

if [ "${DETACH}" = true ]; then
  if [ -f "${PIDFILE}" ] && kill -0 "$(cat "${PIDFILE}")" 2>/dev/null; then
    echo "A process appears to be running already (pid $(cat "${PIDFILE}")). Stop it or remove ${PIDFILE} before starting another instance."; exit 1
  fi
  echo "Starting Open WebUI (production code) on port ${PORT} in background..."
  nohup "${EXEC_PREFIX[@]}" bash -lc "$RUN_CMD" > "${LOGFILE}" 2>&1 &
  echo $! > "${PIDFILE}"
  echo "Launched (pid $(cat "${PIDFILE}")); logs: ${LOGFILE}"
  echo "To follow logs: tail -F ${LOGFILE}"
else
  echo "Starting Open WebUI (production code) on port ${PORT} in foreground (CTRL-C to stop)"
  exec "${EXEC_PREFIX[@]}" bash -lc "$RUN_CMD"
fi
