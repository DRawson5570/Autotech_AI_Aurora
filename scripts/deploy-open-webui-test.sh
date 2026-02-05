#!/usr/bin/env bash
set -euo pipefail

# Deploy a test instance of the repo on the same host on a different port
# Usage: ./deploy-open-webui-test.sh [--port 8081] [--service-name open-webui-test] [--test-db /path/to/db-test.sqlite3]
# Run this as the repo owner (not root). The script will use sudo when writing /etc and systemd.

REPO_DIR=/prod/autotech_ai
CONDA_ENV_NAME=open-webui
DEFAULT_PORT=8081
SERVICE_NAME=open-webui-test
ENV_FILE_BASE=/etc/default
SYSTEMD_DIR=/etc/systemd/system

# Parse args
PORT=${DEFAULT_PORT}
TEST_DB=""
USE_PROD_DB=false
FORCE=false
ALLOW_MIGRATIONS=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --test-db)
      TEST_DB="$2"
      shift 2
      ;;
    --use-prod-db)
      USE_PROD_DB=true
      shift 1
      ;;
    --force)
      FORCE=true
      shift 1
      ;;
    --allow-migrations)
      ALLOW_MIGRATIONS=true
      shift 1
      ;;
    -h|--help)
      echo "Usage: $0 [--port PORT] [--service-name SERVICE] [--test-db /path/to/db] [--use-prod-db] [--allow-migrations] [--force]"
      echo "  --use-prod-db        Make the test instance use the production DB directly (dangerous)."
      echo "  --allow-migrations   If using production DB, allow running migrations against it."
      echo "  --force              Skip confirmation prompts when using production DB."
      exit 0
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

SERVICE_UNIT=${SYSTEMD_DIR}/${SERVICE_NAME}.service
ENV_FILE=${ENV_FILE_BASE}/${SERVICE_NAME}

if [ "$(id -u)" -eq 0 ]; then
  echo "Please do NOT run this script as root. Run as the regular user that owns ${REPO_DIR}."
  exit 1
fi

if [ ! -d "${REPO_DIR}" ]; then
  echo "Repo directory not found at ${REPO_DIR}"
  exit 1
fi

cd "${REPO_DIR}"

# Node version check
if command -v node >/dev/null 2>&1; then
  NODE_VERSION=$(node -v | sed 's/^v//')
  NODE_MAJOR=$(echo "${NODE_VERSION}" | cut -d. -f1)
  if [ "${NODE_MAJOR}" -lt 20 ]; then
    echo "Node ${NODE_VERSION} detected — Node >= 20 required. Install via nvm:"
    echo "  curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.4/install.sh | bash"
    echo "  export NVM_DIR=\"$HOME/.nvm\" && \. \"$NVM_DIR/nvm.sh\" && nvm install 20 && nvm use 20"
    exit 1
  fi
else
  echo "Node not found. Install Node 20 (nvm recommended)."
  exit 1
fi

# Build frontend
echo "Building frontend (npm ci + build)"
if command -v npm >/dev/null 2>&1; then
  npm ci --legacy-peer-deps || npm install --legacy-peer-deps
  npm run build
else
  echo "npm not found; please install Node & npm (nvm recommended)."
  exit 1
fi

# Install Python deps in conda env
echo "Installing Python dependencies into conda env '${CONDA_ENV_NAME}'..."
conda run -n "${CONDA_ENV_NAME}" --no-capture-output pip install -r backend/requirements.txt
conda run -n "${CONDA_ENV_NAME}" --no-capture-output pip install -e .

# Detect production DB (if running pip service) to copy it for a test DB
echo "Detecting current DATABASE_URL from running open-webui service (if present)..."
SOURCE_DATABASE_URL=""
if systemctl --type=service --state=running | grep -q '^open-webui\.service'; then
  ENVSTR=$(sudo systemctl show open-webui --property=Environment --value || true)
  if [ -n "${ENVSTR}" ]; then
    # Find DATABASE_URL=<val>
    for item in ${ENVSTR//:/ }; do
      case "$item" in
        DATABASE_URL=*) SOURCE_DATABASE_URL="${item#DATABASE_URL=}"; break ;;
      esac
    done
  fi
fi

# If SOURCE_DATABASE_URL not found, try conventional path
if [ -z "${SOURCE_DATABASE_URL}" ]; then
  PROD_DB_PATH="${REPO_DIR}/backend/data/db.sqlite3"
  if [ -f "${PROD_DB_PATH}" ]; then
    SOURCE_DATABASE_URL="sqlite:////${PROD_DB_PATH}"
  fi
fi

# Compute TEST_DB path
if [ -n "${TEST_DB}" ]; then
  TEST_DB_PATH="${TEST_DB}"
else
  TEST_DB_PATH="${REPO_DIR}/backend/data/db-test.sqlite3"
fi

