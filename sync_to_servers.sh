#!/bin/bash
# Sync Autotech AI project files to production servers
# Usage: ./sync_to_servers.sh [--prod-only | --backup-only]

set -e

PROD_SERVER="poweredge1"
BACKUP_SERVER="poweredge2"
REMOTE_PATH="/prod/autotech_ai"
LOCAL_PATH="/home/drawson/autotech_ai"

# Files/folders to exclude from sync
EXCLUDES=(
    ".git"
    "__pycache__"
    "*.pyc"
    ".env"
    "node_modules"
    "*.log"
    "cypress/videos"
    "cypress/screenshots"
    ".pytest_cache"
    "*.pid"
    "backend/data/*.db"
    "backend/data/*.db-journal"
    "backend/data/*.db.local_backup"
    "backend/data/vector_db"
    "backend/data/vector_db.local_backup"
    "backend/data/uploads"
    "vite.config.ts.timestamp-*"
)

# Build exclude string for rsync
EXCLUDE_ARGS=""
for exc in "${EXCLUDES[@]}"; do
    EXCLUDE_ARGS="$EXCLUDE_ARGS --exclude=$exc"
done

sync_server() {
    local server=$1
    local server_name=$2
    
    echo "=========================================="
    echo "Syncing to $server_name ($server)..."
    echo "=========================================="
    
    rsync -avz --delete \
        $EXCLUDE_ARGS \
        "$LOCAL_PATH/" \
        "$server:$REMOTE_PATH/"
    
    echo ""
    echo "✓ $server_name sync complete"
    echo ""
}

# Parse arguments
SYNC_PROD=true
SYNC_BACKUP=true

if [ "$1" == "--prod-only" ]; then
    SYNC_BACKUP=false
elif [ "$1" == "--backup-only" ]; then
    SYNC_PROD=false
fi

echo "Autotech AI Server Sync"
echo "======================="
echo "Local:  $LOCAL_PATH"
echo "Remote: $REMOTE_PATH"
echo ""

if [ "$SYNC_PROD" = true ]; then
    sync_server "$PROD_SERVER" "Production"
fi

if [ "$SYNC_BACKUP" = true ]; then
    sync_server "$BACKUP_SERVER" "Backup"
fi

echo "=========================================="
echo "All syncs complete!"
echo "=========================================="
echo ""
echo "Note: Services may need restart after sync:"
echo "  ssh $PROD_SERVER 'sudo systemctl restart autotech_ai'"
echo "  ssh $BACKUP_SERVER 'sudo systemctl restart autotech_ai'"
