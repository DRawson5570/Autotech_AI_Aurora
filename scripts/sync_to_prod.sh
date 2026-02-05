#!/usr/bin/env bash
# Sync repository to production server using rsync while excluding sensitive/config/database files.
# Default: dry-run. Requires SSH access to the target (poweredge2) and write permission to the destination path.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

# Defaults (adjust with env vars or CLI flags)
REMOTE_HOST=${REMOTE_HOST:-poweredge1}
REMOTE_USER=${REMOTE_USER:-$USER}
REMOTE_PATH=${REMOTE_PATH:-/prod/autotech_ai}
SSH_PORT=${SSH_PORT:-22}

# Exclude file - by default we use scripts/rsync_excludes.txt
EXCLUDE_FILE=${EXCLUDE_FILE:-$SCRIPT_DIR/rsync_excludes.txt}
RSYNC_OPTS_DEFAULT=(--archive --compress --stats --human-readable --progress)
# By default we will NOT run --delete until explicitly asked (safe mode)
RSYNC_DELETE_FLAG=""
# By default dry-run (safe)
DRY_RUN=--dry-run
VERBOSE=0

usage() {
  cat <<EOF
Usage: $0 [options]

Options:
  -h, --help         Show this message and exit
  -H, --host HOST    Remote host (default: ${REMOTE_HOST})
  -u, --user USER    Remote SSH user (default: ${REMOTE_USER})
  -p, --path PATH    Remote destination path (default: ${REMOTE_PATH})
  -P, --port PORT    SSH port (default: ${SSH_PORT})
  -n, --no-dry-run   Actually perform the sync (default is dry-run)
  -d, --delete       Allow rsync --delete to remove files on remote (use with care)
  -e, --exclude FILE Use a custom exclude-file
  -v, --verbose      Show rsync output

Examples:
  # Dry-run (default):
  $0

  # Real sync (no-dry-run):
  DRY_RUN="" $0 --no-dry-run

  # Real sync with delete (be careful):
  DRY_RUN="" $0 --no-dry-run --delete

Notes:
  - The script will by default exclude sensitive files and backend/data (DB files). See $EXCLUDE_FILE to modify the exclude list.
  - The script does NOT overwrite any server-side system config outside of the repository path. Ensure the remote path is correct.
EOF
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    -H|--host) REMOTE_HOST="$2"; shift 2;;
    -u|--user) REMOTE_USER="$2"; shift 2;;
    -p|--path) REMOTE_PATH="$2"; shift 2;;
    -P|--port) SSH_PORT="$2"; shift 2;;
    -n|--no-dry-run) DRY_RUN=""; shift 1;;
    -d|--delete) RSYNC_DELETE_FLAG="--delete"; shift 1;;
    -e|--exclude) EXCLUDE_FILE="$2"; shift 2;;
    -v|--verbose) VERBOSE=1; shift 1;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown option: $1"; usage; exit 1;;
  esac
done

REMOTE_DEST="${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"

if [[ ! -f "$EXCLUDE_FILE" ]]; then
  echo "Exclude file not found: $EXCLUDE_FILE" >&2
  exit 1
fi

# Build rsync args
RSYNC_OPTS=("${RSYNC_OPTS_DEFAULT[@]}")
# Exclude-from uses our exclude file
RSYNC_OPTS+=(--exclude-from="$EXCLUDE_FILE")
# If verbose print more info
if [[ $VERBOSE -eq 1 ]]; then
  RSYNC_OPTS+=(--verbose)
fi
# If delete requested add flag
if [[ -n "$RSYNC_DELETE_FLAG" ]]; then
  RSYNC_OPTS+=("$RSYNC_DELETE_FLAG")
fi

# SSH options: keep HostKeyChecking default, but allow specifying port
SSH_CMD="ssh -p ${SSH_PORT}"
RSYNC_OPTS+=(--rsh="$SSH_CMD")

# Prevent accidental rsyncing of working tree changes outside repo
cd "$REPO_ROOT"

echo "Preparing to sync from: $REPO_ROOT"
echo "Destination: $REMOTE_DEST"
echo "Exclude file: $EXCLUDE_FILE"
if [[ -n "$DRY_RUN" ]]; then
  echo "Mode: dry-run (no changes will be made). Use --no-dry-run to apply changes."
else
  echo "Mode: APPLYING changes (no --dry-run)."
fi

# Show rsync command for review
echo
echo "rsync command preview:"
echo rsync ${RSYNC_OPTS[*]} . "${REMOTE_DEST}"

# Confirm if delete enabled and not dry-run
if [[ -n "$RSYNC_DELETE_FLAG" && -z "$DRY_RUN" ]]; then
  echo
  echo "WARNING: --delete is enabled and you are applying changes. This may remove files on remote." >&2
  read -p "Type 'yes' to proceed: " confirm
  if [[ "$confirm" != "yes" ]]; then
    echo "Aborting."; exit 1
  fi
fi

# Execute rsync
set -x
rsync ${DRY_RUN:+--dry-run} ${RSYNC_OPTS[@]} ./ "${REMOTE_DEST}" || {
  echo "rsync returned non-zero exit status." >&2
  exit 2
}
set +x

echo
echo "Sync finished (dry-run=${DRY_RUN:+true}). Review output above."

# Optional: run remote health check (disabled by default)
# echo "Running optional remote health check..."
# ssh -p $SSH_PORT ${REMOTE_USER}@${REMOTE_HOST} "curl -sS http://127.0.0.1:8080/openapi.json | jq '.paths | keys[]' | grep /api/v1/billing || true"

exit 0
