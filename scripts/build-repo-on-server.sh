#!/usr/bin/env bash
set -euo pipefail

# Build/install the repo on the server WITHOUT creating/updating systemd units.
# Intended for servers that already have a service unit (e.g., autotech_ai.service)
# and just need updated code + rebuilt frontend + refreshed python deps.
#
# Run this on the server as the repo owner (not root). It will not use sudo.

REPO_DIR=${REPO_DIR:-/prod/autotech_ai}
CONDA_ENV_NAME=${CONDA_ENV_NAME:-open-webui}

resolve_conda() {
  if command -v conda >/dev/null 2>&1; then
    command -v conda
    return 0
  fi

  # Common install locations
  local candidates=(
    "${HOME}/anaconda3/bin/conda"
    "${HOME}/miniconda3/bin/conda"
    "/opt/conda/bin/conda"
    "/usr/local/miniconda3/bin/conda"
  )

  for p in "${candidates[@]}"; do
    if [ -x "${p}" ]; then
      echo "${p}"
      return 0
    fi
  done

  # Try sourcing conda.sh if present, then retry
  local conda_sh_candidates=(
    "${HOME}/anaconda3/etc/profile.d/conda.sh"
    "${HOME}/miniconda3/etc/profile.d/conda.sh"
    "/opt/conda/etc/profile.d/conda.sh"
  )
  for shfile in "${conda_sh_candidates[@]}"; do
    if [ -f "${shfile}" ]; then
      # shellcheck disable=SC1090
      . "${shfile}" || true
      if command -v conda >/dev/null 2>&1; then
        command -v conda
        return 0
      fi
    fi
  done

  return 1
}

if [ "$(id -u)" -eq 0 ]; then
  echo "Please do NOT run this script as root. Run as the regular user that owns ${REPO_DIR}." >&2
  exit 1
fi

if [ ! -d "${REPO_DIR}" ]; then
  echo "Repo directory not found at ${REPO_DIR}" >&2
  exit 1
fi

cd "${REPO_DIR}"

echo "Building frontend (npm ci + build)..."
if ! command -v node >/dev/null 2>&1; then
  echo "Node not found. Install Node >= 20 on the server." >&2
  exit 1
fi
if ! command -v npm >/dev/null 2>&1; then
  echo "npm not found. Install Node/npm on the server." >&2
  exit 1
fi

NODE_VERSION=$(node -v | sed 's/^v//')
NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
if [ "${NODE_MAJOR}" -lt 20 ]; then
  echo "Node ${NODE_VERSION} detected — Node >= 20 is required." >&2
  exit 1
fi

npm ci --legacy-peer-deps || npm install --legacy-peer-deps
npm run build

echo "Installing Python deps into conda env '${CONDA_ENV_NAME}'..."
CONDA_BIN=$(resolve_conda || true)
if [ -z "${CONDA_BIN}" ]; then
  echo "ERROR: conda not found on PATH and not found in common locations." >&2
  echo "Set CONDA_BIN=/path/to/conda or ensure conda is available in non-interactive shells." >&2
  exit 1
fi

"${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" --no-capture-output pip install -r backend/requirements.txt
"${CONDA_BIN}" run -n "${CONDA_ENV_NAME}" --no-capture-output pip install -e .

echo "Build complete. You can now restart your systemd service."
