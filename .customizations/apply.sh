#!/bin/bash
# Re-apply Autotech AI customizations after pulling upstream updates
#
# Usage: ./.customizations/apply.sh [--dry-run]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

DRY_RUN=""
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN="--check"
    echo "=== DRY RUN MODE - No changes will be made ==="
fi

echo "=== Applying Autotech AI Customizations ==="
echo "Project root: $PROJECT_ROOT"
echo ""

# Function to apply a patch with fallback
apply_patch() {
    local patch_file="$1"
    local description="$2"
    
    if [[ ! -f "$SCRIPT_DIR/$patch_file" ]]; then
        echo "⚠️  Skipping $description - patch file not found"
        return
    fi
    
    echo "Applying: $description"
    
    if git apply $DRY_RUN "$SCRIPT_DIR/$patch_file" 2>/dev/null; then
        echo "✅ $description applied successfully"
    else
        echo "⚠️  $description had conflicts - trying 3-way merge..."
        if git apply --3way $DRY_RUN "$SCRIPT_DIR/$patch_file" 2>/dev/null; then
            echo "✅ $description applied with 3-way merge"
        else
            echo "❌ $description FAILED - manual intervention needed"
            echo "   Review: $SCRIPT_DIR/$patch_file"
        fi
    fi
    echo ""
}

# Try master patch first
echo "=== Attempting master patch ==="
if git apply $DRY_RUN "$SCRIPT_DIR/all_changes.patch" 2>/dev/null; then
    echo "✅ All changes applied successfully from master patch!"
    exit 0
fi

echo "Master patch had conflicts - applying individual patches..."
echo ""

# Apply individual patches
echo "=== Backend Patches ==="
apply_patch "main_py.patch" "Main application (routers)"
apply_patch "config.patch" "Configuration settings"
apply_patch "env.patch" "Environment variables"
apply_patch "db.patch" "Database session handling"
apply_patch "users_model.patch" "User model (phone/address)"
apply_patch "users_router.patch" "User router (permissions)"

echo "=== Frontend Patches ==="
apply_patch "auth_page.patch" "Auth page (cache clearing)"
apply_patch "app_layout.patch" "App layout (Stripe handling)"

echo ""
echo "=== Summary ==="
echo "Patches applied. Next steps:"
echo "1. Review any conflicts marked with ❌"
echo "2. Run: alembic upgrade head"
echo "3. Rebuild frontend: npm run build"
echo "4. Test critical features: billing, mitchell, login"
echo ""
echo "New files (should already exist):"
cat "$SCRIPT_DIR/new_files.txt" | head -20
echo "... (see new_files.txt for full list)"
