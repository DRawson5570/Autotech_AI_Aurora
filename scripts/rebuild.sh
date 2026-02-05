#!/usr/bin/env bash
set -euo pipefail

# Rebuild helper for local development.
# - Rebuilds the Svelte frontend into ./build
# - Optionally restarts a systemd service if present
#
# Usage:
#   ./scripts/rebuild.sh              # build + restart if a known service exists
#   ./scripts/rebuild.sh --no-restart # build only
#   ./scripts/rebuild.sh --install    # npm install before build

NO_RESTART=0
DO_INSTALL=0

for arg in "$@"; do
  case "$arg" in
    --no-restart) NO_RESTART=1 ;;
    --install) DO_INSTALL=1 ;;
    -h|--help)
      sed -n '1,40p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $arg"
      echo "Run: $0 --help"
      exit 2
      ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "==> Rebuilding frontend in $REPO_DIR"

if ! command -v npm >/dev/null 2>&1; then
  echo "ERROR: npm not found. Install Node.js + npm (Node 20+ recommended)."
  exit 1
fi

if [[ "$DO_INSTALL" -eq 1 ]]; then
  echo "==> Installing Node deps (legacy peer deps)"
  npm install --legacy-peer-deps
elif [[ ! -d node_modules ]]; then
  echo "==> node_modules missing; installing Node deps (legacy peer deps)"
  npm install --legacy-peer-deps
fi

npm run build

echo "==> Frontend build complete"

if [[ "$NO_RESTART" -eq 1 ]]; then
  echo "==> Skipping restart (--no-restart)"
  exit 0
fi

if command -v systemctl >/dev/null 2>&1; then
  if systemctl list-unit-files | grep -q '^open-webui-local\.service'; then
    echo "==> Restarting systemd service: open-webui-local"
    sudo systemctl restart open-webui-local
    sudo systemctl --no-pager --full status open-webui-local || true
    exit 0
  fi

  if systemctl list-unit-files | grep -q '^autotech_ai\.service'; then
    echo "==> Restarting systemd service: autotech_ai"
    sudo systemctl restart autotech_ai
    sudo systemctl --no-pager --full status autotech_ai || true
    exit 0
  fi
fi

echo "==> No known systemd service found to restart."
echo "    If you're running via docker-compose, you may need: make startAndBuild"
echo "    If you're running uvicorn manually, just restart that process."
