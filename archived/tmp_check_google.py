#!/usr/bin/env python3
import json, sqlite3, os, hashlib
from base64 import urlsafe_b64encode
DB='/prod/autotech_ai/backend/data/db.sqlite3'
print('DB exists:', os.path.exists(DB))
con=sqlite3.connect(DB)
row=con.cursor().execute('select data from config order by id desc limit 1').fetchone()
conf=json.loads(row[0])
google = conf.get('model_provider',{}).get('credentials',{}).get('google')
enc = google.get('api_key_encrypted') if google else None
envfile='/etc/default/autotech_ai'
env={}
try:
    with open(envfile) as f:
        for l in f:
            l = l.strip()
            if not l or l.startswith('#'):
                continue
            if '=' in l:
                k,v = l.split('=',1)
                v = v.strip().strip('"').strip("'")
                env[k.strip()] = v
except Exception as e:
    print('read env error',e)
key = env.get('OAUTH_CLIENT_INFO_ENCRYPTION_KEY') or env.get('WEBUI_SECRET_KEY') or os.environ.get('OAUTH_CLIENT_INFO_ENCRYPTION_KEY')
print('key found:', bool(key))
if key:
    print('key len:', len(key))
try:
    from cryptography.fernet import Fernet
    if not key:
        raise Exception('no key')
    kb = urlsafe_b64encode(hashlib.sha256(key.encode()).digest()) if len(key)!=44 else key.encode()
    f = Fernet(kb)
    dec = f.decrypt(enc.encode()).decode()
    print('decrypted:', dec)
except Exception as e:
    print('decryption error:', repr(e))
print('google keys:', list((google or {}).keys()))
print('top-level google config snippet:')
print(json.dumps(conf.get('google',{}), indent=2)[:1000])
