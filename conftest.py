"""Test config to ensure backend test packages import correctly when running pytest from repo root."""
import os
import sys

# Ensure backend/open_webui is on sys.path so tests that import `test.*` will resolve
ROOT = os.path.dirname(__file__)
# Add the package dir (backend/open_webui) so tests that import top-level `test` package resolve
BACKEND_PKG = os.path.join(ROOT, "backend", "open_webui")
if BACKEND_PKG not in sys.path:
    sys.path.insert(0, BACKEND_PKG)

# Also add backend to allow `import open_webui` to resolve to the local package
BACKEND_DIR = os.path.join(ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