if [ "${USE_PROD_DB}" = true ]; then
  if [ -z "${SOURCE_DATABASE_URL}" ]; then
    echo "Cannot --use-prod-db: production DATABASE_URL not detected. Aborting."
    exit 1
  fi

  echo "WARNING: You requested to use the production DB for the test service. This will point the test service at the same DB used by production (may run migrations that modify it)."
  if [ "${FORCE}" != true ]; then
    read -p "Type YES to confirm you want to use the production DB for testing: " CONFIRM
    if [ "${CONFIRM}" != "YES" ]; then
      echo "Confirmation not given; aborting."
      exit 1
    fi
  else
    echo "--force specified; proceeding without interactive confirmation."
  fi

  # Use the production DB directly — no copying
  TEST_DB_PATH="${SOURCE_DATABASE_URL#sqlite:////}"
  echo "Test service will use production DB path: ${TEST_DB_PATH}"
else
  if [ -n "${SOURCE_DATABASE_URL}" ]; then
    echo "Found source DB: ${SOURCE_DATABASE_URL}"
    if [[ "${SOURCE_DATABASE_URL}" == sqlite:* ]]; then
      # extract file path
      SRC_FILE=${SOURCE_DATABASE_URL#sqlite:////}
      if [ -f "${SRC_FILE}" ]; then
        echo "Copying SQLite DB to test DB: ${SRC_FILE} -> ${TEST_DB_PATH}"
        cp "${SRC_FILE}" "${TEST_DB_PATH}"
      else
        echo "Source sqlite DB file not found at ${SRC_FILE}; proceeding without DB copy"
      fi
    else
      echo "Source DB is not SQLite. For non-sqlite DBs (Postgres), please create a test database (dump/restore) manually and pass --test-db to this script."
    fi
  else
    echo "No source DB found; proceeding with an empty test DB at ${TEST_DB_PATH} (if it doesn't exist, it will be created on migration)."
  fi
fi

# Write environment file for test service (sudo required)
echo "Writing environment file ${ENV_FILE} (sudo)..."
sudo --tt tee "${ENV_FILE}" > /dev/null <<EOF
FRONTEND_BUILD_DIR=${REPO_DIR}/build
OPEN_WEBUI_DIR=${REPO_DIR}
DATABASE_URL=sqlite:////${TEST_DB_PATH}
REDIS_URL=redis://localhost:6379
SECRET_KEY=replace_this_with_a_secure_value
WEBUI_NAME="AUTOTECH AI (TEST)"
# NOTE: adjust any additional env vars as needed
EOF

# Create systemd unit for test service (prefer conda python path if available)
PYTHON_PATH=$(conda run -n "${CONDA_ENV_NAME}" --no-capture-output which python || true)
if [ -n "${PYTHON_PATH}" ]; then
  echo "Creating systemd unit ${SERVICE_UNIT} using ${PYTHON_PATH}"
  sudo --tt tee "${SERVICE_UNIT}" > /dev/null <<EOF
[Unit]
Description=Open WebUI (test repository instance)
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${PYTHON_PATH} -m uvicorn open_webui.main:app --host 0.0.0.0 --port ${PORT}
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
else
  echo "Conda python path not detected; creating unit that runs via conda run"
  sudo --tt tee "${SERVICE_UNIT}" > /dev/null <<EOF
[Unit]
Description=Open WebUI (test repository instance)
After=network.target

[Service]
User=$(whoami)
WorkingDirectory=${REPO_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=/bin/bash -lc 'conda run -n ${CONDA_ENV_NAME} --no-capture-output python -m uvicorn open_webui.main:app --host 0.0.0.0 --port ${PORT}'
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
fi

# Run migrations if allowed and not using production DB, or if explicitly allowed with --allow-migrations
if [ "${USE_PROD_DB}" = true ]; then
  echo "Using production DB for test service; by default we will NOT run database migrations."
  if [ "${ALLOW_MIGRATIONS}" = true ]; then
    echo "--allow-migrations specified: running alembic migrations against production DB (TODO: ensure backups exist)."
    conda run -n "${CONDA_ENV_NAME}" --no-capture-output python -m alembic -c backend/open_webui/alembic.ini upgrade head || true
  else
    echo "Skipping migrations as requested. If you want to run migrations against the production DB, re-run with --allow-migrations (and ensure you have a backup)."
  fi
else
  echo "Running alembic migrations against test DB..."
  conda run -n "${CONDA_ENV_NAME}" --no-capture-output python -m alembic -c backend/open_webui/alembic.ini upgrade head || true
fi

# Reload systemd and start the test service
echo "Reloading systemd and enabling service ${SERVICE_NAME}..."
sudo systemctl daemon-reload
sudo systemctl enable --now "${SERVICE_NAME}"

echo "Service status (last 50 lines):"
sudo systemctl status "${SERVICE_NAME}" -l --no-pager

echo "Tail logs (journalctl -u ${SERVICE_NAME}):"
sudo journalctl -u "${SERVICE_NAME}" -n 200 --no-pager

cat <<EOF

Test instance deployed as systemd service: ${SERVICE_NAME}
Listening on port: ${PORT}
Environment file: ${ENV_FILE}
Systemd unit: ${SERVICE_UNIT}
Test DB path: ${TEST_DB_PATH}

Verify by curling:
  curl -I http://127.0.0.1:${PORT}/

When you're ready to roll out, either:
  - point production to the updated DB (careful; take backups), or
  - follow the switch helper to flip services when ready.

EOF