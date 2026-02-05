#!/usr/bin/env bash
set -euo pipefail

# Deploy this repo to hp6 by rsync'ing into /prod/autotech_ai and restarting the systemd service.
# Run this from your dev machine (not on the server).
#
# Requirements:
# - SSH access to the server (keys recommended)
# - rsync installed locally
# - The remote repo lives at /prod/autotech_ai
# - The remote host uses systemd service (default: autotech_ai)
#
# Typical usage:
#   ./scripts/deploy-hp6.sh --user YOUR_SSH_USER --wipe-data

HOST=hp6
DEST_DIR=/prod/autotech_ai
SSH_USER=
SERVICE_NAME=auto
# Default remote build step: rebuild repo without touching systemd unit/env.
REMOTE_DEPLOY_SCRIPT=./scripts/build-repo-on-server.sh
WIPE_DATA=false
BACKUP_DATA=true
BACKUP_RETAIN=
DRY_RUN=false

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  --host HOST             Remote host (default: ${HOST})
  --user USER             SSH user (required)
  --dest DIR              Remote destination dir (default: ${DEST_DIR})
  --service NAME          systemd service to restart (default: ${SERVICE_NAME}). Use 'auto' to detect.
  --remote-deploy PATH    Remote script to run after rsync (default: ${REMOTE_DEPLOY_SCRIPT})
                          Set to 'none' to skip.
  --no-backup-data         Skip automatic backup of ${DEST_DIR}/backend/data before deploy
  --backup-retain N        Keep only the newest N backup archives in ${DEST_DIR}/_deploy_backups (default: keep all)
  --wipe-data             Delete ${DEST_DIR}/backend/data/* on the server before deploy
  --dry-run               Print actions and run rsync with --dry-run
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --host)
      HOST="$2"; shift 2 ;;
    --user)
      SSH_USER="$2"; shift 2 ;;
    --dest)
      DEST_DIR="$2"; shift 2 ;;
    --service)
      SERVICE_NAME="$2"; shift 2 ;;
    --remote-deploy)
      REMOTE_DEPLOY_SCRIPT="$2"; shift 2 ;;
    --wipe-data)
      WIPE_DATA=true; shift 1 ;;
    --no-backup-data)
      BACKUP_DATA=false; shift 1 ;;
    --backup-retain)
      BACKUP_RETAIN="$2"; shift 2 ;;
    --dry-run)
      DRY_RUN=true; shift 1 ;;
    -h|--help)
      usage; exit 0 ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "${SSH_USER}" ]]; then
  echo "--user is required" >&2
  usage
  exit 2
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync not found on this machine." >&2
  exit 1
fi

REMOTE="${SSH_USER}@${HOST}"

detect_remote_service_name() {
  # Prefer your suspected service name, then fall back to the known ones used by repo scripts.
  # Returns the detected service name, or empty string if nothing found.
  local candidates=(autotech_ai open-webui-local open-webui)
  local found=()

  for svc in "${candidates[@]}"; do
    # check unit files first, then loaded units
    if ssh -t "${REMOTE}" "systemctl list-unit-files --type=service --no-legend 2>/dev/null | awk '{print \$1}' | grep -qx '${svc}.service'"; then
      found+=("${svc}")
    elif ssh -t "${REMOTE}" "systemctl list-units --type=service --all --no-legend 2>/dev/null | awk '{print \$1}' | grep -qx '${svc}.service'"; then
      found+=("${svc}")
    fi
  done

  if [[ ${#found[@]} -eq 0 ]]; then
    echo ""
    return 0
  fi

  # If multiple, keep the first (candidate order is priority order)
  echo "${found[0]}"
}

echo "Deploy target: ${REMOTE}:${DEST_DIR}"
if [[ "${SERVICE_NAME}" == "auto" ]]; then
  echo "Service: auto (will detect on remote)"
else
  echo "Service: ${SERVICE_NAME}"
fi
echo "Remote deploy script: ${REMOTE_DEPLOY_SCRIPT}"
echo "Backup data: ${BACKUP_DATA}"
echo "Backup retain: ${BACKUP_RETAIN:-all}"
echo "Wipe data: ${WIPE_DATA}"

SSH_FLAGS=()
if [[ "${DRY_RUN}" == true ]]; then
  echo "DRY RUN enabled"
fi

if [[ "${SERVICE_NAME}" == "auto" ]]; then
  if [[ "${DRY_RUN}" == true ]]; then
    echo "Skipping service auto-detect in dry-run; will use 'autotech_ai' for preview."
    SERVICE_NAME=autotech_ai
  else
    echo "Detecting systemd service name on remote..."
    detected=$(detect_remote_service_name)
    if [[ -n "${detected}" ]]; then
      SERVICE_NAME="${detected}"
      echo "Detected service: ${SERVICE_NAME}"
    else
      echo "WARNING: Could not auto-detect service name on remote. Defaulting to autotech_ai." >&2
      SERVICE_NAME=autotech_ai
    fi
  fi
fi

# Stop service first (ignore failure if service doesn't exist yet)
echo "Stopping service on remote..."
if [[ "${DRY_RUN}" == true ]]; then
  echo "ssh -t ${REMOTE} sudo systemctl stop ${SERVICE_NAME}"
else
  ssh -t "${REMOTE}" "sudo systemctl stop '${SERVICE_NAME}' || true"
fi

# Backup server-side data before any destructive action
if [[ "${BACKUP_DATA}" == true ]]; then
  echo "Backing up remote data dir..."
  if [[ "${DRY_RUN}" == true ]]; then
    echo "ssh -t ${REMOTE} 'mkdir -p ${DEST_DIR}/_deploy_backups && ts=\$(date +%Y%m%d_%H%M%S) && sudo tar -czf ${DEST_DIR}/_deploy_backups/backend-data-\${ts}.tgz -C ${DEST_DIR}/backend data'"
  else
    ssh -tt "${REMOTE}" "mkdir -p '${DEST_DIR}/_deploy_backups' && ts=\$(date +%Y%m%d_%H%M%S) && sudo tar -czf '${DEST_DIR}/_deploy_backups/backend-data-'\${ts}'.tgz' -C '${DEST_DIR}/backend' data"
  fi

  if [[ -n "${BACKUP_RETAIN:-}" ]]; then
    if [[ ! "${BACKUP_RETAIN}" =~ ^[0-9]+$ ]]; then
      echo "ERROR: --backup-retain must be a non-negative integer" >&2
      exit 2
    fi
    echo "Pruning remote backups (retain ${BACKUP_RETAIN})..."
    if [[ "${DRY_RUN}" == true ]]; then
      echo "ssh -t ${REMOTE} 'cd ${DEST_DIR}/_deploy_backups && ls -1t backend-data-*.tgz 2>/dev/null | tail -n +$((BACKUP_RETAIN+1)) | xargs -r sudo rm -f --'"
    else
      ssh -tt "${REMOTE}" "cd '${DEST_DIR}/_deploy_backups' && ls -1t backend-data-*.tgz 2>/dev/null | tail -n +$((BACKUP_RETAIN+1)) | xargs -r sudo rm -f --"
    fi
  fi
fi

# Optionally wipe server-side data
if [[ "${WIPE_DATA}" == true ]]; then
  echo "Wiping remote data dir..."
  if [[ "${DRY_RUN}" == true ]]; then
    echo "ssh -t ${REMOTE} sudo rm -rf ${DEST_DIR}/backend/data/*"
  else
    ssh -t "${REMOTE}" "sudo rm -rf '${DEST_DIR}/backend/data/'* || true"
  fi
fi

# Rsync repo contents to remote dest
echo "Rsyncing repo to remote..."
RSYNC_FLAGS=(
  -az
  --delete
  --info=progress2
  --exclude .git/
  --exclude node_modules/
  --exclude .svelte-kit/
  --exclude backend/data/
  --exclude backend/__pycache__/
  --exclude '**/__pycache__/'
  --exclude '**/*.pyc'
  --exclude website/nginx.conf
)

