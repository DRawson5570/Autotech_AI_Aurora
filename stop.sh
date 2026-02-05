#!/usr/bin/env bash
set -euo pipefail

# Stops the Open WebUI systemd service on this machine.
# Intended for servers like poweredge2 where Open WebUI runs via systemd (no Docker).

SERVICE_NAME=${1:-${SERVICE_NAME:-autotech_ai}}

echo "Stopping ${SERVICE_NAME}.service..."
sudo systemctl stop "${SERVICE_NAME}" || true
sudo systemctl status "${SERVICE_NAME}" -l --no-pager || true
