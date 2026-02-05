#!/usr/bin/env python3
"""
Safe helper to update Open WebUI tool rows in backend/data/webui.db from each addon's
`openwebui_tool.py` file.

Usage:
  # Dry run (default): shows what would be changed
  ./scripts/update_openwebui_tools.py --dry-run

  # Apply updates (after verifying dry-run):
  ./scripts/update_openwebui_tools.py --apply

This script:
 - makes a timestamped backup of the DB
 - finds addons/*/openwebui_tool.py
 - attempts to map addon folder name to tool.id (e.g., addon folder 'autodb_agent' -> tool id 'autodb')
   you can override id mapping via --map 'folder:id'
 - runs in dry-run by default; use --apply to perform updates
"""

import argparse
from pathlib import Path
import sqlite3
import shutil
import datetime
import sys

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / 'backend' / 'data' / 'webui.db'
ADDONS = ROOT / 'addons'


def backup_db(db_path: Path) -> Path:
    ts = datetime.datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    backup = db_path.with_suffix(f'.{ts}.bak')
    shutil.copy2(db_path, backup)
    return backup


def find_openwebui_tools(addons_dir: Path):
    return list(addons_dir.glob('*/openwebui_tool.py'))


def apply_update(db_path: Path, tool_id: str, content: str):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute('UPDATE tool SET content = ? WHERE id = ?', (content, tool_id))
    conn.commit()
    conn.close()


def get_tool_row(db_path: Path, tool_id: str):
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    cur.execute('SELECT id, name, length(content) FROM tool WHERE id = ?', (tool_id,))
    row = cur.fetchone()
    conn.close()
    return row


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--apply', action='store_true', help='Perform the updates (default: dry run)')
    p.add_argument('--map', action='append', help='Optional folder:id mapping entries like "autodb_agent:autodb"')
    args = p.parse_args()

    mapping = {}
    if args.map:
        for m in args.map:
            if ':' in m:
                k, v = m.split(':', 1)
                mapping[k] = v

    if not DB_PATH.exists():
        print(f"DB not found at {DB_PATH}")
        sys.exit(1)

    tools = find_openwebui_tools(ADDONS)
    if not tools:
        print("No openwebui_tool.py files found under addons/")
        return

    print(f"Found {len(tools)} addon openwebui_tool.py files")

    if args.apply:
        bak = backup_db(DB_PATH)
        print(f"Created DB backup: {bak}")

    for tool_file in tools:
        folder = tool_file.parent.name
        default_id = mapping.get(folder) or folder.replace('_agent', '').replace('_', '')
        tool_id = default_id
        print(f"\n[{folder}] -> trying tool id '{tool_id}' (file: {tool_file})")

        row = get_tool_row(DB_PATH, tool_id)
        if not row:
            print(f"  - No DB row for id='{tool_id}'. Skipping. (inspect DB to find correct id)")
            continue
        print(f"  - DB row found: id={row[0]} name={row[1]} content_length={row[2]}")

        content = tool_file.read_text()
        new_len = len(content)
        print(f"  - File length: {new_len} bytes")

        if args.apply:
            apply_update(DB_PATH, tool_id, content)
            print(f"  - Updated tool id='{tool_id}' in DB")
        else:
            print(f"  - Dry run: would replace content for tool id='{tool_id}' (use --apply to write)")

    print('\nDone.')


if __name__ == '__main__':
    main()