if [[ "${DRY_RUN}" == true ]]; then
  RSYNC_FLAGS+=(--dry-run)
fi

rsync "${RSYNC_FLAGS[@]}" ./ "${REMOTE}:${DEST_DIR}/"

# Run optional on-server script (build deps, etc.)
if [[ "${REMOTE_DEPLOY_SCRIPT}" == "none" ]]; then
  echo "Skipping remote deploy step (--remote-deploy none)"
else
  echo "Running remote deploy script..."
  if [[ "${DRY_RUN}" == true ]]; then
    echo "ssh -t ${REMOTE} 'cd ${DEST_DIR} && bash ${REMOTE_DEPLOY_SCRIPT}'"
  else
    # Use login shell so PATH/profile are loaded (helps conda/node resolution on servers)
    ssh -tt "${REMOTE}" "cd '${DEST_DIR}' && /bin/bash -lc \"bash '${REMOTE_DEPLOY_SCRIPT}'\""
  fi
fi

# Ensure service is started (explicit)
echo "Starting service on remote..."
if [[ "${DRY_RUN}" == true ]]; then
  echo "ssh -t ${REMOTE} sudo systemctl enable --now ${SERVICE_NAME}"
  echo "ssh -t ${REMOTE} sudo systemctl status ${SERVICE_NAME} --no-pager"
else
  ssh -t "${REMOTE}" "sudo systemctl enable --now '${SERVICE_NAME}'"
  ssh -t "${REMOTE}" "sudo systemctl status '${SERVICE_NAME}' -l --no-pager || true"
fi

echo "Done. Tail logs with: ssh -t ${REMOTE} 'sudo journalctl -u ${SERVICE_NAME} -f'"
