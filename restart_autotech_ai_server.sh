#!/usr/bin/env bash
set -euo pipefail

# Restarts the Open WebUI systemd service on this machine.
# Intended for servers like hp6 where Open WebUI runs via systemd (no Docker).

SERVICE_NAME=${1:-${SERVICE_NAME:-autotech_ai}}

echo "Restarting ${SERVICE_NAME}.service..."
sudo systemctl restart "${SERVICE_NAME}"
sudo systemctl status "${SERVICE_NAME}" -l --no-pager || true
