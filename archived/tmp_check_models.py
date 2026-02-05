#!/usr/bin/env python3
import sqlite3,json,hashlib,subprocess
from base64 import urlsafe_b64encode
DB='/prod/autotech_ai/backend/data/db.sqlite3'
con=sqlite3.connect(DB)
conf=json.loads(con.cursor().execute('select data from config order by id desc limit 1').fetchone()[0])
enc=conf.get('model_provider',{}).get('credentials',{}).get('google',{}).get('api_key_encrypted')
# decrypt
from cryptography.fernet import Fernet
kb = urlsafe_b64encode(hashlib.sha256('t0p-s3cr3t'.encode()).digest())
f = Fernet(kb)
dec = f.decrypt(enc.encode()).decode()
try:
    parsed = json.loads(dec)
    if isinstance(parsed,str):
        parsed = json.loads(parsed)
except Exception:
    parsed = json.loads(dec)
key = parsed.get('api_key')
print('Using key masked:', key[:6]+'...'+key[-6:])
# Google models
print('\n-- Google models API response contains gemini-3? --')
proc = subprocess.run(['curl','-sS',f'https://generativelanguage.googleapis.com/v1/models?key={key}'], capture_output=True, text=True)
print('contains gemini-3?', 'gemini-3' in proc.stdout)
# Server-side models
print('\n-- Server-side /api/models contains gemini-3? --')
cur=con.cursor()
row = cur.execute("select id from user where role='admin' limit 1").fetchone()
user_id=row[0]
from open_webui.utils.auth import create_token
token=create_token({'id': user_id}, expires_delta=None)
proc2=subprocess.run(['curl','-sS','-H',f'Authorization: Bearer {token}','http://127.0.0.1:8080/api/models'], capture_output=True, text=True)
print('contains gemini-3?', 'gemini-3' in proc2.stdout)
print('\n-- snippet of server models --')
print(proc2.stdout[:2000])
