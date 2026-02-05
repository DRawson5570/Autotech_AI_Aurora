#!/usr/bin/env python3
import sqlite3
DB='/prod/autotech_ai/backend/data/db.sqlite3'
con=sqlite3.connect(DB)
row=con.cursor().execute("select id,email,role from user where role='admin' limit 1").fetchone()
print('admin row:', row)
if not row:
    raise SystemExit(1)
user_id=row[0]
print('user_id:', user_id)
from open_webui.utils.auth import create_token
# create token with default expiry
token = create_token({'id': user_id}, expires_delta=None)
print(token)
