#!/usr/bin/env bash
set -euo pipefail

# Toggle between pip-installed open-webui (service: open-webui)
# and local repo service (open-webui-local).
# Usage: sudo --tt /usr/local/bin/switch-open-webui.sh local|pip

if [[ "$#" -ne 1 ]]; then
  echo "Usage: $0 local|pip"
  exit 2
fi

if [[ "$1" == "local" ]]; then
  sudo systemctl stop open-webui || true
  sudo systemctl disable open-webui || true
  sudo systemctl daemon-reload
  sudo systemctl enable --now open-webui-local
  sudo systemctl status open-webui-local --no-pager
elif [[ "$1" == "pip" ]]; then
  sudo systemctl stop open-webui-local || true
  sudo systemctl disable open-webui-local || true
  sudo systemctl daemon-reload
  sudo systemctl enable --now open-webui
  sudo systemctl status open-webui --no-pager
else
  echo "Usage: $0 local|pip"
  exit 2
fi