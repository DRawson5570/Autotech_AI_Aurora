#!/usr/bin/env bash
set -euo pipefail

# Deploy helper for local repo server (run on target server as the user that owns /prod/autotech_ai)
# Usage: sudo --tt bash ./deploy-open-webui-local.sh

REPO_DIR=/prod/autotech_ai
CONDA_ENV_NAME=open-webui
SERVICE_USER=$(whoami)
FRONTEND_PORT=8080
ENV_FILE=/etc/default/open-webui-local
SYSTEMD_UNIT=/etc/systemd/system/open-webui-local.service

# Prevent running as root — run the script as the repo owner (use sudo only when prompted by commands inside the script)
if [ "$(id -u)" -eq 0 ]; then
  echo "Please do NOT run this script as root. Exit and re-run as the regular user that owns $REPO_DIR."
  exit 1
fi

if [ ! -d "$REPO_DIR" ]; then
  echo "Repo not found at $REPO_DIR"
  exit 1
fi

cd "$REPO_DIR"

echo "Checking Node version (requires >=20)..."
if command -v node >/dev/null 2>&1; then
  NODE_VERSION=$(node -v | sed 's/^v//')
  NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)
  if [ "$NODE_MAJOR" -lt 20 ]; then
    echo "Node $NODE_VERSION detected — Node >= 20 is required. Please install Node 20 (nvm recommended)."
    echo "Quick install (per-user, non-invasive):"
    echo "  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.4/install.sh | bash"
    echo "  export NVM_DIR=\"$HOME/.nvm\" && \. \"$NVM_DIR/nvm.sh\" && nvm install 20 && nvm use 20"
    exit 1
  fi
else
  echo "Node not found. Please install Node 20 (nvm recommended)."
  exit 1
fi

echo "Installing Node deps and building frontend..."
if command -v npm >/dev/null 2>&1; then
  # Some package peer-deps conflict with the exact versions; prefer legacy peer deps resolution
  npm ci --legacy-peer-deps || npm install --legacy-peer-deps
  npm run build
else
  echo "npm not found; please install Node.js & npm"
  exit 1
fi

# Install Python deps into conda env
echo "Installing Python dependencies into conda env '$CONDA_ENV_NAME'..."
conda run -n "$CONDA_ENV_NAME" --no-capture-output pip install -r backend/requirements.txt
conda run -n "$CONDA_ENV_NAME" --no-capture-output pip install -e .

# detect python path inside conda env (optional)
PYTHON_PATH=$(conda run -n "$CONDA_ENV_NAME" --no-capture-output which python || true)
if [ -z "$PYTHON_PATH" ]; then
  echo "WARNING: Unable to detect python in conda env '$CONDA_ENV_NAME'. The systemd unit will use conda run."
fi

echo "Writing environment file to $ENV_FILE (sudo will be used)..."
sudo --tt tee "$ENV_FILE" > /dev/null <<EOF
FRONTEND_BUILD_DIR=${REPO_DIR}/build
OPEN_WEBUI_DIR=${REPO_DIR}
DATABASE_URL=sqlite:////prod/autotech_ai/backend/data/db.sqlite3
REDIS_URL=redis://localhost:6379
SECRET_KEY=replace_this_with_a_secure_value
WEBUI_NAME="AUTOTECH AI"
EOF

# Create systemd unit (if PYTHON_PATH found use it, otherwise use conda run)
echo "Creating systemd unit $SYSTEMD_UNIT"
if [ -n "$PYTHON_PATH" ]; then
  sudo --tt tee "$SYSTEMD_UNIT" > /dev/null <<EOF
[Unit]
Description=Open WebUI (local repo)
After=network.target

[Service]
User=${SERVICE_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_PATH} -m uvicorn open_webui.main:app --host 0.0.0.0 --port ${FRONTEND_PORT}
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
else
  sudo --tt tee "$SYSTEMD_UNIT" > /dev/null <<EOF
[Unit]
Description=Open WebUI (local repo)
After=network.target

[Service]
User=${SERVICE_USER}
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/bin/bash -lc 'conda run -n ${CONDA_ENV_NAME} --no-capture-output python -m uvicorn open_webui.main:app --host 0.0.0.0 --port ${FRONTEND_PORT}'
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
fi

# Run DB migrations (explicit)
echo "Running DB migrations (alembic)..."
conda run -n "$CONDA_ENV_NAME" --no-capture-output python -m alembic -c backend/open_webui/alembic.ini upgrade head || true

# Reload systemd and enable/start
echo "Reloading systemd and starting service open-webui-local..."
sudo systemctl daemon-reload
sudo systemctl enable --now open-webui-local
sudo systemctl status open-webui-local -l --no-pager || true

echo "Deployment finished. Check logs with: sudo journalctl -u open-webui-local -f"