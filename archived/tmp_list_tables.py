#!/usr/bin/env python3
import sqlite3
DB='/prod/autotech_ai/backend/data/db.sqlite3'
con=sqlite3.connect(DB)
cur=con.cursor()
cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
print('table_count:', cur.fetchone()[0])
cur.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name")
for name, sql in cur.fetchall():
    print('\nTABLE:', name)
    print(sql[:400])
